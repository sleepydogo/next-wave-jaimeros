"""Ejecuta la llamada. Modo real (Twilio) o simulado (para demo sin gastar)."""
import asyncio
import json
import logging
import time
import uuid

from .. import bus, costs, db, events, state
from ..config import (PUBLIC_URL, SIMULATE_CALLS, TWILIO_ACCOUNT_SID,
                      TWILIO_AUTH_TOKEN, TWILIO_FROM)
from ..state import r as redis_client
from . import brain, report

log = logging.getLogger("caller")

# Respuestas del conductor en modo simulado. Pasan por el brain real.
SIM_REPLIES = {
    "arrival_check": ["Si, ya llegue, estoy en la fila. Dame diez minutos que termino de acomodar.",
                      "Listo, cualquier cosa avisame."],
    "load_authorized": ["Dale, perfecto, voy para alla ahora mismo.", "Gracias."],
    "emergency": ["Y... la verdad estoy muy cansado, vengo manejando desde las cuatro de la manana. "
                  "Pare un toque porque me estaba durmiendo.",
                  "Si, voy a descansar veinte minutos y sigo."],
}


async def save_session(call_id, s):
    await redis_client.set(f"call:{call_id}", json.dumps(s), ex=3600)


async def load_session(call_id):
    v = await redis_client.get(f"call:{call_id}")
    return json.loads(v) if v else None


async def start(payload, reason, detail="", source_event_id=None, event_type=None):
    """Arranca una llamada. Devuelve call_id."""
    call_id = uuid.uuid4().hex[:12]
    payload = dict(payload)
    if detail:
        payload["detail"] = detail
    trip_id = payload.get("trip_id", "unknown")
    event_type = event_type or {"arrival_check": events.TRUCK_ARRIVED,
                                "load_authorized": events.PORT_READY,
                                "emergency": events.TRUCK_STOPPED}.get(reason, events.TRUCK_STOPPED)
    event = {"schema_version": 1, "event_id": source_event_id or events.new_id(),
             "type": event_type, "payload": payload, "ts": time.time()}
    ctx = {"name": payload.get("worker_name", "conductor"),
           "phone": payload.get("worker_phone", ""), "port": payload.get("port_name", "el puerto"),
           "container": payload.get("container", "el contenedor"), "detail": payload.get("detail", ""),
           "trip_id": trip_id}
    opener = brain.opener(reason, ctx)
    session = {"trip_id": trip_id, "reason": reason, "ctx": ctx, "event": event,
               "history": [{"role": "assistant", "content": opener}],
               "t0": time.time(), "last_ts": time.time(),
               "asr_turns": 0, "tok_in": 0, "tok_out": 0}
    await save_session(call_id, session)
    # transcript queda NULL a proposito: el saludo todavia no fue dicho ni
    # escuchado por nadie. Si la llamada no llega a tener conversacion real,
    # el dashboard tiene que mostrar "sin transcripcion", no un texto inventado.
    db.x("INSERT INTO calls (id,trip_id,reason,status,transcript,ts) VALUES (?,?,?,?,?,?)",
         (call_id, trip_id, reason, "ringing", None, time.time()))
    log.info("llamada %s -> %s (%s)", call_id, ctx["phone"], reason)

    try:
        events.validate_trigger(event_type, payload)
    except ValueError as exc:
        log.warning("evento invalido para llamada %s: %s", call_id, exc)
        await finish(call_id, status="failed")
    else:
        if SIMULATE_CALLS:
            asyncio.create_task(_simulate(call_id))
        else:
            try:
                sid = await asyncio.to_thread(_twilio_dial, call_id, ctx["phone"])
                db.x("UPDATE calls SET twilio_sid=? WHERE id=?", (sid, call_id))
                log.info("llamada %s iniciada twilio_sid=%s telefono=***%s", call_id, sid,
                         ctx["phone"][-4:])
            except Exception:
                log.exception("twilio fallo al iniciar call_id=%s", call_id)
                await finish(call_id, status="failed")
    return call_id


def _twilio_dial(call_id, to):
    from twilio.rest import Client
    call = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN).calls.create(
        to=to, from_=TWILIO_FROM,
        url=f"{PUBLIC_URL}/twilio/voice/{call_id}",
        status_callback=f"{PUBLIC_URL}/twilio/status/{call_id}",
        status_callback_method="POST",
        status_callback_event=["completed"],
    )
    return call.sid


async def turn(call_id, user_said, latency_s, confidence=None):
    """Un turno de conversacion. Devuelve (reply, done)."""
    s = await load_session(call_id)
    if not s:
        return "Gracias, hasta luego.", True
    s["history"].append({"role": "user", "content": user_said})
    s["asr_turns"] += 1

    out, (ti, to) = await brain.respond(s["reason"], s["history"], s["ctx"])
    if s["asr_turns"] >= 2 and not out.get("done"):
        out = {**out, "done": True,
               "outcome": {**out.get("outcome", {}), "needs_human": True}}
    s["tok_in"] += ti
    s["tok_out"] += to
    s["history"].append({"role": "assistant", "content": out["reply"]})
    s["last_ts"] = time.time()
    await save_session(call_id, s)

    vm = brain.voice_metrics(out.get("voice", {}), user_said, latency_s, confidence)
    transcript = "\n".join(f"{'AGENTE' if m['role'] == 'assistant' else 'CONDUCTOR'}: {m['content']}"
                           for m in s["history"])
    db.x("UPDATE calls SET transcript=?, outcome=?, voice=? WHERE id=?",
         (transcript, json.dumps(out.get("outcome", {})), json.dumps(vm), call_id))
    return out["reply"], bool(out.get("done"))


async def finish(call_id, duration_s=None, status="done"):
    if not await state.once(f"call:{call_id}:finish", ttl=86400):
        return
    s = await load_session(call_id)
    if not s:
        return
    dur = duration_s if duration_s is not None else time.time() - s["t0"]
    cost = costs.call_cost(dur, s["asr_turns"], s["tok_in"], s["tok_out"])
    db.x("UPDATE calls SET status=?, duration_s=?, cost_usd=? WHERE id=?",
         (status, dur, cost, call_id))
    row = db.one("SELECT * FROM calls WHERE id=?", (call_id,))
    transcript = row["transcript"] or ""
    outcome = json.loads(row["outcome"] or "{}")
    voice = json.loads(row["voice"] or "{}")
    built = report.build(s["event"], {"call_id": call_id}, outcome, voice, status, transcript)
    await bus.publish(events.CALL_FINISHED, {
        "trip_id": s["trip_id"], "call_id": call_id, "reason": s["reason"],
        "source_event_id": s["event"]["event_id"], "report": built,
        "cost_usd": cost,
    })


async def _simulate(call_id):
    """Corre la conversacion completa sin telefono. Sirve para demo y para tests."""
    s = await load_session(call_id)
    await asyncio.sleep(1.5)
    for reply in SIM_REPLIES.get(s["reason"], ["Si, dale."]):
        await asyncio.sleep(1.2)
        _, done = await turn(call_id, reply, latency_s=1.8, confidence=0.88)
        if done:
            break
    await finish(call_id)

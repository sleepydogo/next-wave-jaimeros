"""Webhooks de Twilio: aca ocurre la conversacion real por telefono.

Flujo: Twilio llama -> /voice devuelve TwiML con <Gather input="speech">
-> el conductor habla -> Twilio postea el texto a /gather -> el brain responde
-> se repite hasta done -> /status cierra y calcula el costo.
"""
import time
from xml.sax.saxutils import escape

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator

from ..agent import caller
from ..config import PUBLIC_URL, TWILIO_AUTH_TOKEN, VALIDATE_TWILIO_SIGNATURE

router = APIRouter(prefix="/twilio", tags=["twilio"])

VOICE = 'voice="Polly.Mia" language="es-MX"'


def _twiml(xml: str):
    return Response(content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{xml}</Response>',
                    media_type="application/xml")


def _ask(call_id: str, text: str):
    return _twiml(
        f'<Gather input="speech" language="es-AR" speechTimeout="auto" '
        f'action="{PUBLIC_URL}/twilio/gather/{call_id}" method="POST">'
        f'<Say {VOICE}>{escape(text)}</Say></Gather>'
        f'<Say {VOICE}>No te escuche. Te vuelvo a llamar en un rato.</Say>')


def _bye(text: str):
    return _twiml(f'<Say {VOICE}>{escape(text)}</Say><Hangup/>')


@router.post("/voice/{call_id}", summary="Arranque de la llamada (lo llama Twilio)")
async def voice(call_id: str, request: Request):
    """Twilio pega aca cuando el conductor atiende. **Devuelve TwiML, no JSON.**

    Responde con un `<Gather input="speech">` y el saludo del agente en `<Say>`.

    Si la sesion ya no existe en Redis (TTL 1 h) devuelve un `<Hangup/>` con
    disculpa.
    """
    _validate_signature(request, dict(await request.form()))
    s = await caller.load_session(call_id)
    if not s:
        return _bye("Hubo un problema con la llamada. Perdon.")
    s["last_ts"] = time.time()
    await caller.save_session(call_id, s)
    return _ask(call_id, s["history"][0]["content"])


@router.post("/gather/{call_id}", summary="El conductor hablo (lo llama Twilio)")
async def gather(call_id: str, request: Request, SpeechResult: str = Form(default=""),
                 Confidence: float = Form(default=0.0)):
    """Twilio postea lo que transcribio. **Devuelve TwiML, no JSON.**

    El brain decide la respuesta y se devuelve otro `<Gather>` si la
    conversacion sigue, o `<Say>` + `<Hangup/>` si ya termino.

    `SpeechResult` vacio -> repregunta en vez de cortar.

    La latencia entre el prompt y esta respuesta se mide y entra en las metricas
    de voz como senal de hesitacion.
    """
    _validate_signature(request, dict(await request.form()))
    s = await caller.load_session(call_id)
    latency = time.time() - s["last_ts"] if s else 2.0
    if not SpeechResult:
        if s:
            s["empty_turns"] = s.get("empty_turns", 0) + 1
            await caller.save_session(call_id, s)
            if s["empty_turns"] >= 2:
                await caller.finish(call_id, status="failed")
                return _bye("No pude escucharte. Voy a avisar a operaciones.")
        return _ask(call_id, "Perdon, no te escuche bien. Me repetis?")
    reply, done = await caller.turn(call_id, SpeechResult, latency, Confidence or None)
    return _bye(reply) if done else _ask(call_id, reply)


@router.post("/status/{call_id}", summary="Fin de llamada (lo llama Twilio)")
async def status(call_id: str, request: Request):
    """Callback de fin de llamada.

    Cierra la llamada, calcula el costo real (minuto iniciado de Twilio + ASR +
    tokens) y publica `call.finished` en el bus.

    **Es el unico lugar donde se escribe `cost_usd`.**
    """
    form = await request.form()
    _validate_signature(request, dict(form))
    dur = float(form.get("CallDuration") or 0) or None
    twilio_status = str(form.get("CallStatus") or "completed").lower()
    status_map = {"completed": "done", "failed": "failed", "no-answer": "no_answer", "busy": "busy"}
    await caller.finish(call_id, dur, status_map.get(twilio_status, "failed"))
    return {"ok": True}


def _validate_signature(request: Request, form):
    if not VALIDATE_TWILIO_SIGNATURE:
        return
    signature = request.headers.get("X-Twilio-Signature")
    if not signature or not TWILIO_AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="firma Twilio ausente")
    url = f"{PUBLIC_URL}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    if not RequestValidator(TWILIO_AUTH_TOKEN).validate(url, form, signature):
        raise HTTPException(status_code=403, detail="firma Twilio invalida")

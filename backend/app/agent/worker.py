"""Reacciona a los eventos del bus decidiendo a quien llamar y por que."""
import logging

from .. import bus, db, events
from . import caller

log = logging.getLogger("agent")


@bus.on(events.TRUCK_ARRIVED)
async def on_arrived(p, msg=None):
    """Llego al puerto -> preguntarle si esta listo para recibir la carga."""
    await caller.start(p, "arrival_check", source_event_id=(msg or {}).get("event_id"), event_type=events.TRUCK_ARRIVED)


@bus.on(events.PORT_READY)
async def on_port_ready(p, msg=None):
    """El puerto habilito -> avisarle que puede pasar a cargar."""
    db.x("UPDATE trips SET status='habilitado' WHERE id=?", (p["trip_id"],))
    await caller.start(p, "load_authorized", source_event_id=(msg or {}).get("event_id"), event_type=events.PORT_READY)


@bus.on(events.TRUCK_STOPPED)
async def on_stopped(p, msg=None):
    mins = max(1, round(p["seconds"] / 60))
    await bus.publish(events.ALERT_RAISED, {
        "trip_id": p["trip_id"], "severity": "alta",
        "title": f"Camion detenido {mins} min en ruta",
        "body": f"Parada no planificada en {p['lat']:.4f},{p['lon']:.4f}. Llamando al conductor.",
    })
    await caller.start(p, "emergency", detail=f"estas detenido hace {mins} minutos",
                       source_event_id=(msg or {}).get("event_id"), event_type=events.TRUCK_STOPPED)


@bus.on(events.TRUCK_SLOWDOWN)
async def on_slowdown(p, msg=None):
    await bus.publish(events.ALERT_RAISED, {
        "trip_id": p["trip_id"], "severity": "media",
        "title": f"Caida abrupta de velocidad ({p['drop_pct']}%)",
        "body": "Posible frenada brusca o incidente. Llamando al conductor.",
    })
    await caller.start(p, "emergency", detail=f"bajaste la velocidad de golpe un {p['drop_pct']} por ciento",
                       source_event_id=(msg or {}).get("event_id"), event_type=events.TRUCK_SLOWDOWN)


@bus.on(events.CALL_FINISHED)
async def on_call_finished(p, msg=None):
    """Cierra el ciclo: actualiza el viaje y escala si la voz da mal."""
    trip_id, out, voice = p["trip_id"], p.get("outcome", {}), p.get("voice", {})

    if p["reason"] == "arrival_check":
        status = "esperando_puerto" if out.get("available") else "en_puerto"
        db.x("UPDATE trips SET status=? WHERE id=?", (status, trip_id))
    elif p["reason"] == "load_authorized" and out.get("available") is not False:
        db.x("UPDATE trips SET status='cargando' WHERE id=?", (trip_id,))

    risk = voice.get("risk", 0)
    if risk >= 0.6 or out.get("needs_human"):
        await bus.publish(events.ALERT_RAISED, {
            "trip_id": trip_id, "severity": "alta" if risk >= 0.6 else "media",
            "title": f"Estado del conductor: riesgo {risk}",
            "body": (f"fatiga={voice.get('fatigue')} estres={voice.get('stress')}. "
                     f"{voice.get('notes', '')} | {out.get('problem') or ''}"),
        })

"""Nombres y helpers del contrato de eventos version 1."""

import time
import uuid
import re

SCHEMA_VERSION = 1

TRUCK_ARRIVED = "truck.arrived"          # el camion entro al geofence del puerto
TRUCK_STOPPED = "truck.stopped"          # parada no planificada en ruta
TRUCK_SLOWDOWN = "truck.slowdown"        # caida abrupta de velocidad
TRUCK_HARSH = "truck.harsh_event"        # frenada / aceleracion brusca
PORT_READY = "port.ready"                # el puerto habilito la carga
CALL_FINISHED = "call.finished"          # el agente termino una llamada
ALERT_RAISED = "alert.raised"            # emergencia -> dispatcher

ALL = [
    TRUCK_ARRIVED, TRUCK_STOPPED, TRUCK_SLOWDOWN, TRUCK_HARSH,
    PORT_READY, CALL_FINISHED, ALERT_RAISED,
]

TRIGGER_EVENTS = [TRUCK_ARRIVED, PORT_READY, TRUCK_STOPPED, TRUCK_SLOWDOWN]


def new_id(prefix="evt"):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def envelope(event_type, payload, event_id=None, ts=None):
    return {"schema_version": SCHEMA_VERSION, "event_id": event_id or new_id(),
            "type": event_type, "payload": payload, "ts": ts or time.time()}


def validate_trigger(event_type, payload):
    """Validacion chica y determinista para no llamar con datos incompletos."""
    required = {"trip_id", "worker_id", "worker_name", "worker_phone",
                "lat", "lon", "location_label"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"faltan campos: {', '.join(missing)}")
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", str(payload["worker_phone"])):
        raise ValueError("worker_phone no esta en formato E.164")
    if event_type in (TRUCK_ARRIVED, PORT_READY) and not payload.get("port_name"):
        raise ValueError("falta port_name")
    if event_type == TRUCK_STOPPED and "seconds" not in payload:
        raise ValueError("falta seconds")
    if event_type == TRUCK_SLOWDOWN and "drop_pct" not in payload:
        raise ValueError("falta drop_pct")

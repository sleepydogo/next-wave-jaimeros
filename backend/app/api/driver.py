"""Endpoints que consume la app movil del conductor."""
import time

from fastapi import APIRouter
from pydantic import BaseModel

from .. import db
from ..detector import worker as detector

router = APIRouter(prefix="/driver", tags=["driver"])


class Ping(BaseModel):
    trip_id: str
    lat: float
    lon: float
    speed: float = 0.0


@router.get("/{driver_id}/trip", summary="Viaje activo del conductor")
def current_trip(driver_id: str):
    """Pantalla principal de la app: `{trip, calls}`.

    Devuelve el ultimo viaje que no este `cerrado` y sus ultimas 5 llamadas.
    Si el conductor no tiene viaje activo devuelve `{"trip": null}`.

    En la demo el `driver_id` es `d1`.
    """
    trip = db.one(
        "SELECT * FROM trips WHERE driver_id=? AND status!='cerrado' ORDER BY created_at DESC LIMIT 1",
        (driver_id,))
    if not trip:
        return {"trip": None}
    calls = db.q("SELECT id,reason,status,ts FROM calls WHERE trip_id=? ORDER BY ts DESC LIMIT 5",
                 (trip["id"],))
    return {"trip": trip, "calls": calls}


@router.post("/ping", summary="Posicion GPS del camion")
async def ping(p: Ping):
    """La app manda posicion cada pocos segundos. **Es el unico input del detector.**

    `speed` va en km/h. Devuelve `{"ok": true, "status": <estado del viaje>}`.

    Segun donde caiga la posicion, el detector puede publicar un evento:

    | situacion | evento | consecuencia |
    |---|---|---|
    | entra al geofence del puerto (800 m) | `truck.arrived` | llamada `arrival_check` |
    | 3+ pings seguidos < 3 km/h por 120 s | `truck.stopped` | alerta alta + llamada `emergency` |
    | cae >60% viniendo a mas de 40 km/h | `truck.slowdown` | alerta media + llamada `emergency` |

    Hay un **lock anti-spam** en Redis: mandar 50 pings iguales dentro del
    geofence genera **una sola** llamada.

    Para probar una parada sin esperar 2 minutos, bajar antes el threshold con
    `POST /ops/thresholds/stop_min_seconds?value=8`.
    """
    await detector.process_ping(p.trip_id, {"lat": p.lat, "lon": p.lon,
                                            "speed": p.speed, "ts": time.time()})
    trip = db.one("SELECT status FROM trips WHERE id=?", (p.trip_id,))
    return {"ok": True, "status": trip["status"] if trip else None}


@router.post("/{trip_id}/ack", summary="'Ya estoy listo para cargar'")
def ack(trip_id: str):
    """Boton en la app que evita una llamada: pasa el viaje a `esperando_puerto`.

    Es una palanca de reduccion de costo: cada ack ahorra una llamada
    (~USD 0.20).
    """
    db.x("UPDATE trips SET status='esperando_puerto' WHERE id=?", (trip_id,))
    return {"ok": True}

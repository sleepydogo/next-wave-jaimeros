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


@router.get("/{driver_id}/trip")
def current_trip(driver_id: str):
    """El viaje activo del conductor, para la pantalla principal de la app."""
    trip = db.one(
        "SELECT * FROM trips WHERE driver_id=? AND status!='cerrado' ORDER BY created_at DESC LIMIT 1",
        (driver_id,))
    if not trip:
        return {"trip": None}
    calls = db.q("SELECT id,reason,status,ts FROM calls WHERE trip_id=? ORDER BY ts DESC LIMIT 5",
                 (trip["id"],))
    return {"trip": trip, "calls": calls}


@router.post("/ping")
async def ping(p: Ping):
    """La app manda posicion cada pocos segundos. Aca vive el detector."""
    await detector.process_ping(p.trip_id, {"lat": p.lat, "lon": p.lon,
                                            "speed": p.speed, "ts": time.time()})
    trip = db.one("SELECT status FROM trips WHERE id=?", (p.trip_id,))
    return {"ok": True, "status": trip["status"] if trip else None}


@router.post("/{trip_id}/ack")
def ack(trip_id: str):
    """Boton 'ya estoy listo' en la app: evita una llamada."""
    db.x("UPDATE trips SET status='esperando_puerto' WHERE id=?", (trip_id,))
    return {"ok": True}

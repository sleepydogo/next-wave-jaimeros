"""Endpoints que consume la app movil del conductor."""
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import bus, db, events, state
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

    En la demo el `driver_id` es `driver_01`.

    Los IDs tienen que cumplir el pattern del contrato de eventos
    (`^[A-Za-z0-9][A-Za-z0-9._:-]{5,127}$`, minimo 6 caracteres): el agente
    valida el payload y descarta lo que no matchee.
    """
    trip = db.one(
        "SELECT t.*, d.name AS driver_name, d.phone AS driver_phone FROM trips t "
        "JOIN drivers d ON d.id=t.driver_id "
        "WHERE t.driver_id=? AND t.status!='cerrado' ORDER BY t.created_at DESC LIMIT 1",
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

    El endpoint **solo encola** la posicion en Redis y vuelve: el detector la
    consume del otro lado. Por eso el `status` que devuelve es el **ultimo
    conocido**, y todavia no refleja este ping.
    """
    await state.push_ping(p.trip_id, {"lat": p.lat, "lon": p.lon,
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


# Los cuatro hitos que disparan una llamada. La app movil los muestra como
# botones para manejar la demo sin depender de que el GPS caiga justo.
DISPARADORES = {
    "llegada": (events.TRUCK_ARRIVED, "llego al puerto",
                lambda t: {"detail": "ingreso al geofence", "port_name": t["port_name"],
                           "distance_m": 0}),
    "desvio": (events.TRUCK_OFF_ROUTE, "se desvio de la ruta",
               lambda t: {"detail": "se desvio de la ruta al puerto", "desvio_m": 5200}),
    "parada": (events.TRUCK_STOPPED, "se detuvo en ruta",
               lambda t: {"detail": "parada no planificada", "seconds": 420}),
    "frenada": (events.TRUCK_SLOWDOWN, "bajo la velocidad de golpe",
                lambda t: {"detail": "caida abrupta de velocidad", "drop_pct": 78,
                           "previous_speed": 82.0, "current_speed": 18.0}),
}


@router.get("/triggers", summary="Hitos que la app puede disparar")
def triggers():
    """Los cuatro disparadores de llamada, para que la app arme los botones."""
    return [{"id": k, "titulo": v[1]} for k, v in DISPARADORES.items()]


@router.post("/{trip_id}/trigger/{hito}", summary="Disparar un hito a mano")
async def trigger(trip_id: str, hito: str):
    """Publica el evento como si lo hubiera detectado el GPS.

    Existe para la demo: deja provocar cada uno de los cuatro hitos desde la
    app, sin tener que esperar a que la posicion real caiga en el lugar justo.
    El payload que sale es identico al que arma el detector, asi que el agente
    no distingue si vino de aca o de un ping.
    """
    if hito not in DISPARADORES:
        raise HTTPException(400, f"hito desconocido: {hito}")
    trip = db.one("SELECT * FROM trips WHERE id=?", (trip_id,))
    if not trip:
        raise HTTPException(404, "no existe ese viaje")

    tipo, titulo, extra = DISPARADORES[hito]
    last = db.one("SELECT lat,lon,speed,ts FROM pings WHERE trip_id=? ORDER BY ts DESC LIMIT 1",
                  (trip_id,))
    # la llegada tiene que ser en el puerto; el resto, donde este el camion
    ping = ({"lat": trip["port_lat"], "lon": trip["port_lon"], "speed": 0, "ts": time.time()}
            if tipo == events.TRUCK_ARRIVED else
            {"lat": last["lat"] if last else trip["port_lat"],
             "lon": last["lon"] if last else trip["port_lon"],
             "speed": 0, "ts": time.time()})

    if tipo == events.TRUCK_ARRIVED:
        db.x("UPDATE trips SET status='en_puerto' WHERE id=?", (trip_id,))
    payload = await detector._event_payload(trip, ping, extra(trip))
    event_id = await bus.publish(tipo, payload)
    return {"ok": True, "hito": hito, "titulo": titulo, "evento": tipo, "event_id": event_id}

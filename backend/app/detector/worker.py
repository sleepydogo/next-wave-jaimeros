"""Consume pings de GPS desde Redis y publica eventos de negocio al bus."""
import asyncio
import logging

from .. import bus, db, events, state
from ..config import DETECCION_AUTOMATICA
from . import geocode, rules

log = logging.getLogger("detector")


async def loop():
    """El detector: consume la cola de pings de Redis, una por una.

    Se arranca en el lifespan de FastAPI. La API solo encola; toda la deteccion
    pasa por aca, asi el endpoint no espera a que se evaluen las reglas.
    """
    log.info("detector escuchando la cola %s", state.PING_QUEUE)
    while True:
        try:
            item = await state.pop_ping()
            if item:
                await process_ping(item["trip_id"], item["ping"])
        except asyncio.CancelledError:
            log.info("detector detenido")
            raise
        except Exception:
            log.exception("el detector fallo procesando un ping")


async def process_ping(trip_id, ping):
    """Llamado por la API cada vez que la app del conductor manda posicion."""
    trip = db.one("SELECT * FROM trips WHERE id=?", (trip_id,))
    if not trip or trip["status"] in ("cargando", "cerrado"):
        return

    await state.set_last(trip_id, ping)
    await state.push_window(trip_id, ping)
    db.x("INSERT INTO pings (trip_id,lat,lon,speed,ts) VALUES (?,?,?,?,?)",
         (trip_id, ping["lat"], ping["lon"], ping["speed"], ping["ts"]))
    window = await state.get_window(trip_id)

    if not DETECCION_AUTOMATICA:
        # la posicion se guarda igual (el mapa la usa), pero los eventos los
        # dispara la app con los botones
        return

    # 1) llegada al puerto
    is_in, dist = rules.arrived(ping, trip)
    if is_in and trip["status"] == "en_ruta":
        if await state.once(f"arrived:{trip_id}", ttl=3600):
            db.x("UPDATE trips SET status='en_puerto' WHERE id=?", (trip_id,))
            await bus.publish(events.TRUCK_ARRIVED, await _event_payload(trip, ping, {
                "detail": "ingreso al geofence", "port_name": trip["port_name"],
                "distance_m": round(dist)}))
        return

    # 2) parada no planificada en ruta
    if not is_in:
        is_stopped, span = rules.stopped(window)
        if is_stopped and await state.once(f"stopped:{trip_id}", ttl=900):
            await bus.publish(events.TRUCK_STOPPED, await _event_payload(trip, ping, {
                "detail": "parada no planificada", "seconds": round(span)}))
            return

        # 3) se salio del corredor hacia el puerto
        origen = db.one("SELECT lat,lon FROM pings WHERE trip_id=? ORDER BY ts ASC LIMIT 1",
                        (trip_id,))
        fuera, desvio = rules.off_route(ping, trip, origen)
        if fuera and await state.once(f"offroute:{trip_id}", ttl=900):
            await bus.publish(events.TRUCK_OFF_ROUTE, await _event_payload(trip, ping, {
                "detail": "se desvio de la ruta al puerto", "desvio_m": round(desvio)}))
            return

        # 4) caida abrupta de velocidad
        is_slow, drop = rules.slowdown(window)
        if is_slow and await state.once(f"slowdown:{trip_id}", ttl=600):
            await bus.publish(events.TRUCK_SLOWDOWN, await _event_payload(trip, ping, {
                "detail": "caida abrupta de velocidad", "drop_pct": round(drop * 100),
                "previous_speed": window[1]["speed"], "current_speed": window[0]["speed"]}))


async def _event_payload(trip, ping, extra):
    """Arma el payload enriquecido que consume el agente. El agente no toca la DB."""
    driver = db.one("SELECT * FROM drivers WHERE id=?", (trip["driver_id"],)) or {}
    # en el puerto ya sabemos como se llama; en ruta hay que preguntarle a Google
    location = trip["port_name"] if extra.get("port_name") else await geocode.label(
        ping["lat"], ping["lon"])
    return {"trip_id": trip["id"], "worker_id": driver.get("id", trip["driver_id"]),
            "worker_name": driver.get("name", "Conductor"),
            "worker_phone": driver.get("phone", "+5491100000000"),
            "lat": ping["lat"], "lon": ping["lon"],
            "location_label": location,
            "container": trip["container"], **extra}

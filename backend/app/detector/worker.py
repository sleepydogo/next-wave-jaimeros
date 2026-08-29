"""Consume pings de GPS desde Redis y publica eventos de negocio al bus."""
import asyncio
import logging

from .. import bus, db, events, state
from . import rules

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

    # 1) llegada al puerto
    is_in, dist = rules.arrived(ping, trip)
    if is_in and trip["status"] == "en_ruta":
        if await state.once(f"arrived:{trip_id}", ttl=3600):
            db.x("UPDATE trips SET status='en_puerto' WHERE id=?", (trip_id,))
            await bus.publish(events.TRUCK_ARRIVED,
                              {"trip_id": trip_id, "distance_m": round(dist)})
        return

    # 2) parada no planificada en ruta
    if not is_in:
        is_stopped, span = rules.stopped(window)
        if is_stopped and await state.once(f"stopped:{trip_id}", ttl=900):
            await bus.publish(events.TRUCK_STOPPED,
                              {"trip_id": trip_id, "seconds": round(span),
                               "lat": ping["lat"], "lon": ping["lon"]})
            return

        # 3) caida abrupta de velocidad
        is_slow, drop = rules.slowdown(window)
        if is_slow and await state.once(f"slowdown:{trip_id}", ttl=600):
            await bus.publish(events.TRUCK_SLOWDOWN,
                              {"trip_id": trip_id, "drop_pct": round(drop * 100),
                               "lat": ping["lat"], "lon": ping["lon"]})

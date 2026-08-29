"""Consume pings de GPS y publica eventos de negocio al bus."""
import logging

from .. import bus, db, events, state
from . import rules

log = logging.getLogger("detector")


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
            await bus.publish(events.TRUCK_ARRIVED, _event_payload(trip, ping, {
                "detail": "ingreso al geofence", "port_name": trip["port_name"],
                "distance_m": round(dist)}))
        return

    # 2) parada no planificada en ruta
    if not is_in:
        is_stopped, span = rules.stopped(window)
        if is_stopped and await state.once(f"stopped:{trip_id}", ttl=900):
            await bus.publish(events.TRUCK_STOPPED, _event_payload(trip, ping, {
                "detail": "parada no planificada", "seconds": round(span)}))
            return

        # 3) caida abrupta de velocidad
        is_slow, drop = rules.slowdown(window)
        if is_slow and await state.once(f"slowdown:{trip_id}", ttl=600):
            await bus.publish(events.TRUCK_SLOWDOWN, _event_payload(trip, ping, {
                "detail": "caida abrupta de velocidad", "drop_pct": round(drop * 100)}))


def _event_payload(trip, ping, extra):
    driver = db.one("SELECT * FROM drivers WHERE id=?", (trip["driver_id"],)) or {}
    return {"trip_id": trip["id"], "worker_id": driver.get("id", trip["driver_id"]),
            "worker_name": driver.get("name", "Conductor"),
            "worker_phone": driver.get("phone", "+5491100000000"),
            "lat": ping["lat"], "lon": ping["lon"],
            "location_label": trip["port_name"] if extra.get("port_name") else "Ruta en curso",
            "container": trip["container"], **extra}

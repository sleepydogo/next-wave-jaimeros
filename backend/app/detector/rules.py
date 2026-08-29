"""Reglas de deteccion. Los thresholds viven en SQLite y los ajusta el cron agent."""
import math
import time

from .. import db

DEFAULTS = {
    "geofence_radius_m": 800.0,    # radio del puerto para considerar "llego"
    "stop_speed_kmh": 3.0,         # debajo de esto = detenido
    "stop_min_seconds": 120.0,     # cuanto tiempo detenido para alertar
    "slowdown_drop_pct": 0.6,      # caida de velocidad >60% = frenada anormal
    "slowdown_min_kmh": 40.0,      # solo si venia rapido
}


def seed():
    for k, v in DEFAULTS.items():
        db.x("INSERT OR IGNORE INTO thresholds (key,value,updated_at,reason) VALUES (?,?,?,?)",
             (k, v, time.time(), "default"))


def th(key):
    row = db.one("SELECT value FROM thresholds WHERE key=?", (key,))
    return row["value"] if row else DEFAULTS[key]


def set_th(key, value, reason):
    db.x("INSERT INTO thresholds (key,value,updated_at,reason) VALUES (?,?,?,?) "
         "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at, reason=excluded.reason",
         (key, float(value), time.time(), reason))


def distance_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def arrived(ping, trip):
    """True si el camion esta dentro del geofence del puerto."""
    d = distance_m(ping["lat"], ping["lon"], trip["port_lat"], trip["port_lon"])
    return d <= th("geofence_radius_m"), d


def stopped(window):
    """True si los pings MAS RECIENTES vienen consecutivamente por debajo de la
    velocidad minima y esa racha cubre al menos stop_min_seconds.
    window viene ordenada del mas nuevo al mas viejo."""
    limit = th("stop_speed_kmh")
    run = []
    for p in window:
        if p["speed"] >= limit:
            break
        run.append(p)
    if len(run) < 3:
        return False, 0
    span = run[0]["ts"] - run[-1]["ts"]
    return span >= th("stop_min_seconds"), span


def slowdown(window):
    """Caida abrupta entre los dos ultimos pings."""
    if len(window) < 2:
        return False, 0
    now, prev = window[0]["speed"], window[1]["speed"]
    if prev < th("slowdown_min_kmh"):
        return False, 0
    drop = (prev - now) / prev if prev else 0
    return drop >= th("slowdown_drop_pct"), drop

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
    "corridor_m": 3000.0,          # cuanto se puede alejar de la recta al puerto
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


def off_route(ping, trip, origen):
    """Distancia del camion al corredor que va del origen al puerto.

    No tenemos la ruta real del viaje, asi que usamos la recta entre donde
    arranco y el puerto, con un ancho tolerante. Alcanza para distinguir "esta
    dando una vuelta por la ciudad" de "se fue para otro lado".

    `origen` es el primer ping del viaje; sin el no se puede evaluar.
    """
    if not origen:
        return False, 0.0
    d = _dist_a_segmento(ping["lat"], ping["lon"], origen["lat"], origen["lon"],
                         trip["port_lat"], trip["port_lon"])
    return d > th("corridor_m"), d


def _dist_a_segmento(plat, plon, alat, alon, blat, blon):
    """Distancia de un punto al segmento A-B, en metros.

    A esta escala la Tierra es plana sin que se note: proyectamos a metros y
    resolvemos en el plano.
    """
    mlat = math.radians((alat + blat) / 2)
    kx = 111320 * math.cos(mlat)   # metros por grado de longitud
    ky = 110540                    # metros por grado de latitud
    ax, ay = 0.0, 0.0
    bx, by = (blon - alon) * kx, (blat - alat) * ky
    px, py = (plon - alon) * kx, (plat - alat) * ky
    largo2 = bx * bx + by * by
    if largo2 == 0:
        return math.hypot(px, py)
    # t = donde cae la proyeccion del punto sobre el segmento, recortado a [0,1]
    t = max(0.0, min(1.0, (px * bx + py * by) / largo2))
    return math.hypot(px - t * bx, py - t * by)

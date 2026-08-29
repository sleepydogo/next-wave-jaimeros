"""Endpoints de la web de metricas / monitorista."""
import json
import time
import uuid

from fastapi import APIRouter

from .. import bus, costs, db, events
from ..detector import rules
from ..jobs import threshold_agent

router = APIRouter(prefix="/ops", tags=["ops"])

DEMO_PORT = {"name": "Puerto Buenos Aires - Terminal 4", "lat": -34.5745, "lon": -58.3660}


def _json(rows, *fields):
    for r in rows:
        for f in fields:
            r[f] = json.loads(r[f]) if r.get(f) else {}
    return rows


@router.get("/trips")
def trips():
    rows = db.q("SELECT t.*, d.name AS driver_name, d.phone FROM trips t "
                "JOIN drivers d ON d.id=t.driver_id ORDER BY t.created_at DESC")
    for t in rows:
        last = db.one("SELECT lat,lon,speed,ts FROM pings WHERE trip_id=? ORDER BY ts DESC LIMIT 1",
                      (t["id"],))
        t["last_ping"] = last
    return rows


@router.get("/trips/{trip_id}")
def trip_detail(trip_id: str):
    return {
        "trip": db.one("SELECT * FROM trips WHERE id=?", (trip_id,)),
        "pings": db.q("SELECT * FROM pings WHERE trip_id=? ORDER BY ts DESC LIMIT 100", (trip_id,)),
        "events": db.q("SELECT * FROM events WHERE trip_id=? ORDER BY ts DESC LIMIT 50", (trip_id,)),
        "calls": _json(db.q("SELECT * FROM calls WHERE trip_id=? ORDER BY ts DESC", (trip_id,)),
                       "outcome", "voice"),
    }


@router.get("/calls")
def calls():
    return _json(db.q("SELECT * FROM calls ORDER BY ts DESC LIMIT 50"), "outcome", "voice")


@router.get("/alerts")
def alerts():
    return db.q("SELECT * FROM alerts ORDER BY ts DESC LIMIT 50")


@router.get("/thresholds")
def thresholds():
    return db.q("SELECT * FROM thresholds ORDER BY key")


@router.post("/thresholds/tune")
async def tune():
    """Dispara el cron agent a mano (para mostrarlo en la demo)."""
    return {"applied": await threshold_agent.run_once()}


@router.post("/thresholds/{key}")
def set_threshold(key: str, value: float):
    """Setter manual. Lo usa el simulador para comprimir los tiempos en la demo.
    Declarado despues de /tune a proposito: si no, {key} se comeria esa ruta."""
    rules.set_th(key, value, "manual")
    return {"ok": True, "key": key, "value": value}


@router.post("/trips/{trip_id}/port-ready")
async def port_ready(trip_id: str):
    """El monitorista (o el sistema del puerto) habilita la carga."""
    await bus.publish(events.PORT_READY, {"trip_id": trip_id})
    return {"ok": True}


@router.get("/metrics")
def metrics():
    """KPIs + el contador de costos que se muestra en vivo."""
    done = db.q("SELECT duration_s, cost_usd FROM calls WHERE status='done'")
    total_cost = round(sum(c["cost_usd"] or 0 for c in done), 4)
    total_min = sum((c["duration_s"] or 0) for c in done) / 60
    # 1 llamada del agente = 1 evento que antes gestionaba el monitorista a mano
    eventos = len(done)
    human = costs.human_cost(eventos)
    voices = _json(db.q("SELECT voice FROM calls WHERE voice IS NOT NULL"), "voice")
    risks = [v["voice"].get("risk", 0) for v in voices if v["voice"]]
    return {
        "trips_activos": db.one("SELECT COUNT(*) c FROM trips WHERE status!='cerrado'")["c"],
        "llamadas": eventos,
        "alertas": db.one("SELECT COUNT(*) c FROM alerts")["c"],
        "minutos_llamada": round(total_min, 2),
        "costo_agente_usd": total_cost,
        "costo_agente_por_evento": round(total_cost / eventos, 4) if eventos else 0,
        "costo_humano_equivalente_usd": human,
        "costo_humano_por_evento": costs.human_cost_per_event(),
        "ahorro_usd": round(human - total_cost, 4),
        "riesgo_promedio_conductores": round(sum(risks) / len(risks), 2) if risks else 0,
        "precios": costs.PRICES,
    }


@router.post("/seed")
def seed():
    """Crea un conductor + viaje de demo. Idempotente-ish: siempre crea uno nuevo."""
    rules.seed()
    did = "d1"
    db.x("INSERT OR REPLACE INTO drivers (id,name,phone) VALUES (?,?,?)",
         (did, "Carlos Gimenez", "+5491100000000"))
    tid = uuid.uuid4().hex[:8]
    db.x("INSERT INTO trips (id,driver_id,container,port_name,port_lat,port_lon,status,created_at) "
         "VALUES (?,?,?,?,?,?,?,?)",
         (tid, did, "MSCU-4471820", DEMO_PORT["name"], DEMO_PORT["lat"], DEMO_PORT["lon"],
          "en_ruta", time.time()))
    return {"trip_id": tid, "driver_id": did, "port": DEMO_PORT}


@router.post("/reset")
def reset():
    for t in ("pings", "events", "calls", "alerts", "trips"):
        db.x(f"DELETE FROM {t}")
    return {"ok": True}

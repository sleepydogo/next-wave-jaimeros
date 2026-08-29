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


@router.get("/trips", summary="Lista de viajes")
def trips():
    """Todos los viajes con su conductor y la ultima posicion conocida.

    Es el endpoint del mapa / tabla principal del dashboard.

    `last_ping` puede ser `null` si el viaje todavia no recibio ninguna posicion.
    """
    rows = db.q("SELECT t.*, d.name AS driver_name, d.phone FROM trips t "
                "JOIN drivers d ON d.id=t.driver_id ORDER BY t.created_at DESC")
    for t in rows:
        last = db.one("SELECT lat,lon,speed,ts FROM pings WHERE trip_id=? ORDER BY ts DESC LIMIT 1",
                      (t["id"],))
        t["last_ping"] = last
    return rows


@router.get("/trips/{trip_id}", summary="Detalle de un viaje")
def trip_detail(trip_id: str):
    """Todo lo que paso en un viaje: `{trip, pings, events, calls}`.

    - **pings**: ultimos 100, mas nuevo primero
    - **events**: ultimos 50. Es el timeline del viaje
    - **calls**: todas, con transcripcion, outcome y metricas de voz

    OJO — inconsistencia conocida: en `calls` los campos `outcome` y `voice`
    vienen parseados como objetos, pero en `events` el campo `payload` viene
    como **string JSON** y hay que hacerle `JSON.parse` en el front.
    """
    return {
        "trip": db.one("SELECT * FROM trips WHERE id=?", (trip_id,)),
        "pings": db.q("SELECT * FROM pings WHERE trip_id=? ORDER BY ts DESC LIMIT 100", (trip_id,)),
        "events": db.q("SELECT * FROM events WHERE trip_id=? ORDER BY ts DESC LIMIT 50", (trip_id,)),
        "calls": _json(db.q("SELECT * FROM calls WHERE trip_id=? ORDER BY ts DESC", (trip_id,)),
                       "outcome", "voice"),
    }


@router.get("/calls", summary="Llamadas con transcripcion y metricas de voz")
def calls():
    """Ultimas 50 llamadas, mas nueva primero.

    - **reason**: `arrival_check` | `load_authorized` | `emergency`
    - **status**: `ringing` | `done` | `failed`
    - **transcript**: la conversacion completa (AGENTE / CONDUCTOR)
    - **outcome**: `{available, eta_min, problem, needs_human}`
    - **voice**: `{stress, fatigue, clarity, notes, asr_confidence, latency_s,
      speech_rate_wps, risk}`

    `voice.risk` (0 a 1) es el que usa el dashboard para marcar conductores en
    rojo. Un riesgo >= 0.6 ya genero una alerta por su cuenta.

    ```json
    {
      "id": "05c55846af35", "reason": "arrival_check", "status": "done",
      "transcript": "AGENTE: Hola Carlos...\\nCONDUCTOR: Si, ya llegue...",
      "outcome": {"available": true, "eta_min": 10, "problem": null,
                  "needs_human": false},
      "voice": {"stress": 0.2, "fatigue": 0.1, "risk": 0.2,
                "asr_confidence": 0.88, "latency_s": 1.8},
      "duration_s": 42.0, "cost_usd": 0.2
    }
    ```
    """
    return _json(db.q("SELECT * FROM calls ORDER BY ts DESC LIMIT 50"), "outcome", "voice")


@router.get("/alerts", summary="Alertas")
def alerts():
    """Ultimas 50 alertas.

    - **severity**: `alta` | `media` | `baja`
    - **channels**: por donde salio, separado por coma

    El ruteo por severidad lo decide el dispatcher:
    alta -> email, whatsapp, dashboard / media -> email, dashboard /
    baja -> dashboard.
    """
    return db.q("SELECT * FROM alerts ORDER BY ts DESC LIMIT 50")


@router.get("/thresholds", summary="Thresholds actuales del detector")
def thresholds():
    """Los 5 thresholds que usa el detector, con quien los toco por ultima vez.

    El campo `reason` dice el origen: `default`, `manual`, o la explicacion que
    dejo el cron agent al ajustarlos.

    | key | default | que controla |
    |---|---|---|
    | `geofence_radius_m` | 800 | radio del puerto para considerar que llego |
    | `stop_speed_kmh` | 3 | debajo de esto se considera detenido |
    | `stop_min_seconds` | 120 | cuanto tiempo detenido para alertar |
    | `slowdown_drop_pct` | 0.6 | caida de velocidad considerada anormal |
    | `slowdown_min_kmh` | 40 | solo aplica si venia mas rapido que esto |
    """
    return db.q("SELECT * FROM thresholds ORDER BY key")


@router.post("/thresholds/tune", summary="Correr el cron agent a mano")
async def tune():
    """Dispara el agente que ajusta los thresholds, que si no corre solo cada 5 min.

    Mira las llamadas de emergencia ya cerradas: si el conductor dijo que no
    pasaba nada (`outcome.problem == null`) fue un **falso positivo**. Muchos
    falsos positivos -> afloja los thresholds. Ninguno -> puede apretarlos para
    detectar antes.

    Sin `OPENAI_API_KEY` cae a una heuristica simple. Nunca escribe un valor
    fuera de `BOUNDS`.

    Devuelve `{"applied": {...}}` con lo que efectivamente cambio. Vacio si
    todavia no habia feedback para aprender.
    """
    return {"applied": await threshold_agent.run_once()}


@router.post("/thresholds/{key}", summary="Setter manual de un threshold")
def set_threshold(key: str, value: float):
    """Pisa un threshold a mano. Pensado para comprimir los tiempos en la demo.

    Ejemplo tipico: `stop_min_seconds=8` para poder mostrar una parada en ruta
    sin esperar los 2 minutos reales.

    OJO de implementacion: esta ruta esta declarada **despues** de
    `/thresholds/tune` a proposito. Si no, el path param `{key}` se comeria esa
    ruta fija.
    """
    rules.set_th(key, value, "manual")
    return {"ok": True, "key": key, "value": value}


@router.post("/trips/{trip_id}/port-ready", summary="El puerto habilita la carga")
async def port_ready(trip_id: str):
    """El monitorista (o el sistema del puerto) habilita la carga del contenedor.

    Publica `port.ready` en el bus: el viaje pasa a `habilitado` y el agente
    llama al conductor con `reason=load_authorized` para avisarle que puede
    pasar a cargar.

    Hoy es un boton manual. La integracion real con el sistema del puerto esta
    pendiente.
    """
    await bus.publish(events.PORT_READY, {"trip_id": trip_id})
    return {"ok": True}


@router.get("/metrics", summary="KPIs y contador de costos en vivo")
def metrics():
    """El contador de costos de la demo: agente vs. monitorista humano.

    La unidad de comparacion es el **evento gestionado** (una llegada, una
    habilitacion, una emergencia), no el minuto de llamada: el monitorista no
    gasta el tiempo hablando, lo gasta mirando pantallas y reintentando.

    - `costo_agente_por_evento`: **medido de verdad** (Twilio + ASR + tokens de
      cada llamada que ocurrio), no estimado
    - `costo_humano_por_evento`: 6 min de monitorista a USD 6/hora
    - `precios`: todos los parametros del modelo, pisables por env

    OJO: los precios por defecto son estimaciones **sin verificar** contra el
    pricing oficial de Twilio y OpenAI.
    """
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


@router.post("/seed", summary="Crear conductor + viaje de demo")
def seed():
    """Arma el escenario de demo y siembra los thresholds por defecto.

    Crea el conductor `d1` (Carlos Gimenez) y un viaje nuevo en estado `en_ruta`
    hacia Puerto Buenos Aires Terminal 4 (-34.5745, -58.3660).

    Devuelve `{trip_id, driver_id, port}`. **Crea un viaje nuevo cada vez que se
    lo llama.**

    Es el primer request a correr para probar cualquier otra cosa.
    """
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


@router.post("/reset", summary="Limpiar los datos de la demo")
def reset():
    """Vacia `pings`, `events`, `calls`, `alerts` y `trips`.

    No toca `drivers` ni `thresholds`.
    """
    for t in ("pings", "events", "calls", "alerts", "trips"):
        db.x(f"DELETE FROM {t}")
    return {"ok": True}

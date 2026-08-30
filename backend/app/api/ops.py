"""Endpoints de la web de metricas / monitorista."""
import json
import time
import uuid

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import bus, costs, db, events, state
from ..config import DEMO_WORKER_PHONE
from ..detector import rules, ruta
from ..jobs import threshold_agent

router = APIRouter(prefix="/ops", tags=["ops"])

DEMO_PORT = {"name": "Puerto Buenos Aires - Terminal 4", "lat": -34.5745, "lon": -58.3660}


def _json(rows, *fields):
    for r in rows:
        for f in fields:
            r[f] = json.loads(r[f]) if r.get(f) else {}
        if "id" in r and "audio_path" in r:
            # el front no ve el filesystem: le damos una url servible
            r["audio_url"] = f"/ops/calls/{r['id']}/audio" if r["audio_path"] else None
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
      "transcript": "AGENTE: Hola Tomas...\\nCONDUCTOR: Si, ya llegue...",
      "outcome": {"available": true, "eta_min": 10, "problem": null,
                  "needs_human": false},
      "voice": {"stress": 0.2, "fatigue": 0.1, "risk": 0.2,
                "asr_confidence": 0.88, "latency_s": 1.8},
      "duration_s": 42.0, "cost_usd": 0.2
    }
    ```
    """
    return _json(db.q("SELECT * FROM calls ORDER BY ts DESC LIMIT 50"), "outcome", "voice")


# El origen del viaje de demo: desde ahi arranca la ruta hasta el puerto.
ORIGEN_DEMO = (-34.7300, -58.2600)   # Avellaneda / acceso sudeste


@router.get("/trips/{trip_id}/ruta", summary="Ruta real del viaje con sus hitos")
async def ruta_del_viaje(trip_id: str):
    """La ruta que maneja el camion, y donde cae cada alerta sobre ella.

    Los hitos de la demo se disparan con botones, asi que todos comparten la
    misma coordenada. Aca se reparten a lo largo del recorrido en orden
    cronologico, uno cada ~3 km, que es como se verian en un viaje real.
    """
    trip = db.one("SELECT * FROM trips WHERE id=?", (trip_id,))
    if not trip:
        raise HTTPException(404, "no existe ese viaje")

    primer_ping = db.one("SELECT lat,lon FROM pings WHERE trip_id=? ORDER BY ts ASC LIMIT 1",
                         (trip_id,))
    origen = ((primer_ping["lat"], primer_ping["lon"]) if primer_ping else ORIGEN_DEMO)
    puntos, estado = await ruta.calcular(origen, (trip["port_lat"], trip["port_lon"]))

    alertas = db.q("SELECT * FROM alerts WHERE trip_id=? ORDER BY ts ASC", (trip_id,))
    posiciones = ruta.repartir(puntos, len(alertas))
    hitos = [{**a, **pos} for a, pos in zip(alertas, posiciones)]

    return {
        "estado": estado,
        "ruta": [{"lat": p[0], "lng": p[1]} for p in puntos],
        "origen": {"lat": origen[0], "lng": origen[1]},
        "destino": {"lat": trip["port_lat"], "lng": trip["port_lon"]},
        "hitos": hitos,
    }


@router.get("/calls/{call_id}/audio", summary="Audio de la llamada")
def call_audio(call_id: str):
    """El wav de la llamada, con las dos voces mezcladas.

    Lo graba el propio puente de audio mientras habla el agente con el
    conductor, asi que existe tanto para las llamadas por telefono como para
    las pruebas desde el navegador.
    """
    row = db.one("SELECT audio_path FROM calls WHERE id=?", (call_id,))
    if not row or not row["audio_path"] or not os.path.exists(row["audio_path"]):
        raise HTTPException(404, "esa llamada no tiene audio grabado")
    return FileResponse(row["audio_path"], media_type="audio/wav",
                        filename=f"llamada-{call_id}.wav")


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


@router.post("/alerts/{alert_id}/resolve", summary="Marcar una alerta como resuelta")
def resolver_alerta(alert_id: int):
    """El monitorista la atendio. Queda registrado cuando."""
    if not db.one("SELECT id FROM alerts WHERE id=?", (alert_id,)):
        raise HTTPException(404, "no existe esa alerta")
    db.x("UPDATE alerts SET resuelta_el=? WHERE id=?", (time.time(), alert_id))
    return {"ok": True, "id": alert_id}


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
    trip = db.one("SELECT * FROM trips WHERE id=?", (trip_id,))
    driver = db.one("SELECT * FROM drivers WHERE id=?", (trip["driver_id"],)) if trip else None
    if not trip or not driver:
        return {"ok": False, "error": "viaje no encontrado"}
    await bus.publish(events.PORT_READY, {
        "trip_id": trip_id, "worker_id": driver["id"], "worker_name": driver["name"],
        "worker_phone": driver["phone"], "lat": trip["port_lat"], "lon": trip["port_lon"],
        "location_label": trip["port_name"], "detail": "carga habilitada", "container": trip["container"],
        "port_name": trip["port_name"],
    })
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

    Crea el conductor `driver_01` (Tomas Schattmann) y un viaje nuevo en estado `en_ruta`
    hacia Puerto Buenos Aires Terminal 4 (-34.5745, -58.3660).

    Devuelve `{trip_id, driver_id, port}`. **Crea un viaje nuevo cada vez que se
    lo llama.**

    Es el primer request a correr para probar cualquier otra cosa.
    """
    rules.seed()
    did = "driver_01"
    db.x("INSERT OR REPLACE INTO drivers (id,name,phone) VALUES (?,?,?)",
         (did, "Tomas Schattmann", DEMO_WORKER_PHONE))
    # idempotente: si el conductor ya tiene un viaje abierto se reusa. Antes
    # creaba uno nuevo en cada arranque y se acumulaban viajes fantasma.
    abierto = db.one("SELECT id FROM trips WHERE driver_id=? AND status!='cerrado' "
                     "ORDER BY created_at DESC LIMIT 1", (did,))
    if abierto:
        return {"trip_id": abierto["id"], "driver_id": did, "port": DEMO_PORT,
                "reusado": True}

    tid = uuid.uuid4().hex[:8]
    db.x("INSERT INTO trips (id,driver_id,container,port_name,port_lat,port_lon,status,created_at) "
         "VALUES (?,?,?,?,?,?,?,?)",
         (tid, did, "MSCU-4471820", DEMO_PORT["name"], DEMO_PORT["lat"], DEMO_PORT["lon"],
          "en_ruta", time.time()))
    return {"trip_id": tid, "driver_id": did, "port": DEMO_PORT, "reusado": False}


@router.post("/reset", summary="Limpiar los datos de la demo")
async def reset():
    """Vacia `pings`, `events`, `calls`, `alerts` y `trips`.

    No toca `drivers` ni `thresholds`.
    """
    for t in ("pings", "events", "calls", "alerts", "trips"):
        db.x(f"DELETE FROM {t}")
    # Redis tambien: la cola de pings sobrevive al reinicio y el detector la
    # consumiria de golpe al arrancar, disparando llamadas viejas.
    borradas = await state.limpiar()
    return {"ok": True, "claves_redis_borradas": borradas}

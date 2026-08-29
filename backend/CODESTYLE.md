# Estilo de codigo — backend NextWave

Python 3.11+, FastAPI, SQLite, agentes que reaccionan a eventos.
Este archivo es la fuente de verdad para escribir codigo nuevo. Seguir el
estilo que ya esta en `app/`, no imponer otro.

---

## Principios

- **Funciones, no clases.** Un modulo = un rol. Las unicas clases son
  `BaseModel` de Pydantic en los endpoints.
- **Corto y directo.** Si cabe en una linea sin mentir, va en una linea.
- **Un proceso, muchos workers.** Detector, agente, dispatcher y cron viven
  como tasks de asyncio dentro de FastAPI. No inventar microservicios.
- **El bus es el contrato.** Nadie llama al agente ni al dispatcher en
  forma directa: publica un evento y el handler reacciona.
- **SQLite es la verdad persistente.** Redis es memoria volatil (ultimo
  ping, ventanas, locks, sesion de llamada). No mezclar.
- **No gastar plata en dev.** Toda integracion externa (Twilio, OpenAI,
  WhatsApp) tiene fallback o modo simulado. El default es no llamar APIs
  de pago.

---

## Python

### Naming

| Cosa | Estilo | Ejemplo |
|---|---|---|
| Modulos, funciones, variables | `snake_case` | `process_ping`, `trip_id` |
| Constantes | `UPPER_SNAKE` | `OPENAI_MODEL`, `SIM_REPLIES` |
| Helpers privados | `_prefijo` | `_ctx`, `_twiml`, `_send` |
| Eventos del bus | `dominio.accion` | `truck.arrived`, `call.finished` |
| Loggers | nombre corto del modulo | `logging.getLogger("brain")` |
| Routers | prefijo de recurso | `/driver`, `/ops`, `/twilio` |

Helpers de `db.py` se quedan cortos a proposito: `q`, `one`, `x`, `conn`.
No renombrarlos. En el resto de la app, nombres que se lean en voz alta.

### Imports

Tres bloques, en este orden, separados por una linea en blanco:

```python
import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from .. import bus, db, events
from ..config import OPENAI_API_KEY
```

- Stdlib → terceros → locales.
- Relativos (`from .. import db`) dentro de `app/`.
- Imports pesados o opcionales (Twilio, aio_pika) van **adentro** de la
  funcion que los usa, no al tope del modulo.
- Side-effect imports (registrar handlers del bus) se anotan:

```python
from .agent import worker as agent_worker  # noqa: F401  (registra handlers)
```

### Tipos

- Type hints en firmas publicas cuando aportan: endpoints, costos, helpers
  que devuelven XML/JSON con forma fija.
- No hace falta anotar todo. El codigo existente es en su mayoria sin
  hints y esta bien.
- Pydantic solo en el borde HTTP (`class Ping(BaseModel)`). Adentro, dicts.

```python
# bien — borde HTTP
class Ping(BaseModel):
    trip_id: str
    lat: float
    lon: float
    speed: float = 0.0

# bien — adentro del sistema
async def process_ping(trip_id, ping):
    ...
```

### Async

- `async def` si toca Redis, el bus, OpenAI, Twilio o `asyncio.sleep`.
- `def` si solo lee/escribe SQLite o arma una respuesta.
- Un endpoint puede ser sync aunque el resto del sistema sea async.
- Nunca `time.sleep` en el event loop. Usar `asyncio.sleep`.
- Tasks de fondo se crean en el `lifespan` de FastAPI, no en import time
  (salvo `asyncio.create_task` para una simulacion puntual, como en
  `caller.start`).

### Errores

- Catch estrecho. Si el catch es amplio, loguear con `log.exception(...)`
  y devolver un fallback seguro. No silenciar.
- Un handler del bus que explota no tumba a los demas: el bus ya envuelve
  cada handler en try/except. No duplicar esa red.
- El brain y el cron agent **siempre** tienen camino sin API key.

```python
# bien
try:
    res = await client.chat.completions.create(...)
    return json.loads(res.choices[0].message.content), tokens
except Exception:
    log.exception("brain fallo")
    return FALLBACK, (0, 0)

# mal
try:
    await algo()
except Exception:
    pass
```

### Logging

```python
log = logging.getLogger("agent")
log.info("llamada %s -> %s (%s)", call_id, phone, reason)
log.exception("handler %s fallo en %s", fn.__name__, event_type)
```

- Printf-style (`%s`), no f-strings en el mensaje del logger.
- `info` para el flujo normal, `warning` para canales simulados / alertas
  que no salieron, `exception` para fallos.
- El format global se setea una sola vez en `main.py`. No reconfigurarlo.

### Comentarios y docstrings

- Espanol, sin vueltas. Docstring de modulo arriba, de una o dos lineas,
  explicando el **rol** del archivo.
- Docstring de funcion solo si el nombre no alcanza, o para documentar
  el shape de entrada/salida (el brain, `turn`, `process_ping`).
- Comentarios de seccion (`# 1) llegada al puerto`) cuando hay una
  secuencia de reglas. No narrar lo obvio.

```python
"""El cerebro del agente de voz: decide que decir y lee metricas de la voz."""
```

### Formato

- Lineas ~100 caracteres. Quebrar un dict o un SQL largo esta bien;
  no forzar 79.
- Dicts compactos, keys en la misma linea cuando caben:

```python
session = {"trip_id": trip_id, "reason": reason, "ctx": ctx,
           "history": [{"role": "assistant", "content": opener}],
           "t0": time.time(), "last_ts": time.time()}
```

- Comillas dobles.
- Trailing comma solo si ayuda al diff de listas multilinea.
- No usar Black/ruff como excusa para reescribir archivos que no
  estas tocando.

---

## FastAPI

### App

- Una sola `FastAPI` en `app/main.py`.
- Routers por audiencia: `driver` (app movil), `ops` (dashboard),
  `twilio` (webhooks). No mezclar.
- Startup/shutdown va en `lifespan`: `db.init()`, `rules.seed()`,
  `bus.start()`, cron. Cancelar las tasks al apagar.

### Endpoints

- Prefijo + tags en el router. Paths en kebab o un solo recurso
  (`/trips/{trip_id}`, `/thresholds/tune`).
- GET devuelve dicts/listas. POST que dispara algo devuelve
  `{"ok": True, ...}`.
- Body de entrada = Pydantic. Query/path = tipos nativos de FastAPI.
- Un endpoint no implementa logica de deteccion ni de llamada: delega
  al worker (`detector.process_ping`, `bus.publish`, `caller.turn`).
- Orden de rutas: las literales (`/thresholds/tune`) **antes** que las
  parametricas (`/thresholds/{key}`). Si no, el path param se come la
  ruta fija. Dejar un comentario cuando el orden sea a proposito.

```python
router = APIRouter(prefix="/ops", tags=["ops"])

@router.post("/thresholds/tune")
async def tune():
    return {"applied": await threshold_agent.run_once()}

@router.post("/thresholds/{key}")
def set_threshold(key: str, value: float):
    """Declarado despues de /tune a proposito."""
    rules.set_th(key, value, "manual")
    return {"ok": True, "key": key, "value": value}
```

### Respuestas especiales

- TwiML se arma a mano y se devuelve con
  `Response(..., media_type="application/xml")`. No usar templates.
- Escapar el texto que va adentro de `<Say>` (`xml.sax.saxutils.escape`).

---

## SQLite

Todo el acceso pasa por `app/db.py`. Nadie abre un `sqlite3.connect`
por su cuenta.

```python
# leer muchos
db.q("SELECT * FROM calls WHERE trip_id=? ORDER BY ts DESC", (trip_id,))

# leer uno (None si no hay)
trip = db.one("SELECT * FROM trips WHERE id=?", (trip_id,))

# escribir
db.x("UPDATE trips SET status=? WHERE id=?", (status, trip_id))

# evento de negocio (queda en la tabla events)
db.log_event(trip_id, event_type, payload)
```

Reglas:

- SQL crudo, parametrizado con `?`. Nunca interpolar valores de usuario
  en el string. El unico `f-string` aceptable es un **nombre de tabla
  literal** controlado por nosotros (`DELETE FROM {t}` con `t` de una
  tupla fija).
- El esquema vive en la constante `SCHEMA` de `db.py`. `CREATE TABLE IF
  NOT EXISTS`. No hay migraciones todavia: si cambia el esquema, se
  discute con el equipo (el actual es borrador).
- `sqlite3.Row` → `dict`. Los JSON se guardan como `TEXT` y se
  serializan/deserializan en el caller (`json.dumps` / `json.loads`),
  no en `db.py`.
- Timestamps: `time.time()` (epoch float), columna `REAL`.
- IDs: `uuid.uuid4().hex` recortado (`[:8]` viajes, `[:12]` llamadas)
  o texto fijo de demo (`driver_01`). No usar AUTOINCREMENT salvo tablas de
  log (`pings`, `events`, `alerts`).
  **Minimo 6 caracteres**: todo ID que viaje en un evento tiene que cumplir
  el pattern del contrato (`^[A-Za-z0-9][A-Za-z0-9._:-]{5,127}$`), o el agente
  descarta el payload. Por eso el conductor de demo es `driver_01` y no `d1`.
- `init()` y `seed()` son idempotentes (`IF NOT EXISTS`,
  `INSERT OR IGNORE`).
- El path de la DB es **absoluto** (`config.DB_PATH`). No depende del cwd.

Columnas de estado se documentan con un comentario al lado:

```sql
status TEXT,            -- en_ruta | en_puerto | esperando_puerto | habilitado | cargando | cerrado
reason TEXT,            -- arrival_check | load_authorized | emergency
```

No introducir ORM.

---

## Agentes

Hay tres piezas de agente. No fusionarlas.

| Modulo | Rol | Habla con |
|---|---|---|
| `app/agent/worker.py` | decide **si** llamar y **por que** | bus → `caller.start` |
| `app/agent/caller.py` | ejecuta la llamada (Twilio o simulado) | Redis sesion, SQLite `calls`, `brain` |
| `app/agent/brain.py` | decide **que decir** y lee la voz | OpenAI |

Mas el cron: `app/jobs/threshold_agent.py` ajusta thresholds. Es otro
agente, no parte de la llamada.

### Contratos

- Razones de llamada: `arrival_check` | `load_authorized` | `emergency`.
  Si agregas una, hay que tocar `OPENERS`, `GOALS`, `SIM_REPLIES` y el
  cierre en `on_call_finished`. Los cuatro juntos.
- El brain **siempre** devuelve JSON con `{reply, done, outcome, voice}`.
  El caller no inventa otro shape. Si OpenAI falla o no hay key →
  `FALLBACK`.
- `caller.turn` es un turno. `caller.finish` cierra, calcula costo y
  publica `call.finished`. Nadie mas escribe el costo.
- Sesion de llamada en Redis (`call:{id}`, TTL 1h). Transcript y
  outcome final en SQLite.
- Prompts en espanol rioplatense, frases cortas (se leen por telefono).
  Maximo 2 preguntas. No inventar datos del viaje: van en el system
  message como JSON del `ctx`.
- `temperature` baja (0.2–0.3), `max_tokens` chico (~300),
  `response_format={"type": "json_object"}`.
- El cron agent nunca escribe un threshold fuera de `BOUNDS`. Clamp
  `max(lo, min(hi, valor))` antes de persistir.

```python
# bien — el worker solo orquesta
@bus.on(events.TRUCK_ARRIVED)
async def on_arrived(p):
    await caller.start(p["trip_id"], "arrival_check")

# mal — el worker no habla con OpenAI ni arma TwiML
@bus.on(events.TRUCK_ARRIVED)
async def on_arrived(p):
    res = await openai.chat.completions.create(...)
```

### Integraciones externas

- Credenciales solo desde `config.py` (env). Nunca hardcodear keys.
- `SIMULATE_CALLS=1` (default): no Twilio. El caller corre `_simulate`
  con `SIM_REPLIES` pasando igual por el brain.
- Cliente OpenAI: `AsyncOpenAI(...) if OPENAI_API_KEY else None`.
  Toda funcion que lo use checkea `if not client`.
- Twilio se importa local y solo en el camino real
  (`_twilio_dial`, WhatsApp del dispatcher).

---

## Bus de eventos

API unica, documentada en `app/bus.py`:

```python
@bus.on(events.TRUCK_ARRIVED)
async def handler(payload):
    ...

await bus.publish(events.TRUCK_ARRIVED, {"trip_id": trip_id, ...})
```

- Nombres de eventos: solo en `app/events.py`. No strings sueltos.
- Payload = dict plano. Siempre incluye `trip_id` si aplica (el bus lo
  usa para `log_event`).
- `publish` persiste el evento en SQLite **antes** de mandarlo a
  Redis/Rabbit. No saltear eso.
- Handlers async, rapidos. I/O pesado (Twilio) se dispara y se vuelve.
- Registrar el handler por import side-effect. El modulo se importa
  en `main.py` aunque nadie lo use.

Locks anti-spam: `await state.once(f"arrived:{trip_id}", ttl=3600)`
**antes** de publicar. Un evento = una llamada. Si agregas una
deteccion nueva, ponele su `once`.

---

## Config

- Todo env se lee en `app/config.py`. El resto de la app importa
  constantes, no llama `os.getenv`.
- Default seguro para demo: `SIMULATE_CALLS=1`, URLs locales, strings
  vacios para credenciales.
- Precios en `costs.py` (`P_VOICE_MIN`, etc.). No magia numerica en
  el caller ni en `/ops/metrics`.

---

## Que no hacer

- No agregar FastAPI, SQLAlchemy, Celery, LangChain ni frameworks de
  agentes. El stack es el que esta.
- No crear un cuarto lugar donde se decida "hay que llamar".
- No devolver TwiML desde `brain` ni prompts desde `caller`.
- No commitear `.env`, `*.db`, ni secrets.
- No "mejorar" el esquema de `db.py` de paso: es borrador del equipo.
- No reescribir un modulo para que quede mas pythonico. El estilo
  compacto es a proposito.

---

## Checklist rapido

1. ¿El cambio vive en el modulo del rol correcto?
2. ¿Si es un hecho de negocio, pasa por `bus.publish` + `events.py`?
3. ¿SQL parametrizado via `db.q` / `db.one` / `db.x`?
4. ¿El agente tiene fallback sin API key / sin Twilio?
5. ¿Hay `state.once` si esto puede dispararse muchas veces?
6. ¿El endpoint HTTP es flaco y delega?
7. ¿Logueaste el fallo y no lo tragaste?

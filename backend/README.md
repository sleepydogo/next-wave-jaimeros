# backend — NextWave

FastAPI + SQLite + Redis. Un solo proceso, con el detector, el agente, el
dispatcher y el cron corriendo adentro como tasks de asyncio.

Para escribir codigo acá: leer **[CODESTYLE.md](CODESTYLE.md)** primero.
Para probar los endpoints: **Swagger en <http://localhost:8000/docs>** — cada
endpoint documenta que dispara, y se prueban desde ahi con "Try it out".

---

## La idea en una frase

La app del conductor manda su posicion, el **detector** decide si eso es un
hecho de negocio (llego al puerto, se detuvo, freno de golpe), lo publica en un
**bus de eventos**, y del otro lado el **agente** llama al conductor por
telefono y el **dispatcher** manda las alertas.

## El flujo completo

```
   app movil                                             dashboard
       │                                                      ▲
       │ POST /driver/ping                          GET /ops/*│
       ▼                                                      │
  ┌─────────────┐    ping     ┌──────────┐                    │
  │ api/driver  │────────────>│ detector │                    │
  └─────────────┘             └────┬─────┘                    │
                                   │ evento                   │
                                   ▼                          │
                            ┌─────────────┐                   │
                            │     bus     │                   │
                            └──┬───────┬──┘                   │
                    ┌──────────┘       └──────────┐           │
                    ▼                             ▼           │
             ┌─────────────┐              ┌──────────────┐    │
             │agent/worker │              │  dispatcher  │    │
             │¿a quien     │              │ email/wpp    │    │
             │ llamo?      │              └──────────────┘    │
             └──────┬──────┘                                  │
                    ▼                                         │
             ┌─────────────┐   ┌──────────┐                   │
             │agent/caller │──>│  brain   │ OpenAI            │
             │Twilio o sim │<──│que decir │                   │
             └──────┬──────┘   └──────────┘                   │
                    │                                         │
                    └──────────> SQLite ──────────────────────┘

              jobs/threshold_agent (cada 5 min) ──> ajusta los
                                                    thresholds del detector
```

### Paso a paso, escenario "el camion llega al puerto"

1. La app hace `POST /driver/ping` con lat/lon/speed.
2. `detector/worker.py` guarda el ping, actualiza la ventana movil en Redis y
   evalua las reglas de `detector/rules.py`.
3. La distancia al puerto cae bajo `geofence_radius_m` → el viaje pasa a
   `en_puerto` y se publica **`truck.arrived`**.
4. `agent/worker.py` escucha ese evento y llama a `caller.start(trip_id,
   "arrival_check")`.
5. `agent/caller.py` marca por Twilio (o simula la conversacion si
   `SIMULATE_CALLS=1`). Cada turno pasa por `agent/brain.py`, que decide que
   decir y estima estres/fatiga de la voz.
6. Al cortar, `caller.finish` calcula el costo real y publica
   **`call.finished`**.
7. `agent/worker.py` cierra el ciclo: actualiza el estado del viaje y, si el
   riesgo de voz es alto, publica **`alert.raised`**.
8. `dispatcher/worker.py` saca esa alerta por email/WhatsApp segun severidad.

Despues el monitorista hace `POST /ops/trips/{id}/port-ready` → se publica
**`port.ready`** → segunda llamada avisando que puede pasar a cargar.

### Por que un bus y no llamadas directas

Nadie invoca al agente ni al dispatcher a mano: publican un evento y quien
tenga que reaccionar reacciona. Eso permite que el detector no sepa que existe
Twilio, y que agregar un canal de alerta no toque el detector.

Backend del bus: **Redis pub/sub** por defecto, **RabbitMQ** si se define
`RABBITMQ_URL`. Se cambia por env, no por codigo.

Todo `publish` persiste el evento en la tabla `events` **antes** de mandarlo al
bus, asi el timeline del dashboard no depende de que el broker este vivo.

---

## Modulos

| Archivo | Rol |
|---|---|
| `app/main.py` | la app FastAPI, arranca los workers en el `lifespan` |
| `app/config.py` | todo el env. Nadie mas llama `os.getenv` |
| `app/db.py` | esquema SQLite + helpers `q` / `one` / `x` |
| `app/state.py` | Redis: ultimo ping, ventana movil, locks anti-spam, sesion de llamada |
| `app/bus.py` | publish / subscribe, backend intercambiable |
| `app/events.py` | los nombres de los eventos. No hay strings sueltos |
| `app/costs.py` | modelo de costos |
| `app/detector/rules.py` | geofence, parada, frenada + lectura de thresholds |
| `app/detector/worker.py` | recibe pings, evalua reglas, publica eventos |
| `app/agent/worker.py` | decide **si** llamar y **por que** |
| `app/agent/caller.py` | ejecuta la llamada (Twilio o simulada) |
| `app/agent/brain.py` | decide **que decir** y lee la voz (OpenAI) |
| `app/dispatcher/worker.py` | alertas por email / WhatsApp |
| `app/jobs/threshold_agent.py` | cron que ajusta los thresholds del detector |
| `app/api/driver.py` | endpoints de la app movil |
| `app/api/ops.py` | endpoints del dashboard |
| `app/api/twilio_hooks.py` | TwiML de la conversacion |
| `sim/simulate_trip.py` | simulador de viaje para la demo |

Las tres piezas de agente **no se fusionan**: `worker` orquesta, `caller`
ejecuta, `brain` piensa. El cron de thresholds es un cuarto agente, aparte.

---

## Eventos

| Evento | Lo publica | Reacciona |
|---|---|---|
| `truck.arrived` | detector | agente → llamada `arrival_check` |
| `truck.stopped` | detector | agente → llamada `emergency` + alerta alta |
| `truck.slowdown` | detector | agente → llamada `emergency` + alerta media |
| `port.ready` | `POST /ops/.../port-ready` | agente → llamada `load_authorized` |
| `call.finished` | caller | agente → actualiza viaje, escala si hay riesgo |
| `alert.raised` | agente | dispatcher → email / WhatsApp |

`truck.harsh_event` esta declarado en `events.py` pero todavia no lo publica
nadie.

**Locks anti-spam.** Antes de publicar, el detector pide
`state.once(f"arrived:{trip_id}", ttl=3600)` en Redis. Un hecho = una llamada,
aunque lleguen 50 pings iguales. Toda deteccion nueva necesita el suyo.

---

## Estado: que vive donde

| | Donde | Por que |
|---|---|---|
| Ultimo ping, ventana movil de pings | Redis (TTL 1h) | volatil, alta frecuencia, solo lo usa el detector |
| Locks anti-spam | Redis (TTL) | expiran solos |
| Sesion de llamada en curso (historial) | Redis (`call:{id}`, TTL 1h) | vive lo que dura la llamada |
| Viajes, llamadas, eventos, alertas, thresholds | SQLite | es la verdad persistente |

No mezclar las dos cosas. Si algo tiene que sobrevivir a un reinicio, va a
SQLite.

### Tablas

`drivers`, `trips`, `pings`, `events`, `calls`, `thresholds`, `alerts`.
El detalle esta en la constante `SCHEMA` de `app/db.py`.

> **El esquema es un borrador y no esta acordado con el equipo.** Se esta
> discutiendo en la rama `design/db-schema`. Las preguntas abiertas (pings a
> SQLite o solo Redis, la maquina de estados de `trips.status`, si el puerto va
> en tabla aparte, si los thresholds deberian ser por puerto) estan en el README
> raiz. No construir encima sin cerrar eso.

---

## Endpoints

Documentacion completa, con ejemplos y el efecto de cada uno, en el
**Swagger: <http://localhost:8000/docs>**. La portada tiene el recorrido de
prueba paso a paso, y cada endpoint explica que evento dispara.

Los tres grupos estan separados por audiencia: `driver` (app movil), `ops`
(dashboard) y `twilio` (webhooks, devuelven XML).

Arrancar por `POST /ops/seed`, que devuelve el `trip_id` que necesita el resto.

| Metodo | Path | Que hace |
|---|---|---|
| `GET` | `/health` | ping de vida |
| `GET` | `/driver/{driver_id}/trip` | viaje activo + ultimas llamadas |
| `POST` | `/driver/ping` | posicion GPS. **Es el input del detector** |
| `POST` | `/driver/{trip_id}/ack` | "ya estoy listo", evita una llamada |
| `GET` | `/ops/trips` | viajes + conductor + ultimo ping |
| `GET` | `/ops/trips/{trip_id}` | pings, eventos y llamadas del viaje |
| `GET` | `/ops/calls` | llamadas con transcripcion, outcome y voz |
| `GET` | `/ops/alerts` | alertas |
| `GET` | `/ops/metrics` | KPIs + costo agente vs. humano |
| `POST` | `/ops/trips/{trip_id}/port-ready` | habilita la carga → 2da llamada |
| `GET` | `/ops/thresholds` | thresholds actuales del detector |
| `POST` | `/ops/thresholds/tune` | corre el cron agent a mano |
| `POST` | `/ops/thresholds/{key}?value=` | setter manual (para la demo) |
| `POST` | `/ops/seed` | crea conductor + viaje de demo |
| `POST` | `/ops/reset` | limpia viajes, pings, eventos, llamadas, alertas |
| `POST` | `/twilio/voice/{call_id}` | TwiML: arranque de la llamada |
| `POST` | `/twilio/gather/{call_id}` | TwiML: el conductor hablo |
| `POST` | `/twilio/status/{call_id}` | fin de llamada → calcula costo |

Tambien esta el Swagger en `http://localhost:8000/docs`.

**Inconsistencia conocida:** en `/ops/calls` los campos `outcome` y `voice`
vienen parseados como objetos, pero en `/ops/trips/{id}` el `payload` de cada
evento viene como string JSON. El front tiene que hacerle `JSON.parse`.

---

## Correr

```bash
brew services start redis

cd backend
uv venv --python 3.11 .venv
uv pip install fastapi 'uvicorn[standard]' redis httpx python-dotenv \
               twilio openai aio-pika python-multipart
cp ../.env.example ../.env
.venv/bin/uvicorn app.main:app --reload --port 8000
```

`SIMULATE_CALLS=1` es el default: **no llama a ninguna API que cobre.** La
conversacion se simula con `SIM_REPLIES` pero pasa igual por el brain, asi que
el flujo que se prueba es el real.

### Demo sin la app movil

```bash
.venv/bin/python -m sim.simulate_trip llegada    # llega al puerto -> 2 llamadas
.venv/bin/python -m sim.simulate_trip parada     # se detiene -> emergencia
.venv/bin/python -m sim.simulate_trip frenada    # caida de velocidad
```

### Llamadas reales

1. `SIMULATE_CALLS=0` + credenciales de Twilio y OpenAI en `.env`.
2. `ngrok http 8000` → esa URL va en `PUBLIC_URL`.
3. En Twilio, los webhooks son `/twilio/voice/{call_id}`,
   `/twilio/gather/{call_id}` y `/twilio/status/{call_id}`.

La conversacion usa `<Gather input="speech">` (Twilio transcribe, el brain
decide). No usa Media Streams ni la Realtime API: se eligio lo simple.

---

## Costos

`app/costs.py`. Los precios son **parametros por env**, no numeros magicos en
el codigo: `P_VOICE_MIN`, `P_ASR_REQ`, `P_LLM_IN`, `P_LLM_OUT`, `P_HUMAN_HOUR`,
`P_HUMAN_MIN_EVENT`.

`GET /ops/metrics` devuelve el costo **medido**, no estimado: se acumula lo que
cada llamada consumio de verdad.

> Los precios por defecto son estimaciones **sin verificar**. Hay que
> chequearlos contra el pricing oficial de Twilio y OpenAI antes de la demo:
> el minuto de voz a movil argentino varia bastante.

Palancas de reduccion ya implementadas: modo simulado en dev, locks anti-spam
(un evento = una llamada), `gpt-4o-mini` con maximo 2 preguntas por llamada, y
el boton de ack en la app que evita la llamada entera.

---

## Bugs conocidos

1. **Doble llamada por un mismo incidente.** Un frenazo de 65 a 0 km/h dispara
   primero `truck.slowdown` y despues `truck.stopped` → dos llamadas de
   emergencia por el mismo hecho. Falta deduplicar en `detector/worker.py`.
2. **"Camion detenido 0 min"** en la alerta cuando el simulador comprime
   `stop_min_seconds` a 8s: el redondeo a minutos da 0.
3. Sin `OPENAI_API_KEY` el brain devuelve `FALLBACK` con `needs_human=true`, y
   eso genera una alerta de riesgo en cada llamada. Es esperable pero ensucia
   la demo.
4. `POST /ops/seed` crea un viaje nuevo cada vez que se lo llama.

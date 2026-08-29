# NextWave — agente de voz para coordinación de carga en puertos

Hackathon Yuno x Nauta — challenge #4 "The Agent on the Line".

Automatiza el trabajo del **monitorista**: hoy una persona mira la posición del
camión en una PC, llama al conductor cuando llega al puerto para ver si está
disponible, y lo vuelve a llamar cuando el puerto habilita la carga. El agente
hace esas llamadas solo, detecta eventos anormales en ruta (paradas, frenadas) y
mide el estado de la voz del conductor.

---

## Nota para el equipo

Se pidió **solamente la estructura de carpetas** para arrancar por la base de
datos. En vez de eso se generó el backend completo de una sola vez, sin discutir
el esquema de datos ni las decisiones de diseño con el equipo. Fue un error de
scope: se saltearon las decisiones que eran del equipo y se llegó a código
corriendo antes de acordar el modelo. Disculpas.

**Nada de esto está commiteado.** El esquema de datos en `backend/app/db.py` es
un borrador unilateral y debe revisarse (o tirarse) antes de construir encima.
Ver "Decisiones pendientes" al final.

---

## Estado actual

### Hecho y verificado corriendo

| Pieza | Estado |
|---|---|
| Backend FastAPI + SQLite + Redis | funciona |
| Bus de eventos (Redis pub/sub; RabbitMQ opcional) | funciona |
| Detector: geofence de llegada, parada en ruta, frenada brusca | funciona |
| Agente de voz (modo simulado, sin gastar Twilio) | funciona |
| Agente de voz (modo real Twilio + OpenAI) | **sin probar** — falta número y ngrok |
| Dispatcher de alertas (email/WhatsApp) | solo loguea + guarda en DB |
| Cron agent que ajusta thresholds | funciona con heurística; con LLM sin probar |
| Contador de costos en vivo | funciona |
| Simulador de viaje para la demo | funciona |

Escenarios corridos end-to-end:

- **llegada**: camión entra al geofence → llamada al conductor → el puerto
  habilita → segunda llamada. Los 6 eventos quedan en la DB.
- **parada**: camión se detiene en ruta → emergencia → llamada + alerta.

### No existe todavía

- `web/` — dashboard de métricas en React. Carpeta vacía.
- `mobile/` — app del conductor en Expo SDK 54. Carpeta vacía.
- `docs/COSTS.md` — el esquema de costos detallado que pide el challenge.
  El *modelo* está implementado en `backend/app/costs.py`, pero el documento
  con la proyección a escala no está escrito.
- Integración con el sistema del puerto/depósito (hoy es un botón manual).

---

## Cómo correr

```bash
# 1. Redis
brew services start redis

# 2. Backend
cd backend
uv venv --python 3.11 .venv
uv pip install fastapi 'uvicorn[standard]' redis httpx python-dotenv \
                twilio openai aio-pika python-multipart
cp ../.env.example ../.env          # SIMULATE_CALLS=1 por defecto: no gasta plata
.venv/bin/uvicorn app.main:app --reload --port 8000

# 3. Demo (en otra terminal)
cd backend
.venv/bin/python -m sim.simulate_trip llegada    # llegada al puerto -> 2 llamadas
.venv/bin/python -m sim.simulate_trip parada     # parada en ruta -> emergencia
.venv/bin/python -m sim.simulate_trip frenada    # caída de velocidad
```

Ver resultados: `curl localhost:8000/ops/metrics`, `/ops/calls`, `/ops/alerts`.

### Para llamadas reales

1. `SIMULATE_CALLS=0` y credenciales de Twilio + OpenAI en `.env`.
2. `ngrok http 8000` → poner la URL en `PUBLIC_URL`.
3. Configurar el número de Twilio. Los webhooks son `/twilio/voice/{call_id}`,
   `/twilio/gather/{call_id}`, `/twilio/status/{call_id}`.

---

## Arquitectura

```
app móvil ──ping GPS──> /driver/ping ──> detector ──evento──> bus
                                                               │
                                          ┌────────────────────┼──────────────┐
                                          ▼                    ▼              ▼
                                    agent worker         dispatcher     (cron agent
                                          │              email/WhatsApp   ajusta
                                     Twilio + OpenAI                     thresholds)
                                          │
                                    /twilio/* webhooks ──> SQLite ──> /ops/* ──> dashboard
```

Corre todo en **un solo proceso** FastAPI, con detector/agente/dispatcher/cron
como tasks de asyncio en módulos separados. Se decidió así por las 24hs; los
módulos están separados para poder partirlos en servicios después.

El bus usa **Redis pub/sub** por defecto y **RabbitMQ** si se define
`RABBITMQ_URL` — Docker estaba apagado durante el desarrollo.

### Mapa de archivos

```
backend/app/
  config.py              env + rutas
  db.py                  esquema SQLite  <-- BORRADOR, revisar
  state.py               memoria volátil en Redis (último ping, ventanas, locks)
  bus.py                 bus de eventos, backend intercambiable
  events.py              nombres de eventos
  costs.py               modelo de costos
  main.py                app FastAPI + arranque de workers
  detector/rules.py      geofence, parada, frenada + thresholds
  detector/worker.py     consume pings, publica eventos
  agent/brain.py         OpenAI: qué decir + métricas de voz
  agent/caller.py        Twilio outbound + modo simulado
  agent/worker.py        evento -> a quién llamar
  dispatcher/worker.py   alertas por email/WhatsApp
  jobs/threshold_agent.py  cron que ajusta thresholds según falsos positivos
  api/driver.py          endpoints de la app móvil
  api/ops.py             endpoints del dashboard
  api/twilio_hooks.py    TwiML de la conversación
backend/sim/simulate_trip.py   simulador de viaje para la demo
```

---

## Modelo de costos

Está en `backend/app/costs.py`. La unidad de comparación es el **evento
gestionado** (una llegada, una habilitación de carga, una emergencia), no el
minuto de llamada: el monitorista no gasta el tiempo hablando, lo gasta mirando
pantallas y reintentando llamadas.

Medido en la corrida real del escenario "parada":

| | por evento |
|---|---|
| Agente | **USD 0.20** |
| Monitorista humano | **USD 0.60** |

Costo del agente por llamada = minuto iniciado de Twilio (0.18) + ASR (0.02) +
tokens de LLM (despreciable, ~0.0002). El humano son 6 min de monitorista a
USD 6/hora.

> Los precios son **estimaciones sin verificar** y están parametrizados por env
> (`P_VOICE_MIN`, `P_ASR_REQ`, `P_LLM_IN`, `P_LLM_OUT`, `P_HUMAN_HOUR`,
> `P_HUMAN_MIN_EVENT`). **Hay que verificarlos en el pricing oficial de Twilio y
> OpenAI antes de la demo** — el precio de voz a móvil argentino varía mucho.

Palancas de reducción de costo ya implementadas:
- Modo simulado para desarrollar sin gastar.
- Locks anti-spam en Redis (`state.once`) para no llamar 10 veces por el mismo evento.
- `gpt-4o-mini` y máximo 2 preguntas por llamada.
- Botón "ya estoy listo" en la app (`/driver/{trip_id}/ack`) que evita la llamada.

---

## Bugs conocidos

1. **Doble llamada por un mismo incidente.** Un frenazo de 65 a 0 km/h dispara
   primero `truck.slowdown` y después `truck.stopped` → dos llamadas de
   emergencia por el mismo hecho. Falta deduplicar en `detector/worker.py`.
2. **"Camión detenido 0 min"** en la alerta: el simulador comprime
   `stop_min_seconds` a 8s y el redondeo a minutos da 0.
3. Sin `OPENAI_API_KEY` el brain devuelve un fallback con `needs_human=true`,
   lo que genera una alerta de "riesgo" en cada llamada. Es esperable, pero
   ensucia la demo si se corre sin key.
4. `POST /ops/seed` crea un viaje nuevo cada vez que se lo llama.

## Decisiones pendientes (para acordar con el equipo)

- **El esquema de datos.** Está en `db.py` y lo escribió una sola persona sin
  consenso. Preguntas abiertas: ¿los `pings` van a SQLite o solo a Redis?
  ¿`trips.status` es la máquina de estados correcta
  (`en_ruta/en_puerto/esperando_puerto/habilitado/cargando/cerrado`)?
  ¿hace falta tabla de puertos en vez del puerto embebido en `trips`?
- ¿Un proceso o servicios separados?
- ¿`<Gather>` con speech-to-text (lo implementado, más simple) o Media Streams
  con OpenAI Realtime (conversación más natural, bastante más trabajo)?
- Cómo se integra el puerto/depósito de verdad.

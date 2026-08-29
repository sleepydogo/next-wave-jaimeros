# NextWave Agent

Agente de voz para operaciones de supply chain. Reacciona a incidentes y cambios
de estado, llama al trabajador por Twilio, conversa con un modelo de OpenAI y
deja un reporte estructurado para el dashboard de operaciones.

Este directorio contiene la especificacion del componente. Durante el
hackathon, el agente vive en `backend/app/agent/` y corre dentro del mismo
proceso FastAPI. El backend y la UI se desarrollan en paralelo por otros
miembros del equipo. El limite entre componentes es el bus de eventos, por lo
que el agente puede construirse y probarse con publishers simulados.

## Objetivo del MVP

Cerrar este circuito de punta a punta:

```text
API -> Redis -> detector -> bus -> agente -> Twilio/OpenAI
                                      |
                                      v
                             SQLite -> API -> UI
```

1. El detector publica un evento operacional.
2. El agente decide si corresponde llamar y con que objetivo.
3. Twilio realiza la llamada y captura la respuesta del trabajador.
4. OpenAI conduce hasta dos preguntas y devuelve una conclusion estructurada.
5. El agente publica el reporte completo en `call.finished`.
6. El backend persiste el reporte y la API lo expone al dashboard.
7. Operaciones recibe los casos que necesitan una persona.

## Alcance para la hackathon

Incluido:

- Llegada al puerto, carga habilitada y posibles emergencias en ruta.
- Llamadas salientes con Twilio `<Gather>` y speech-to-text.
- Respuestas estructuradas de OpenAI con fallback seguro.
- Modo simulado sin costo, activo por defecto.
- Transcript, diagnostico, triage, resolucion, proximos pasos y feedback.
- Escalamiento a operaciones cuando hay riesgo o el agente no puede resolver.

Fuera del MVP:

- OpenAI Realtime y audio bidireccional por Media Streams.
- Un microservicio desplegado por separado.
- Automatizaciones irreversibles sin aprobacion humana.
- Reemplazar SQLite por una base de datos distribuida.
- Soportar cualquier flujo logistico fuera de los tres escenarios de demo.

La especificacion completa y los contratos estan en [`SPECS.md`](./SPECS.md).
El orden de implementacion para las 16 horas esta en
[`ROADMAP.md`](./ROADMAP.md).
El contrato que deben usar detector y backend esta en
[`EVENTS.md`](./EVENTS.md), con JSON Schema en
[`event.schema.json`](./event.schema.json).

Roadmaps de integraciones:

- [`DISPATCHER_ROADMAP.md`](./DISPATCHER_ROADMAP.md): dashboard + email Resend.
- [`TWILIO_ROADMAP.md`](./TWILIO_ROADMAP.md): Twilio Voice + OpenAI.
- [`RABBITMQ_DOCKER_ROADMAP.md`](./RABBITMQ_DOCKER_ROADMAP.md): broker, ngrok y Compose.

## Estado actual

Existe un prototipo generado en `backend/app/`, pero no debe asumirse que el
backend ni sus contratos estan terminados. Hay que validar y adaptar cada pieza:

| Componente | Archivo | Estado |
|---|---|---|
| Decision evento -> llamada | `app/agent/worker.py` | implementado con deduplicacion por `event_id` |
| Twilio y simulacion | `app/agent/caller.py` | implementado; Twilio real sin validar |
| Conversacion OpenAI | `app/agent/brain.py` | implementado con validacion y fallback |
| Bus Redis/RabbitMQ | `app/bus.py` | implementado con envelope versionado |
| Contrato con backend | bus de eventos | acordar primero |
| Reporte operacional completo | `app/agent/report.py` | implementado con triage determinista |
| Persistencia y UI | trabajo de otros miembros | en paralelo |

## Desarrollo local

Requisitos: Python 3.11+, `uv` y Redis. Para el entorno completo, Docker Desktop.

```bash
brew services start redis
cd backend
uv venv --python 3.11 .venv
uv pip install -e .
cp ../.env.example ../.env
.venv/bin/uvicorn app.main:app --reload --port 8000
```

El default debe ser `SIMULATE_CALLS=1`; asi no se consumen creditos de Twilio.
Para probar el flujo completo sin llamadas reales:

```bash
cd backend
.venv/bin/python -m sim.simulate_trip llegada
.venv/bin/python -m sim.simulate_trip parada
```

Resultados actuales:

```bash
curl http://localhost:8000/ops/calls
curl http://localhost:8000/ops/alerts
curl http://localhost:8000/ops/metrics
```

## Llamadas reales

Definir en `.env`:

```dotenv
SIMULATE_CALLS=0
PUBLIC_URL=https://<dominio-publico>
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

Luego exponer FastAPI con `ngrok http 8000`. Twilio usa estos webhooks:

- `POST /twilio/voice/{call_id}`
- `POST /twilio/gather/{call_id}`
- `POST /twilio/status/{call_id}`

El modelo es configurable. Para el MVP se conserva `gpt-4o-mini` por costo y
latencia hasta validar otro modelo con una llamada real.

## Criterio de demo

La demo esta completa cuando un escenario simulado o real produce un reporte
consultable que permite responder: que paso, donde, cual es el triage, como se
resolvio, que sigue, cual es el diagnostico y que dijo el trabajador.

Seguir `backend/CODESTYLE.md`: funciones en lugar de clases, eventos como unico
contrato, SQLite como verdad persistente y fallback sin servicios pagos.

# Contrato de eventos enriquecidos

Version: `1`

Este documento es la fuente de verdad para la integracion entre detector,
agente y backend. La definicion machine-readable esta en
[`event.schema.json`](./event.schema.json).

## Decisiones cerradas

- El agente consume JSON enriquecido; no consulta backend ni DB para llamar.
- `trip_id` es el ID canonico de operacion en eventos de entrada.
- `report.operation_id` debe ser igual a `payload.trip_id`.
- Todos los eventos disparadores incluyen los datos minimos del trabajador.
- Todos los timestamps son Unix epoch en segundos, UTC.
- Todos los telefonos usan formato E.164, por ejemplo `+5491100000000`.
- El payload de entrada es plano.
- El agente siempre termina con `call.finished`, incluso ante un fallo.
- Backend persiste `call.finished.payload.report` de forma idempotente.
- Redis o RabbitMQ solo transportan el mensaje; no cambian su estructura.

## Envelope

Todos los mensajes usan:

```json
{
  "schema_version": 1,
  "event_id": "evt_01J6A8Y9R2",
  "type": "truck.stopped",
  "payload": {},
  "ts": 1787990400.0
}
```

| Campo | Tipo | Regla |
|---|---|---|
| `schema_version` | integer | debe ser `1` |
| `event_id` | string | unico y estable entre reintentos |
| `type` | string | uno de los eventos definidos abajo |
| `payload` | object | depende de `type` |
| `ts` | number | momento en que ocurrio el hecho |

El publisher crea `event_id`. Un retry conserva el mismo ID. Un hecho nuevo usa
otro ID. El agente deduplica los eventos de entrada por `event_id`.

## Campos comunes de entrada

Los cuatro eventos que disparan llamadas requieren:

| Campo | Tipo | Regla |
|---|---|---|
| `trip_id` | string | ID de la operacion |
| `worker_id` | string | ID estable del trabajador |
| `worker_name` | string | nombre para saludarlo |
| `worker_phone` | string | telefono E.164 |
| `lat` | number | latitud entre -90 y 90 |
| `lon` | number | longitud entre -180 y 180 |
| `location_label` | string | ubicacion legible para el reporte |
| `detail` | string | contexto opcional, sin datos inventados |
| `container` | string | contenedor opcional |
| `port_name` | string | puerto opcional salvo donde se indique |

No enviar secrets, audio, transcript ni objetos anidados en eventos de entrada.

## Eventos de entrada

### `truck.arrived`

El camion ingreso al geofence del puerto. Dispara `arrival_check`.
`port_name` es obligatorio.

```json
{
  "schema_version": 1,
  "event_id": "evt_arrived_001",
  "type": "truck.arrived",
  "payload": {
    "trip_id": "op_123",
    "worker_id": "driver_45",
    "worker_name": "Carlos",
    "worker_phone": "+5491100000000",
    "lat": -34.5745,
    "lon": -58.366,
    "location_label": "Puerto Buenos Aires - Terminal 4",
    "detail": "ingreso al geofence",
    "container": "MSCU-4471820",
    "port_name": "Puerto Buenos Aires - Terminal 4"
  },
  "ts": 1787990400.0
}
```

### `port.ready`

El puerto habilito la carga. Dispara `load_authorized`. `port_name` es
obligatorio.

```json
{
  "schema_version": 1,
  "event_id": "evt_ready_001",
  "type": "port.ready",
  "payload": {
    "trip_id": "op_123",
    "worker_id": "driver_45",
    "worker_name": "Carlos",
    "worker_phone": "+5491100000000",
    "lat": -34.5745,
    "lon": -58.366,
    "location_label": "Puerto Buenos Aires - Terminal 4",
    "detail": "carga habilitada en puerta 3",
    "container": "MSCU-4471820",
    "port_name": "Puerto Buenos Aires - Terminal 4"
  },
  "ts": 1787990700.0
}
```

### `truck.stopped`

El camion lleva demasiado tiempo detenido fuera de una parada planificada.
Dispara `emergency`. `seconds` es obligatorio.

```json
{
  "schema_version": 1,
  "event_id": "evt_stopped_001",
  "type": "truck.stopped",
  "payload": {
    "trip_id": "op_123",
    "worker_id": "driver_45",
    "worker_name": "Carlos",
    "worker_phone": "+5491100000000",
    "lat": -34.6037,
    "lon": -58.3816,
    "location_label": "RN9 km 72",
    "detail": "parada no planificada",
    "container": "MSCU-4471820",
    "seconds": 420
  },
  "ts": 1787990400.0
}
```

### `truck.slowdown`

El detector encontro una caida abrupta de velocidad. Dispara `emergency`.
`drop_pct` es obligatorio; las velocidades son opcionales.

```json
{
  "schema_version": 1,
  "event_id": "evt_slowdown_001",
  "type": "truck.slowdown",
  "payload": {
    "trip_id": "op_123",
    "worker_id": "driver_45",
    "worker_name": "Carlos",
    "worker_phone": "+5491100000000",
    "lat": -34.6037,
    "lon": -58.3816,
    "location_label": "RN9 km 72",
    "detail": "caida abrupta de velocidad",
    "container": "MSCU-4471820",
    "drop_pct": 82.5,
    "previous_speed": 80.0,
    "current_speed": 14.0
  },
  "ts": 1787990400.0
}
```

## Evento de salida

### `call.finished`

Es el unico evento terminal del agente. Se emite una vez por intento de llamada
y siempre contiene un reporte completo. El `event_id` de salida es nuevo y
`source_event_id` apunta al evento que origino la llamada.

```json
{
  "schema_version": 1,
  "event_id": "evt_call_finished_001",
  "type": "call.finished",
  "payload": {
    "trip_id": "op_123",
    "call_id": "call_789",
    "source_event_id": "evt_stopped_001",
    "reason": "emergency",
    "report": {
      "id": "report_abc123",
      "operation_id": "op_123",
      "worker_id": "driver_45",
      "call_id": "call_789",
      "event_type": "truck.stopped",
      "what_happened": "Camion detenido fuera de una parada planificada",
      "where": {
        "lat": -34.6037,
        "lon": -58.3816,
        "label": "RN9 km 72"
      },
      "triage": {
        "level": "high",
        "needs_human": true,
        "reason": "El trabajador reporta fatiga"
      },
      "agent_resolution": "Escalo el caso a operaciones",
      "next_steps": [
        {
          "action": "Contactar al supervisor de turno",
          "owner": "operations",
          "status": "pending"
        }
      ],
      "diagnosis": {
        "code": "worker_fatigue",
        "summary": "Parada preventiva por cansancio",
        "confidence": 0.88
      },
      "worker_feedback": {
        "summary": "Necesita descansar veinte minutos",
        "available": false,
        "eta_min": 20
      },
      "call_status": "done",
      "transcript": "AGENTE: Esta todo bien?\nTRABAJADOR: Necesito descansar.",
      "created_at": 1787990460.0
    },
    "cost_usd": 0.2
  },
  "ts": 1787990460.0
}
```

Estados terminales de `report.call_status`:

- `done`: hubo conversacion y cierre normal.
- `failed`: error interno, de datos, Twilio u OpenAI sin fallback posible.
- `no_answer`: el trabajador no atendio.
- `busy`: la linea estaba ocupada.

Para `failed`, `no_answer` o `busy`, el reporte igualmente incluye el hecho y
la ubicacion originales, `diagnosis.code=unknown`, `needs_human=true` y un
proximo paso para operaciones. `transcript` puede ser un string vacio.

## Idempotencia

- El agente adquiere `state.once("event:{event_id}", ttl=86400)` antes de llamar.
- El callback terminal adquiere
  `state.once("call:{call_id}:finish", ttl=86400)`.
- Backend persiste reportes con `call_id` unico.
- Redelivery del mismo evento no crea otra llamada.
- Redelivery de `call.finished` no crea otro reporte.

## Compatibilidad

Dentro de `schema_version=1` solo se agregan campos opcionales. Renombrar,
eliminar, cambiar tipos o volver obligatorio un campo requiere version `2`.
Consumidores deben rechazar versiones desconocidas y loggear el `event_id`.

## Validacion para mocks

Los mocks de backend deben copiar uno de los ejemplos de entrada y cambiar solo
los valores. Antes de integrar, validar cada fixture contra
`event.schema.json`. Hay fixtures listos en [`examples/`](./examples/). Un
payload invalido no debe iniciar una llamada.

Validacion manual:

```bash
npx --yes ajv-cli@5 validate --spec=draft2020 \
  -s backend/agent/event.schema.json \
  -d "backend/agent/examples/*.json"
```

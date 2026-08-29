# Especificacion del agente de voz

## 1. Proposito

El agente atiende eventos de una operacion de supply chain, contacta al
trabajador involucrado y devuelve informacion accionable a operaciones. Debe
reducir llamadas manuales sin ocultar incertidumbre ni ejecutar acciones de
riesgo sin intervencion humana.

La prioridad de esta especificacion es tener una demo end-to-end confiable en
16 horas. Las decisiones favorecen simplicidad, simulacion y observabilidad.
El roadmap ejecutable esta en [`ROADMAP.md`](./ROADMAP.md).
El contrato de integracion definitivo esta en [`EVENTS.md`](./EVENTS.md) y
[`event.schema.json`](./event.schema.json); prevalece ante cualquier ejemplo
resumido de este documento.

## 2. Arquitectura decidida

Para el MVP no se crea otro proceso ni otro repositorio. Detector, bus, agente y
dispatcher son modulos dentro de FastAPI y se ejecutan como tasks de `asyncio`.
Ningun modulo llama directamente al worker del agente: publica un evento.
El backend y la UI se implementan en paralelo; el agente debe funcionar con un
publisher y un consumer simulados hasta el momento de integracion.

```text
cliente GPS / API
       |
       v
FastAPI -> Redis (estado volatil) -> detector
                                      |
                                      v
                    SQLite <- bus de eventos -> agent.worker
                                                   |
                                                   v
                                         agent.caller -> Twilio
                                                   |
                                             agent.brain -> OpenAI
                                                   |
                                                   v
                                             call.finished
                                                   |
                                      backend -> SQLite -> /ops/* -> dashboard
```

El bus usa Redis pub/sub por defecto. Si existe `RABBITMQ_URL`, usa RabbitMQ.
El evento se persiste en SQLite antes de publicarse. RabbitMQ es el transporte
preferido para una futura separacion fisica, no un requisito de la demo.

### Responsabilidades

| Modulo | Responsabilidad | No debe hacer |
|---|---|---|
| `agent/worker.py` | decidir si llamar, motivo y escalamiento | hablar con OpenAI |
| `agent/caller.py` | sesion, Twilio, transcript, cierre y costo | decidir el dialogo |
| `agent/brain.py` | dialogo y extraccion estructurada | escribir DB o TwiML |
| `bus.py` | persistir, publicar y despachar eventos | logica operacional |
| `db.py` | acceso SQLite | guardar estado volatil |
| `state.py` | sesiones y locks con TTL en Redis | ser fuente de verdad |

## 3. Escenarios del MVP

| Evento | Motivo de llamada | Objetivo | Triage inicial |
|---|---|---|---|
| `truck.arrived` | `arrival_check` | confirmar disponibilidad y ETA | bajo |
| `port.ready` | `load_authorized` | confirmar que puede avanzar a carga | bajo |
| `truck.stopped` | `emergency` | entender parada y necesidad de ayuda | alto |
| `truck.slowdown` | `emergency` | descartar incidente o frenada riesgosa | medio |

Una deteccion repetida debe usar un lock `state.once` para evitar llamadas
duplicadas. Una llamada hace como maximo dos preguntas. Si no logra una
conclusion, marca `needs_human=true` y escala.

## 4. Contrato de entrada

El envelope interno del bus es:

```json
{
  "schema_version": 1,
  "type": "truck.stopped",
  "event_id": "evt_123",
  "payload": {
    "trip_id": "op_123",
    "worker_id": "driver_45",
    "worker_name": "Carlos",
    "worker_phone": "+5491100000000",
    "lat": -34.6037,
    "lon": -58.3816,
    "location_label": "RN9 km 72",
    "seconds": 420
  },
  "ts": 1787990400.0
}
```

Reglas:

- `type` usa nombres definidos unicamente en `app/events.py`.
- `schema_version` vale `1`; un cambio incompatible requiere otra version.
- `event_id` identifica el hecho y permite deduplicar su procesamiento.
- `payload` es un objeto plano e incluye `trip_id`.
- `trip_id` es el `operation_id` del dominio hasta acordar otro modelo.
- Todos los eventos incluyen `worker_id`, `worker_name` y `worker_phone` para
  que el agente no dependa del backend. La alternativa es acordar un unico
  endpoint de contexto; no se implementan ambos caminos para la demo.
- La ubicacion puede venir como coordenadas y, si existe, nombre legible.
- Los consumidores deben tolerar redelivery; iniciar una llamada requiere una
  clave idempotente por operacion, evento y ventana temporal.

Payload minimo por evento:

| Evento | Campos adicionales requeridos |
|---|---|
| `truck.arrived` | ubicacion o puerto |
| `port.ready` | puerto o punto de carga |
| `truck.stopped` | `lat`, `lon`, `seconds` |
| `truck.slowdown` | `lat`, `lon`, `drop_pct` |

## 5. Flujo de llamada

1. `agent.worker` recibe el evento, determina el motivo y pasa al caller el tipo
   y payload originales.
2. `agent.caller` obtiene viaje y trabajador del payload enriquecido. Si el
   equipo elige una API de contexto, usa ese unico adapter en su lugar.
3. Crea `call_id`, persiste estado `ringing` y guarda la sesion, incluido el
   evento original, en Redis por una hora.
4. En simulacion ejecuta respuestas predefinidas. En real, Twilio inicia la
   llamada contra `PUBLIC_URL`.
5. Twilio reproduce el mensaje con `<Say>` y captura voz con `<Gather>`.
6. Cada turno se envia a OpenAI junto al objetivo, contexto e historial.
7. `agent.brain` responde JSON, nunca TwiML.
8. Al finalizar se guardan transcript, resultado, metricas, duracion y costo.
9. Se genera el reporte y se publica `call.finished`.
10. El worker actualiza la operacion o publica `alert.raised`.

Estados terminales de llamada: `done`, `failed`, `no_answer` y `busy`. Para el
MVP, cualquier estado sin conversacion genera reporte con diagnostico `unknown`
y escalamiento humano.

## 6. Contrato del modelo

El proveedor es OpenAI y el modelo se selecciona con `OPENAI_MODEL`. El valor
inicial es `gpt-4o-mini`; debe poder cambiarse sin tocar codigo.

Entrada:

- Objetivo de la llamada.
- Datos conocidos de operacion, trabajador y ubicacion.
- Historial de la llamada.
- Regla de no inventar datos y limite de dos preguntas.

Salida obligatoria:

```json
{
  "reply": "Gracias. Voy a avisar a operaciones.",
  "done": true,
  "outcome": {
    "available": false,
    "eta_min": null,
    "problem": "fatiga",
    "needs_human": true
  },
  "voice": {
    "stress": 0.3,
    "fatigue": 0.9,
    "clarity": 0.8,
    "notes": "indica cansancio y pide detenerse"
  }
}
```

Configuracion objetivo: temperatura `0.2-0.3`, salida JSON y unos 300 tokens
maximos. Si falta la API key, la respuesta es invalida o OpenAI falla, se usa un
fallback determinista y `needs_human=true`.

No se deben presentar las metricas de voz como diagnostico medico. Son senales
operacionales con baja confianza y requieren confirmacion humana.

## 7. Reporte operacional

Cada intento de llamada debe producir exactamente un reporte, incluso si nadie
atiende. `operation_id` referencia a `trips.id` y `worker_id` a `drivers.id` en
el contrato propuesto.

```json
{
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
  "agent_resolution": "Recomendo no continuar y escalo a operaciones",
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
    "summary": "Se detuvo porque se estaba durmiendo",
    "available": false,
    "eta_min": 20
  },
  "call_status": "done",
  "transcript": "AGENTE: ...\nTRABAJADOR: ...",
  "created_at": 1787990400.0
}
```

### Valores controlados

- `triage.level`: `low`, `medium`, `high`, `critical`.
- `diagnosis.code`: `normal`, `delayed`, `vehicle_issue`, `worker_fatigue`,
  `safety_incident`, `no_contact`, `unknown`.
- `next_steps[].owner`: `agent`, `worker`, `operations`, `maintenance`.
- `next_steps[].status`: `pending`, `completed`, `cancelled`.
- `call_status`: `done`, `failed`, `no_answer`, `busy`.

`next_steps` es una lista porque un incidente puede requerir varias acciones.
Solo una accion segura, reversible y explicitamente implementada puede tener
`owner=agent`. En el MVP, enviar una alerta o programar un reintento son las
unicas acciones autonomas previstas.

### Persistencia propuesta

El equipo de backend puede agregar una tabla `operation_reports` despues de
validarla:

```sql
CREATE TABLE IF NOT EXISTS operation_reports (
    id TEXT PRIMARY KEY,
    operation_id TEXT,
    worker_id TEXT,
    call_id TEXT UNIQUE,
    event_type TEXT,
    what_happened TEXT,
    where_json TEXT,
    triage_json TEXT,
    agent_resolution TEXT,
    next_steps_json TEXT,
    diagnosis_json TEXT,
    worker_feedback_json TEXT,
    call_status TEXT,
    transcript TEXT,
    created_at REAL
);
```

Los campos compuestos se guardan como JSON `TEXT`. `call_id UNIQUE` vuelve
idempotente la generacion. El agente entrega el reporte en `call.finished`; el
backend es responsable de persistirlo. Redis solo guarda la sesion activa.

### Construccion del reporte

Para el MVP, `app/agent/report.py` arma el reporte con reglas deterministas; no
hace una segunda llamada al modelo:

- IDs y trabajador salen de la llamada y del evento original.
- `what_happened` y `where` salen del evento original, nunca se inventan.
- `triage` toma el mayor nivel entre las reglas de seguridad y el riesgo de voz.
- `agent_resolution` describe acciones realmente ejecutadas.
- `next_steps` se deriva del triage, `needs_human` y el motivo de llamada.
- `diagnosis` usa un codigo controlado basado en `outcome.problem`; si no hay
  evidencia suficiente usa `unknown`.
- `worker_feedback` resume el outcome y conserva disponibilidad y ETA.

El evento original debe viajar hasta la sesion porque `reason=emergency` no
permite distinguir por si solo una parada de una caida de velocidad.

## 8. Contrato de salida

Al finalizar la llamada, el agente publica:

```json
{
  "schema_version": 1,
  "type": "call.finished",
  "event_id": "evt_result_456",
  "payload": {
    "trip_id": "op_123",
    "call_id": "call_789",
    "source_event_id": "evt_123",
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
      "transcript": "AGENTE: ...\nTRABAJADOR: ...",
      "created_at": 1787990460.0
    },
    "cost_usd": 0.2
  },
  "ts": 1787990400.0
}
```

El backend persiste `payload.report` de forma idempotente por `call_id`. La UI
lee el reporte desde la API y no consume el bus directamente.

Endpoints minimos para la UI:

| Metodo | Ruta | Resultado |
|---|---|---|
| `GET` | `/ops/reports` | reportes recientes, ultimo primero |
| `GET` | `/ops/reports/{report_id}` | detalle completo |
| `GET` | `/ops/operations/{operation_id}/reports` | historial de operacion |

Los endpoints solo consultan SQLite y devuelven los JSON ya deserializados.

## 9. Triage y automatizacion

Reglas iniciales, antes de cualquier inferencia del modelo:

| Condicion | Triage | Accion |
|---|---|---|
| Riesgo inmediato, accidente o pedido de emergencia | critical | alertar y escalar ya |
| Fatiga alta, averia o imposibilidad de continuar | high | alertar y bloquear avance manualmente |
| Retraso con ETA conocida, frenada sin dano | medium | registrar y notificar |
| Confirmacion normal de llegada o carga | low | actualizar estado |
| Sin respuesta o informacion insuficiente | high | reintento unico y escalamiento |

El modelo puede enriquecer el motivo, pero no reducir un triage determinado por
una regla de seguridad. Un humano debe intervenir ante `high` o `critical`.

## 10. Seguridad y privacidad

- Credenciales solo por variables de entorno y nunca en logs o eventos.
- Validar la firma de los webhooks de Twilio antes de una puesta en produccion.
- Escapar todo texto insertado en `<Say>`.
- No incluir telefono completo ni transcript en logs de nivel `info`.
- Informar al trabajador que habla con un asistente automatico.
- Definir retencion y acceso de transcripts antes de usar datos reales.
- El agente no diagnostica salud ni sanciona trabajadores.
- Ante duda, falla cerrada: registrar, escalar y no ejecutar la accion.

## 11. Observabilidad y fallos

Loggear con `call_id`, `trip_id`, tipo de evento, estado y latencia, sin datos
sensibles. Metricas minimas para la demo:

- Eventos recibidos y llamadas iniciadas.
- Llamadas completadas, fallidas y sin respuesta.
- Tiempo evento -> llamada y duracion de llamada.
- Reportes por nivel de triage.
- Escalamientos y costo estimado.
- Errores de Twilio, OpenAI y bus.

Si Twilio falla, persistir `failed`. Si OpenAI falla durante una llamada, usar
fallback y escalar. Si Redis pierde una sesion, cerrar como `failed` y usar
diagnostico `unknown`. Un handler fallido no debe detener otros handlers del bus.

## 12. Plan de implementacion de 16 horas

| Prioridad | Entregable | Condicion de terminado |
|---|---|---|
| P0 | contrato y tabla de reportes | un reporte por `call_id` |
| P0 | generador de reporte al cerrar llamada | cubre llamada exitosa y fallida |
| P0 | endpoints de lectura | UI obtiene lista y detalle |
| P0 | simulacion end-to-end | llegada y parada generan reporte |
| P1 | llamada real | una llamada validada con ngrok |
| P1 | UI de detalle | muestra todos los campos requeridos |
| P1 | deduplicacion | un incidente no genera dos llamadas |
| P2 | RabbitMQ | solo si Redis pub/sub bloquea la demo |

Orden recomendado: primero flujo simulado y reporte visible; despues Twilio
real; al final mejoras visuales, RabbitMQ y cambios de modelo.

## 13. Criterios de aceptacion

1. Un evento soportado inicia como maximo una llamada dentro de su ventana.
2. La demo funciona sin credenciales pagas con `SIMULATE_CALLS=1`.
3. Una llamada exitosa genera transcript y los nueve datos operacionales
   requeridos: operacion, trabajador, que, donde, triage, resolucion, proximos
   pasos, diagnostico y feedback.
4. Una llamada fallida tambien genera reporte y escalamiento.
5. `high` y `critical` nunca se resuelven silenciosamente.
6. La UI puede obtener lista y detalle sin leer Redis ni RabbitMQ.
7. Reiniciar FastAPI no elimina reportes.
8. No se llama a Twilio cuando `SIMULATE_CALLS=1`.

## 14. Decisiones pendientes

- Confirmar si `trip_id` es definitivamente el identificador de operacion.
- Acordar el esquema `operation_reports` antes de modificar `db.py`.
- Elegir el modelo de OpenAI luego de medir latencia, costo y calidad real.
- Decidir si produccion usara `<Gather>` o OpenAI Realtime.
- Definir reintentos, retencion de audio/transcripts y responsables por accion.
- Extraer el agente como servicio solo cuando exista una necesidad operativa.

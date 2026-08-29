# Roadmap de implementacion: bus y agente

## Objetivo

Entregar en 16 horas un agente demostrable que:

1. Consume un evento operacional desde el bus.
2. Inicia una llamada simulada o real.
3. Conversa con el trabajador usando OpenAI.
4. Genera un reporte estructurado.
5. Publica el resultado para que el backend lo persista y la UI lo muestre.

El backend y la UI se desarrollan en paralelo. El agente no debe esperar a que
esten terminados: durante el desarrollo usa eventos de entrada y consumidores
de salida simulados.

El contrato definitivo esta en [`EVENTS.md`](./EVENTS.md) y su JSON Schema en
[`event.schema.json`](./event.schema.json). Los ejemplos de este roadmap son un
resumen; ante cualquier diferencia mandan esos dos archivos.

## Responsabilidad propia

Incluido en este trabajo:

- `app/events.py`: nombres y contratos de eventos.
- `app/bus.py`: publicacion, consumo y dispatch.
- `app/agent/worker.py`: evento -> decision de llamada.
- `app/agent/caller.py`: sesion, Twilio, simulacion y cierre.
- `app/agent/brain.py`: conversacion y extraccion con OpenAI.
- Webhooks `/twilio/*` necesarios para completar la llamada.
- Generacion del reporte y publicacion de `call.finished`.
- Simulador y pruebas del flujo del agente.

Responsabilidad de los companeros:

- API de negocio, detector y endpoints `/ops/*`.
- Esquema final y persistencia de operaciones/reportes.
- Dashboard y visualizacion del reporte.

Punto compartido:

- Acordar hoy los JSON de entrada y salida. Despues de acordarlos, solo se
  agregan campos opcionales; no se renombran ni eliminan campos.

## Estrategia de desacople

Para no depender de consultas a una API o base todavia inexistente, el evento
de entrada debe traer el contexto minimo para llamar. Esta es la opcion
recomendada para la hackathon:

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
    "seconds": 420,
    "detail": "parada no planificada"
  },
  "ts": 1787990400.0
}
```

Si el equipo no quiere datos del trabajador en el bus, debe entregar antes de
la integracion un endpoint estable como `GET /internal/operations/{trip_id}`.
No implementar ambas alternativas para la demo.

La salida estable del agente es `call.finished` con `report` completo:

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
  "ts": 1787990460.0
}
```

El backend persiste `payload.report`. El agente puede guardar una copia local
para debug, pero esa copia no es el contrato de integracion.

## Plan de 16 horas

### Paso 0: congelar contratos - 30 minutos

Acciones:

- Compartir con backend los JSON de entrada y salida anteriores.
- Confirmar que `trip_id` equivale a `operation_id`.
- Elegir evento enriquecido o endpoint de contexto. Se recomienda el evento.
- Confirmar quien persiste el reporte. Se recomienda el backend consumidor.
- Definir un telefono de prueba y responsable de las credenciales.

Terminado cuando:

- Backend puede producir un ejemplo de entrada.
- Backend acepta persistir un ejemplo de salida.
- No queda ninguna consulta bloqueante para obtener nombre o telefono.

No avanzar sin cerrar este paso; es el unico bloqueo de coordinacion.

### Paso 1: bus minimo confiable - 1 hora 30 minutos

Acciones:

- Definir constantes en `events.py`: eventos operacionales y `call.finished`.
- Mantener una API unica: `@bus.on(...)`, `bus.publish(...)`, `bus.start()`.
- Usar Redis pub/sub para la primera demo local.
- Conservar RabbitMQ detras de `RABBITMQ_URL`, sin hacerlo requisito inicial.
- Persistir cada evento en el log SQLite antes de enviarlo al transporte.
- Agregar `event_id`, timestamp y logs con tipo de evento.
- Aislar errores por handler para que un consumidor no detenga a los demas.
- Deduplicar eventos con `source_event_id` o un lock con TTL.

Prueba:

- Un script publica `truck.stopped`; un handler recibe exactamente un payload.
- Un handler que falla no impide que el siguiente procese el evento.

Terminado cuando:

- Publisher y consumer corren localmente de punta a punta.
- Publicar dos veces el mismo `event_id` no inicia dos llamadas.

### Paso 2: vertical slice simulado - 2 horas

Acciones:

- Implementar primero solo `truck.stopped -> emergency`.
- Crear `call_id` y una sesion con contexto, historial y evento original.
- Ejecutar respuestas predefinidas cuando `SIMULATE_CALLS=1`.
- Publicar `call.finished` al cerrar; el inicio se mantiene como estado interno.
- No consultar la API ni la DB del backend en este paso.

Prueba:

```text
publisher simulado -> bus -> worker -> caller simulado -> call.finished
```

Terminado cuando:

- Un comando produce en consola un `call.finished` valido.
- El resultado conserva `source_event_id`, operacion, trabajador y ubicacion.

Este es el primer hito demostrable. Si algo posterior falla, esta version debe
seguir funcionando.

### Paso 3: brain de OpenAI - 2 horas

Acciones:

- Mantener prompts cortos en espanol rioplatense.
- Limitar la llamada a dos preguntas.
- Enviar solo contexto conocido y prohibir que el modelo invente datos.
- Exigir JSON con `reply`, `done`, `outcome` y `voice`.
- Validar presencia y tipos de los campos antes de usarlos.
- Usar `OPENAI_MODEL`, temperatura baja y limite pequeno de tokens.
- Implementar fallback determinista sin API key o ante JSON invalido.

Prueba:

- Respuesta valida de OpenAI completa la llamada.
- Sin `OPENAI_API_KEY`, el flujo termina y marca `needs_human=true`.
- Una respuesta invalida no rompe el consumer.

Terminado cuando:

- El mismo vertical slice funciona con modelo real y con fallback.

### Paso 4: generador de reportes - 2 horas

Acciones:

- Crear `app/agent/report.py` con una funcion pura que reciba evento, llamada,
  outcome y metricas de voz.
- Construir los nueve campos acordados en `SPECS.md`.
- Derivar ubicacion y hecho desde el evento, no desde el modelo.
- Aplicar reglas deterministas de triage.
- No permitir que el modelo reduzca un triage de seguridad.
- Generar reporte tambien para `failed`, `busy` y `no_answer`.
- Incluir el reporte completo en `call.finished`.

Prueba:

- Caso normal produce triage `low`.
- Fatiga o pedido de ayuda produce `high` o `critical`.
- Sin respuesta produce diagnostico `unknown` y escalamiento.

Terminado cuando:

- Todos los campos requeridos existen para llamada exitosa y fallida.
- El JSON puede ser persistido por backend sin transformaciones ambiguas.

### Paso 5: Twilio real - 3 horas

Acciones:

- Implementar llamada saliente con Twilio.
- Exponer FastAPI con ngrok.
- Implementar `/twilio/voice/{call_id}`, `/twilio/gather/{call_id}` y
  `/twilio/status/{call_id}`.
- Armar TwiML a mano, escapar `<Say>` y usar `<Gather>` speech-to-text.
- Mapear `completed`, `failed`, `busy` y `no-answer` a estados internos.
- Asegurar que el callback terminal genere un solo reporte.
- Mantener imports y credenciales de Twilio solo en el camino real.

Prueba:

- Hacer una llamada al telefono de prueba.
- Responder al menos una pregunta.
- Confirmar `call.finished` con transcript y reporte.

Terminado cuando:

- Una llamada real completa el mismo contrato que la simulacion.
- Repetir un callback de Twilio no duplica el reporte.

Si Twilio consume mas de tres horas, volver al simulador y continuar la
integracion. Una demo simulada completa vale mas que una llamada real rota.

### Paso 6: escenarios restantes - 1 hora 30 minutos

Acciones:

- Agregar `truck.arrived -> arrival_check`.
- Agregar `port.ready -> load_authorized`.
- Agregar `truck.slowdown -> emergency` reutilizando el flujo existente.
- Completar openers, objetivos, respuestas simuladas y reglas de reporte.
- Definir lock anti-spam por operacion y tipo de incidente.

Prueba:

- Ejecutar un ejemplo por escenario.
- Verificar motivo, opener, triage y reporte esperados.

Terminado cuando:

- Los cuatro eventos soportados terminan sin ramas especiales fuera del worker.

### Paso 7: integracion con backend - 1 hora 30 minutos

Acciones:

- Consumir un evento producido por el backend real.
- Comparar el payload con el contrato congelado.
- Entregar al backend un `call.finished` real o simulado.
- Confirmar que se persiste usando `source_event_id` o `call_id` como clave
  idempotente.
- Agregar solo adaptaciones pequenas; no redisenar el agente en esta etapa.

Terminado cuando:

- Un evento del backend produce un reporte visible desde su endpoint.
- El backend no necesita conocer sesiones, prompts ni detalles de Twilio.

### Paso 8: estabilizacion y demo - 2 horas

Acciones:

- Correr el flujo completo tres veces desde estado limpio.
- Probar sin OpenAI, sin Twilio y con un evento duplicado.
- Revisar logs para eliminar telefono, secrets y transcript completo.
- Preparar un escenario principal y uno de fallback.
- Documentar comandos exactos y variables necesarias.
- Congelar cambios 30 minutos antes de presentar.

Terminado cuando:

- La demo principal funciona tres veces consecutivas.
- Existe un comando unico para ejecutar la simulacion.
- El modo simulado queda disponible si falla internet o una credencial.

## Orden de prioridades

P0, obligatorio:

- Contratos acordados.
- Bus local.
- Un escenario simulado end-to-end.
- Reporte completo.
- Fallback sin OpenAI/Twilio.
- Integracion de salida con backend.

P1, importante:

- Una llamada real de Twilio.
- Los otros tres escenarios.
- Idempotencia de callbacks y eventos.

P2, solo si sobra tiempo:

- RabbitMQ real.
- Metricas avanzadas de voz.
- Reintentos configurables.
- Mejoras de prompts.
- OpenAI Realtime o Media Streams.

No implementar OpenAI Realtime durante estas 16 horas.

## Pruebas minimas

| Caso | Entrada | Resultado esperado |
|---|---|---|
| emergencia simulada | `truck.stopped` | reporte `high`, llamada terminada |
| flujo normal | `truck.arrived` | reporte `low`, disponibilidad guardada |
| sin OpenAI | evento valido, sin key | fallback y `needs_human=true` |
| sin respuesta | status `no-answer` | reporte `unknown`, escalamiento |
| evento duplicado | mismo `event_id` dos veces | una sola llamada |
| callback duplicado | mismo status Twilio dos veces | un solo reporte |
| payload invalido | falta `worker_phone` | `call.finished` con status `failed` |

## Checklist de integracion

- [ ] Backend publica uno de los eventos soportados.
- [ ] El evento contiene `event_id`, `trip_id` y contexto del trabajador.
- [ ] Los telefonos usan formato E.164.
- [ ] Agente publica `call.finished` aunque la llamada falle.
- [ ] Backend persiste por `call_id` o `source_event_id` de forma idempotente.
- [ ] UI puede mostrar todos los campos de `report` sin leer Redis.
- [ ] `SIMULATE_CALLS=1` no consume servicios pagos.
- [ ] Secrets quedan solo en variables de entorno.
- [ ] Existe un escenario de demo probado sin internet.

## Regla para recortar alcance

Ante un bloqueo, recortar en este orden:

1. RabbitMQ: usar Redis pub/sub.
2. Llamada real: usar simulacion.
3. Escenarios secundarios: conservar solo `truck.stopped`.
4. Metricas de voz: conservar solo transcript y outcome.

Nunca recortar el contrato del reporte, el fallback ni la idempotencia basica.

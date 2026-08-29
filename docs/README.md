# docs

## Dónde está la documentación

- **API**: Swagger en <http://localhost:8000/docs> con el backend corriendo.
  Los 18 endpoints, agrupados por audiencia (`driver`, `ops`, `twilio`), cada
  uno explicando qué evento dispara y qué devuelve. La portada tiene el
  recorrido de prueba paso a paso.
- **Backend**: [`backend/README.md`](../backend/README.md) — el flujo completo,
  los módulos y qué estado vive en Redis vs. SQLite.
- **Estilo de código**: [`backend/CODESTYLE.md`](../backend/CODESTYLE.md).
- **Contrato del agente**: [`backend/agent/EVENTS.md`](../backend/agent/EVENTS.md).
- **Roadmap del dispatcher**:
  [`backend/agent/DISPATCHER_ROADMAP.md`](../backend/agent/DISPATCHER_ROADMAP.md).
- **Roadmap de Twilio Voice**:
  [`backend/agent/TWILIO_ROADMAP.md`](../backend/agent/TWILIO_ROADMAP.md).
- **Roadmap de RabbitMQ y Docker**:
  [`backend/agent/RABBITMQ_DOCKER_ROADMAP.md`](../backend/agent/RABBITMQ_DOCKER_ROADMAP.md).

## Documentos pendientes

- **`COSTS.md`** — el esquema de costos detallado que pide el challenge.
  El modelo ya está implementado en `backend/app/costs.py` y el endpoint
  `/ops/metrics` devuelve el costo real medido. Falta el documento con:
  - desglose por evento (telefonía, ASR, LLM, mensajería)
  - comparativa contra el monitorista humano
  - proyección a escala (N camiones × M eventos/día × 30 días)
  - palancas de reducción de costo y cuánto ahorra cada una
  - **verificar los precios** contra el pricing oficial de Twilio y OpenAI:
    los valores actuales son estimaciones sin confirmar.

- **`ARCHITECTURE.md`** — por ahora el diagrama vive en el README raíz.

Ver "Decisiones pendientes" en el README raíz antes de escribir esto.

# docs

Vacío todavía salvo este índice.

Documentos pendientes:

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

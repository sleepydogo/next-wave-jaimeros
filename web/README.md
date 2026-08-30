# web — dashboard de métricas

Vacío todavía. Acá va la web del monitorista en React (Vite).

Qué tiene que mostrar:

- Lista de camiones activos con su último ping y estado del viaje.
- Timeline de eventos por viaje (llegada, parada, frenada, llamadas).
- Transcripciones de las llamadas + métricas de voz del conductor (estrés,
  fatiga, riesgo).
- Botón "el puerto habilitó la carga" → dispara la segunda llamada.
- Contador de costos en vivo: agente vs. monitorista humano.

Endpoints que consume (backend en `localhost:8000`, CORS abierto):

```
GET  /ops/trips                     lista de viajes + último ping
GET  /ops/trips/{id}                detalle: pings, eventos, llamadas
GET  /ops/calls                     llamadas con transcripción y voz
GET  /ops/alerts                    alertas
GET  /ops/metrics                   KPIs + costos
GET  /ops/thresholds                thresholds actuales del detector
POST /ops/trips/{id}/port-ready     habilitar la carga
POST /ops/thresholds/tune           correr el cron agent a mano
```

El frontend consume siempre estos endpoints; ya no usa el dataset mock como
fallback. Para apuntarlo a otro ambiente, copiar `.env.example` a `.env.local`
y cambiar `VITE_API_URL`. En Vercel, configurar la misma variable con la URL
pública del backend.

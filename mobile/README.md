# mobile — app del conductor

Vacío todavía. Acá va la app en React Native (Expo SDK 54).

Qué tiene que hacer:

- Mostrar el viaje activo: contenedor, puerto destino, estado.
- Mandar la posición GPS cada pocos segundos al backend (es lo que alimenta al
  detector).
- Botón "ya estoy listo para cargar" → evita una llamada, y por lo tanto ahorra
  plata.
- Ver el historial de llamadas que le hizo el agente.

Endpoints que consume (backend en `localhost:8000`):

```
GET  /driver/{driver_id}/trip    viaje activo + últimas llamadas
POST /driver/ping                {trip_id, lat, lon, speed}
POST /driver/{trip_id}/ack       "ya estoy listo"
```

Mientras no exista la app, `backend/sim/simulate_trip.py` genera los pings y
alcanza para la demo.

# Trigger manual de una llamada

Este flujo permite disparar el agente desde la API actual. Con
`SIMULATE_CALLS=1` ejecuta toda la conversacion sin llamar por telefono. Cuando
Twilio este configurado y `SIMULATE_CALLS=0`, usa el mismo request para iniciar
una llamada real.

## Opcion recomendada: llegada al puerto

### 1. Crear una operacion

```http
POST http://localhost:8000/ops/seed
```

No requiere body. Ejemplo con curl:

```bash
curl --request POST http://localhost:8000/ops/seed
```

Respuesta esperada:

```json
{
  "trip_id": "a1b2c3d4",
  "driver_id": "driver_01",
  "port": {
    "name": "Puerto Buenos Aires - Terminal 4",
    "lat": -34.5745,
    "lon": -58.366
  }
}
```

Guardar el `trip_id` de la respuesta.

### 2. Enviar el ping que dispara la llamada

```http
POST http://localhost:8000/driver/ping
Content-Type: application/json
```

Payload para Postman, Insomnia o Swagger:

```json
{
  "trip_id": "a1b2c3d4",
  "lat": -34.5745,
  "lon": -58.366,
  "speed": 20
}
```

Reemplazar `a1b2c3d4` por el `trip_id` creado en el paso anterior.

Ejemplo con curl:

```bash
curl --request POST http://localhost:8000/driver/ping \
  --header "Content-Type: application/json" \
  --data '{
    "trip_id": "a1b2c3d4",
    "lat": -34.5745,
    "lon": -58.366,
    "speed": 20
  }'
```

Las coordenadas estan dentro del geofence del puerto. El detector publica
`truck.arrived` y el agente inicia una llamada con motivo `arrival_check`.

El procesamiento es asincrono. La respuesta del ping puede mostrar el estado
anterior durante unos segundos.

## Script completo

Este comando crea la operacion, extrae el ID y dispara la llegada:

```bash
SEED=$(curl --silent --fail --request POST http://localhost:8000/ops/seed)
TRIP_ID=$(printf '%s' "$SEED" | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["trip_id"])')

curl --fail --request POST http://localhost:8000/driver/ping \
  --header "Content-Type: application/json" \
  --data "{\"trip_id\":\"$TRIP_ID\",\"lat\":-34.5745,\"lon\":-58.366,\"speed\":20}"

printf '\ntrip_id=%s\n' "$TRIP_ID"
```

## Opcion inmediata: puerto habilitado

Si ya existe una operacion, este endpoint dispara una llamada
`load_authorized` sin enviar coordenadas nuevas:

```http
POST http://localhost:8000/ops/trips/{trip_id}/port-ready
```

No requiere body:

```bash
curl --request POST \
  http://localhost:8000/ops/trips/a1b2c3d4/port-ready
```

Respuesta esperada:

```json
{
  "ok": true
}
```

## Verificar el resultado

Esperar entre 5 y 15 segundos en modo simulado:

```bash
curl http://localhost:8000/ops/calls
curl http://localhost:8000/ops/trips/a1b2c3d4
curl http://localhost:8000/ops/alerts
curl http://localhost:8000/ops/metrics
docker compose logs --since 2m backend
```

En `/ops/calls` debe aparecer una llamada con:

```json
{
  "trip_id": "a1b2c3d4",
  "reason": "arrival_check",
  "status": "done"
}
```

Si la llamada sigue en `ringing`, esperar unos segundos y consultar otra vez.

## Probar ahora con OpenAI y sin Twilio

Como `OPENAI_API_KEY` ya esta en `.env`, se puede probar el modelo real mientras
la telefonia sigue simulada:

```dotenv
SIMULATE_CALLS=1
SIMULATE_DISPATCH=1
```

Recrear backend para que lea el `.env`:

```bash
docker compose up -d --build --force-recreate backend
docker compose exec backend python -c \
  'from app.agent.brain import client; print("openai_configured=", client is not None)'
```

El comando solo confirma que existe configuracion; no imprime la API key.
Despues ejecutar el script completo de llegada.

## Preparar una llamada real

Antes de cambiar a `SIMULATE_CALLS=0`:

1. Configurar `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` y `TWILIO_FROM`.
2. Configurar `NGROK_AUTHTOKEN`, `NGROK_DOMAIN` y `PUBLIC_URL`.
3. Habilitar el pais destino en Twilio Voice Geo Permissions.
4. Verificar el telefono receptor si la cuenta Twilio es trial.
5. Usar un numero E.164, por ejemplo `+54911XXXXXXXX`.

El seed actual crea `driver_01` con el telefono ficticio `+5491100000000`.
Antes de una llamada real hay que reemplazarlo por el telefono verificado. Para
una prueba local puntual, respetar el orden seed -> actualizar telefono -> ping:

```bash
SEED=$(curl --silent --fail --request POST http://localhost:8000/ops/seed)
TRIP_ID=$(printf '%s' "$SEED" | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["trip_id"])')

docker compose exec backend python -c \
  'from app import db; db.x("UPDATE drivers SET phone=? WHERE id=?", ("+54911XXXXXXXX", "driver_01"))'

curl --fail --request POST http://localhost:8000/driver/ping \
  --header "Content-Type: application/json" \
  --data "{\"trip_id\":\"$TRIP_ID\",\"lat\":-34.5745,\"lon\":-58.366,\"speed\":20}"
```

No commitear un telefono personal. La solucion estable es leerlo desde una
variable `DEMO_WORKER_PHONE` en `/ops/seed`.

El `docker-compose.yml` actual fija `SIMULATE_CALLS: "1"`. Antes de la prueba
real debe cambiarse por `SIMULATE_CALLS: ${SIMULATE_CALLS:-1}`. Luego levantar
ngrok y habilitar llamadas reales:

```bash
SIMULATE_CALLS=0 SIMULATE_DISPATCH=1 \
  docker compose --profile voice up -d --build --force-recreate
```

Verificar antes de disparar:

```bash
curl http://localhost:4040/api/tunnels
curl https://example.ngrok-free.app/health
```

Reemplazar `example.ngrok-free.app` por `NGROK_DOMAIN`.

Finalmente ejecutar la secuencia seed -> actualizar telefono -> ping mostrada
arriba. No volver a llamar `/ops/seed` despues de actualizar el telefono porque
restaura el valor ficticio.

## Evitar llamadas duplicadas

- Crear un viaje nuevo para cada prueba.
- No repetir el mismo ping de llegada muchas veces.
- No ejecutar llegada y `port-ready` al mismo tiempo.
- Mantener `SIMULATE_CALLS=1` hasta terminar la configuracion de Twilio.
- Revisar saldo, numero destino y logs antes de habilitar llamadas reales.

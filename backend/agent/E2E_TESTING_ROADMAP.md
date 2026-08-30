# Roadmap de testing end-to-end

## Objetivo

Probar backend e integraciones como un sistema completo:

```text
API -> Redis -> detector -> RabbitMQ -> agente -> OpenAI
                                      -> dispatcher -> Resend
                                      -> Twilio/ngrok
                                      -> SQLite -> API ops
```

Web y mobile quedan fuera de este roadmap. Los pings del conductor se generan
por API o simulador.

La estrategia combina:

- Suite automatica para contratos, API, detector, RabbitMQ, agente y OpenAI.
- Smoke tests manuales para Twilio, ngrok y Resend reales.
- Defaults simulados para evitar llamadas y emails accidentales.

## Principio de ejecucion

Probar una frontera externa por vez:

1. Todo simulado.
2. Telefonia simulada + OpenAI real.
3. Resend real.
4. Twilio real + OpenAI real.

Si se habilitan todos los proveedores desde el inicio, un fallo no permite
saber que integracion lo produjo.

## Gate 0: corregir bloqueos conocidos

No ejecutar proveedores reales hasta cerrar estos puntos encontrados en el
codigo actual.

### Compose ignora los flags reales

`docker-compose.yml` fija:

```yaml
SIMULATE_CALLS: "1"
SIMULATE_DISPATCH: "1"
```

Debe usar:

```yaml
SIMULATE_CALLS: ${SIMULATE_CALLS:-1}
SIMULATE_DISPATCH: ${SIMULATE_DISPATCH:-1}
```

De lo contrario, ejecutar `SIMULATE_CALLS=0 docker compose ...` sigue simulando.

### Callback de Twilio cierra antes de tiempo

`caller.py` solicita callbacks para `initiated`, `ringing`, `answered` y
`completed`, pero `twilio_hooks.status` trata todo estado desconocido como
`failed` y llama al cierre idempotente.

Elegir una solucion:

- Recomendada: pedir solamente `status_callback_event=["completed"]`.
- Alternativa: ignorar estados no terminales en `/twilio/status/{call_id}`.

### Firma invalida en `/twilio/voice`

Twilio firma todos los parametros POST. `voice()` actualmente valida con `{}`.
Debe leer `await request.form()` y pasar esos parametros a `_validate_signature`.

### `call.finished` no cumple el schema

El publisher agrega `outcome` y `voice` al payload, pero
`event.schema.json` usa `additionalProperties: false` y no los admite.

Elegir una solucion y usarla en runtime, fixtures y tests:

- Recomendada: quitar `outcome` y `voice` del nivel superior; ya estan
  representados dentro de `report`.
- Alternativa: agregarlos formalmente al schema.

### Reset incompleto

`POST /ops/reset` no limpia Redis, RabbitMQ, drivers ni thresholds. La suite no
debe depender de ese endpoint para aislar casos. Usar volumenes nuevos o
`docker compose down -v` al iniciar la corrida completa.

### El seed usa un telefono ficticio

`POST /ops/seed` guarda `+5491100000000`. Antes del smoke real, leer el telefono
de prueba desde una variable como `DEMO_WORKER_PHONE`, con el valor ficticio
como default seguro. Pasar esa variable por Compose y no hardcodear un telefono
personal.

## Gate 1: preparar el harness automatico

### Dependencias de test

Agregar un extra de desarrollo a `backend/pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
    "pytest>=8",
    "jsonschema>=4.23",
]
```

`httpx` ya es dependencia de runtime.

### Estructura recomendada

```text
backend/tests/e2e/
  conftest.py
  test_health.py
  test_contracts.py
  test_arrival.py
  test_port_ready.py
  test_slowdown.py
  test_stopped.py
  test_dispatcher.py
  test_rabbitmq.py
scripts/e2e.sh
```

Helpers necesarios en `conftest.py`:

- Cliente HTTP con base `http://localhost:8000`.
- `seed_trip()` que devuelve el `trip_id` de esa prueba.
- `ping()` para enviar GPS.
- `poll()` con timeout para esperar resultados asincronos.
- Filtros por `trip_id`; nunca usar conteos globales.
- Carga y validacion de `backend/agent/event.schema.json`.
- Parser de `events[].payload`, que la API actualmente devuelve como string JSON.

No usar sleeps fijos para esperar llamadas. Hacer polling cada 250-500 ms con
timeout de 30-60 segundos y mostrar el ultimo response al fallar.

### Runner

`scripts/e2e.sh` debe:

1. Verificar que Docker este disponible.
2. Ejecutar `docker compose down -v`.
3. Levantar Redis, RabbitMQ y backend con simulacion segura.
4. Esperar `GET /ready`, no solamente `/health`.
5. Ejecutar pytest.
6. Guardar logs al fallar.
7. Apagar el stack en un trap, incluso si pytest falla.

No usar `start.sh` para la suite: crea datos y dispara una llegada antes de que
empiecen las aserciones.

## Capa 1: preflight estatico

Ejecutar antes de levantar el stack:

```bash
python3 -m json.tool backend/agent/event.schema.json >/dev/null
npx --yes ajv-cli@5 validate --spec=draft2020 \
  -s backend/agent/event.schema.json \
  -d "backend/agent/examples/*.json"
docker compose config --services
```

No ejecutar `docker compose config` completo en logs compartidos: expande los
secrets del `.env`.

Criterios:

- JSON Schema valido.
- Todos los fixtures cumplen el schema.
- Compose contiene `redis`, `rabbitmq`, `backend` y el profile `ngrok`.

## Capa 2: infraestructura y readiness

Modo seguro:

```bash
SIMULATE_CALLS=1 SIMULATE_DISPATCH=1 docker compose up -d --build
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
docker compose ps
```

Aserciones automaticas:

- `/health` devuelve `{"ok": true}`.
- `/ready` devuelve `ok=true` y `transport=rabbitmq`.
- No hay servicios unhealthy.
- RabbitMQ expone exchange `nextwave` durable.
- Existen `nextwave.workers`, `nextwave.dlx` y `nextwave.dead`.
- Redis responde `PONG`.

Credenciales de RabbitMQ para tests salen de env. Los defaults actuales son
`nextwave` / `nextwave-dev`, no `guest` / `guest`.

## Capa 3: baseline de API

Con volumenes limpios:

1. `POST /ops/seed` una sola vez.
2. `GET /driver/{driver_id}/trip` devuelve ese viaje.
3. `GET /ops/trips` contiene ese `trip_id`.
4. `GET /ops/calls` y `/ops/alerts` empiezan vacios.
5. `GET /ops/thresholds` devuelve las cinco reglas.
6. Un ping fuera del puerto queda persistido.

No afirmar el status devuelto inmediatamente por `/driver/ping`: el detector
procesa la cola de Redis de forma asincrona. Esperar el estado mediante
`GET /ops/trips/{trip_id}`.

## Capa 4: flujos deterministas sin OpenAI

Esta capa valida orquestacion y fallback. Levantar backend con:

```bash
OPENAI_API_KEY= SIMULATE_CALLS=1 SIMULATE_DISPATCH=1 \
  docker compose up -d --force-recreate backend
```

### Llegada

1. Crear viaje.
2. Enviar ping fuera del geofence.
3. Enviar ping dentro del puerto.
4. Esperar llamada terminal.

Afirmar por `trip_id`:

- Un evento `truck.arrived`.
- Una llamada `arrival_check` con status `done`.
- Transcript no vacio.
- Un evento `call.finished`.
- Reporte con los campos requeridos y `needs_human=true` por fallback.

### Puerto habilitado

1. Reutilizar un viaje que ya llego.
2. Ejecutar `POST /ops/trips/{trip_id}/port-ready`.
3. Esperar una segunda llamada terminal.

Afirmar:

- Un evento `port.ready`.
- Una llamada `load_authorized`.
- Estado final compatible con el outcome.
- Dos llamadas totales para ese viaje.

### Frenada

1. Crear viaje lejos del puerto.
2. Enviar velocidad alta.
3. Enviar velocidad suficientemente baja para superar el threshold.

Afirmar:

- Un evento `truck.slowdown`.
- Una alerta `media` inmediata.
- Una llamada `emergency`.
- Un `call.finished` con reporte `medium` o mayor.

### Parada sin frenada

No usar el simulador actual para esta asercion: primero acelera y luego pasa a
cero, lo que tambien dispara slowdown.

1. Bajar temporalmente `stop_min_seconds` para el test.
2. Crear viaje lejos del puerto.
3. Enviar solo pings de baja velocidad durante la ventana requerida.
4. Restaurar el threshold al terminar.

Afirmar:

- Un evento `truck.stopped`.
- Una alerta `alta`.
- Una sola llamada `emergency`.

### Regresion frenada seguida de parada

Agregar un caso separado que reproduzca velocidad alta -> cero -> permanencia
detenida. El resultado correcto es una sola llamada de emergencia para el mismo
incidente. Marcarlo `xfail` hasta que exista deduplicacion cruzada entre
`truck.slowdown` y `truck.stopped`.

## Capa 5: OpenAI real con telefonia simulada

Esta es la primera prueba que debe ejecutarse ahora que existe
`OPENAI_API_KEY`. Mantener Twilio y Resend simulados.

Recrear backend para que lea el `.env` actualizado:

```bash
docker compose up -d --build --force-recreate backend
docker compose exec backend python -c \
  'from app.agent.brain import client; print("openai_configured=", client is not None)'
```

El comando confirma presencia sin imprimir la key.

Ejecutar `llegada`, `frenada` y `parada`. Para respuestas del modelo no afirmar
texto exacto. Validar solo por salidas observables:

- Transcript con al menos una respuesta no vacia del agente.
- Llamada en estado terminal dentro del timeout.
- `outcome.available`: boolean o null.
- `outcome.eta_min`: numero no negativo o null.
- `outcome.needs_human`: booleano.
- Metricas `stress`, `fatigue`, `clarity` y `risk` entre 0 y 1.
- Maximo dos turnos del trabajador.
- `call.finished.payload.report` cumple el JSON Schema.
- El reporte conserva `operation_id`, `worker_id`, ubicacion y evento original.

Control de costo:

- Ejecutar un caso de cada tipo, no loops abiertos.
- Guardar modelo, tokens y costo estimado de cada llamada.
- Si OpenAI devuelve rate limit o timeout, el test debe verificar fallback y
  marcar el proveedor como degradado, no romper el bus.

## Capa 6: dispatcher

### Automatica, simulada

Con `SIMULATE_DISPATCH=1`:

- `baja` persiste sin email.
- `media` y `alta` persisten con canal `email,dashboard`.
- Logs muestran `status=simulated`.
- Redelivery del mismo `event_id` no duplica el intento de email.

Hay que decidir si alertas SQLite duplicadas son aceptables. Actualmente el
lock cubre el email, pero `_save` ocurre antes del lock y puede insertar dos
filas ante redelivery.

### Smoke manual, Resend real

Solo despues de pasar la suite simulada:

```bash
SIMULATE_DISPATCH=0 SIMULATE_CALLS=1 \
  docker compose up -d --force-recreate backend
```

1. Confirmar que `ALERT_EMAIL_TO` pertenece a la cuenta o dominio verificado.
2. Disparar una sola alerta alta.
3. Verificar email recibido y `provider_id` en logs.
4. Repetir el mismo `event_id` y confirmar que no llega otro email.

## Capa 7: RabbitMQ resiliente

Pruebas automaticas:

1. Publicar un evento valido y comprobar su consumo.
2. Publicar un envelope con version desconocida y esperar en `nextwave.dead`.
3. Publicar JSON invalido y esperar en dead-letter.
4. Detener backend, publicar un mensaje persistente y volver a iniciarlo.
5. Confirmar que el mensaje pendiente se procesa tras el reinicio.
6. Reiniciar RabbitMQ y comprobar que backend reconecta.
7. Verificar que redelivery no duplica llamadas ni emails.

Toda asercion usa `event_id` unico. No depender de la cantidad global de
mensajes porque management conserva datos entre corridas si no se borran
volumenes.

## Capa 8: Twilio y ngrok real

Ejecutar solamente despues de corregir Gate 0.

### Preflight

1. Confirmar saldo y geo permissions de Twilio.
2. Verificar el telefono destino si la cuenta es trial.
3. Confirmar `TWILIO_FROM` con capacidad Voice.
4. Confirmar `NGROK_AUTHTOKEN`, `NGROK_DOMAIN` y `PUBLIC_URL`.
5. Mantener `SIMULATE_DISPATCH=1`.

Levantar:

```bash
SIMULATE_CALLS=0 SIMULATE_DISPATCH=1 \
  docker compose --profile voice up -d --build --force-recreate
curl --fail http://localhost:4040/api/tunnels
curl --fail https://example.ngrok-free.app/health
```

Reemplazar `example.ngrok-free.app` por el dominio configurado.

### Smoke atendido

1. Sembrar un viaje cuyo trabajador tenga el telefono real de prueba.
2. Disparar `port.ready` o un evento controlado.
3. Atender, responder una o dos preguntas y esperar el cierre.

Evidencias:

- `CallSid` y status `completed` en Twilio Console.
- Requests `voice`, `gather` y `status` con HTTP 200 en ngrok.
- Llamada `done` con transcript, outcome, costo y reporte.
- Un solo `call.finished`.

### Estados negativos

Ejecutar como smoke separado, no en cada corrida:

- No atender -> `no_answer`.
- Rechazar/ocupado -> `busy` si el carrier lo informa.
- Telefono invalido -> `failed`.
- Repetir callback terminal firmado -> no duplica el reporte.
- Request sin firma -> HTTP 403.

## Capa 9: persistencia y restart

1. Completar una llamada simulada.
2. Ejecutar `docker compose restart backend`.
3. Confirmar que viajes, eventos, llamadas y alertas siguen en API.
4. Confirmar `/ready` despues de reconectar.
5. Ejecutar otra llamada y verificar que los IDs previos no se pisan.

`docker compose down` debe conservar datos. `docker compose down -v` debe dejar
la siguiente corrida completamente limpia.

## Matriz de ejecucion

| Suite | Twilio | OpenAI | Resend | Frecuencia |
|---|---|---|---|---|
| contratos/API | simulado | sin key | simulado | cada cambio |
| detector/agente fallback | simulado | sin key | simulado | cada cambio |
| agente con modelo | simulado | real | simulado | antes de demo |
| dispatcher real | simulado | real o sin key | real | smoke unico |
| voz real | real | real | simulado | smoke controlado |
| demo completa | real | real | real | ensayo final unico |

## Evidencias de una corrida

Guardar en `artifacts/e2e/<timestamp>/`, sin commitear:

- Resultado de pytest.
- Logs de backend desde el inicio de la corrida.
- Responses JSON de trip, calls, alerts y metrics.
- Conteos de `nextwave.workers` y `nextwave.dead`.
- IDs: `trip_id`, `event_id`, `call_id`, `CallSid` y provider ID de Resend.
- Captura de Twilio Console para el smoke real.

Redactar API keys, auth tokens, telefonos completos y transcripts sensibles.

## Criterios de aprobacion

La app backend esta lista para demo cuando:

1. La suite automatica pasa tres veces consecutivas desde volumenes limpios.
2. Llegada, port-ready, frenada y parada producen los eventos esperados.
3. Cada evento operacional inicia como maximo una llamada.
4. Toda llamada terminal produce exactamente un `call.finished` valido.
5. OpenAI real devuelve shapes validos o activa fallback seguro.
6. Alertas se persisten y el email no se duplica.
7. RabbitMQ conserva mensajes y enruta invalidos a dead-letter.
8. Reiniciar backend no pierde datos ni rompe el consumer.
9. Una llamada real atendida completa voz -> OpenAI -> reporte.
10. Existe un comando para volver inmediatamente a modo simulado.

## Orden recomendado

1. Corregir Gate 0.
2. Crear harness y tests de contratos/readiness.
3. Automatizar llegada y port-ready.
4. Automatizar frenada y parada.
5. Ejecutar OpenAI real con telefonia simulada.
6. Probar RabbitMQ restart y DLQ.
7. Hacer smoke de Resend.
8. Hacer smoke de Twilio/ngrok.
9. Ejecutar ensayo final con evidencias.

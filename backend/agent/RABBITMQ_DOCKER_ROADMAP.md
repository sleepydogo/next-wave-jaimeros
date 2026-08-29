# Roadmap de RabbitMQ y Docker Compose

## Objetivo

Levantar Redis, RabbitMQ, backend y ngrok con Docker Compose, con defaults
seguros para desarrollo y un modo explicito para llamadas y emails reales.

## Estado actual

`docker-compose.yml` ya levanta Redis, RabbitMQ y backend. En Compose,
`RABBITMQ_URL` siempre esta definido, por lo que el bus usa RabbitMQ y no Redis
pub/sub.

Pendientes:

- RabbitMQ no tiene volumen persistente.
- Exchange y mensajes no son persistentes.
- Hay una sola queue y no existe dead-letter queue.
- Errores de handlers se capturan y el mensaje igual queda confirmado.
- Las conexiones no se cierran durante shutdown.
- Compose fuerza `SIMULATE_CALLS=1` y `PUBLIC_URL=http://localhost:8000`.
- Faltan ngrok, Resend y varias variables de configuracion.

## Topologia MVP

Con el monolito actual alcanza con:

```text
exchange: nextwave             type: fanout, durable
queue:    nextwave.workers     durable
dlx:      nextwave.dlx         durable
queue:    nextwave.dead        durable
```

No migrar a topic exchanges durante la hackathon. Si agente, dispatcher y
backend se separan en procesos, cada uno necesitara su propia queue; el contrato
JSON no cambia.

## Fase 1: robustecer RabbitMQ - P0

Cambios en `bus.py`:

1. Conservar la conexion y el channel para cerrarlos en shutdown.
2. Declarar exchange con `durable=True`.
3. Declarar queue durable con dead-letter exchange.
4. Publicar con `DeliveryMode.PERSISTENT`.
5. Configurar `prefetch_count` bajo, por ejemplo 10.
6. Loggear `event_id`, tipo y backend de transporte.
7. Validar `schema_version` antes de dispatch.
8. No confirmar un mensaje si un handler obligatorio fallo.

El punto 8 requiere que `_dispatch` devuelva o propague el fallo. El catch
actual evita que RabbitMQ pueda reintentar o mandar a dead-letter.

Para evitar loops infinitos, limitar retries mediante header o usar la dead
letter queue directamente para la demo.

Criterio de salida:

- Reiniciar backend no elimina mensajes persistentes pendientes.
- Un payload invalido termina en `nextwave.dead`.
- RabbitMQ management muestra exchange y ambas queues sanas.

## Fase 2: shutdown y readiness - P0

- Hacer que `bus.start()` devuelva una task y conserve recursos AMQP.
- Agregar `bus.stop()` para cancelar consumer y cerrar channel/conexion.
- En `lifespan`, cancelar y esperar tasks con `gather(..., return_exceptions=True)`.
- Exponer en `/health` si Redis y RabbitMQ estan disponibles, o agregar
  `/ready` para dependencias.
- No aceptar publishers hasta que `_amqp_ready` este activo.

Criterio de salida:

- `docker compose stop backend` no deja conexiones zombie.
- Backend no aparece ready antes de conectarse al broker.

## Fase 3: Compose objetivo - P0

Actualizar servicios:

### Redis

- Mantener healthcheck.
- Agregar volumen `redis-data:/data`.
- Ejecutar append-only para conservar locks/sesiones durante reinicios breves:
  `redis-server --appendonly yes`.

### RabbitMQ

- Mantener imagen management y healthcheck.
- Agregar volumen `rabbitmq-data:/var/lib/rabbitmq`.
- Configurar usuario y password desde `.env`.
- Exponer `15672` para inspeccion local.

### Backend

- Reemplazar valores hardcodeados por interpolacion de env.
- Pasar todas las variables de voz, OpenAI y dispatcher.
- Mantener `SIMULATE_CALLS=1` y `SIMULATE_DISPATCH=1` como defaults.
- Usar `PUBLIC_URL=https://${NGROK_DOMAIN}` en modo real.

### ngrok

Agregar un servicio bajo profile `voice`:

```yaml
  ngrok:
    image: ngrok/ngrok:3-alpine
    profiles: ["voice"]
    command: ["http", "--domain=${NGROK_DOMAIN}", "backend:8000"]
    environment:
      NGROK_AUTHTOKEN: ${NGROK_AUTHTOKEN}
    ports:
      - "4040:4040"
    depends_on:
      backend:
        condition: service_healthy
```

El dominio estatico se obtiene desde el dashboard de ngrok. `PUBLIC_URL` debe
ser exactamente `https://${NGROK_DOMAIN}`.

## Variables objetivo

Agregar a `.env.example`:

```dotenv
# broker
RABBITMQ_USER=nextwave
RABBITMQ_PASSWORD=nextwave-dev

# tunnel
NGROK_AUTHTOKEN=
NGROK_DOMAIN=CHANGEME.ngrok-free.app

# external effects: safe by default
SIMULATE_CALLS=1
SIMULATE_DISPATCH=1

# Twilio Voice
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM=
VALIDATE_TWILIO_SIGNATURE=1

# OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# Resend
RESEND_API_KEY=
ALERT_EMAIL_FROM="NextWave <onboarding@resend.dev>"
ALERT_EMAIL_TO=
```

Los valores reales viven en `.env`, que no se commitea.

## Comandos operativos

Modo seguro, sin llamadas ni emails:

```bash
docker compose up -d --build
docker compose logs -f backend
```

Modo voz real con ngrok:

```bash
SIMULATE_CALLS=0 docker compose --profile voice up -d --build
docker compose logs -f backend ngrok
```

Modo voz y email reales:

```bash
SIMULATE_CALLS=0 SIMULATE_DISPATCH=0 \
  docker compose --profile voice up -d --build
```

Inspeccion:

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:4040/api/tunnels
open http://localhost:15672
```

Apagar conservando datos:

```bash
docker compose down
```

Borrar todo solo de forma explicita:

```bash
docker compose down -v
```

## Fase 4: smoke test completo - P0

1. Copiar `.env.example` a `.env` y completar secrets.
2. Levantar modo seguro y ejecutar escenario `parada`.
3. Confirmar eventos en RabbitMQ y datos en `/ops/*`.
4. Reiniciar backend durante un evento pendiente.
5. Levantar profile `voice` y verificar URL publica.
6. Hacer una llamada real atendida.
7. Disparar una alerta alta y verificar email.
8. Repetir evento/callback y comprobar idempotencia.

## Orden recomendado

1. Compose parametrizado y volumenes.
2. RabbitMQ durable y shutdown limpio.
3. ngrok profile `voice`.
4. Twilio real.
5. Resend real.
6. Dead-letter y pruebas de fallo.

## Definicion de terminado

- `docker compose up` levanta un entorno seguro sin secrets.
- El profile `voice` publica backend por HTTPS.
- RabbitMQ conserva mensajes y expone dead letters.
- Redis conserva sesiones durante reinicios breves.
- Una variable permite cambiar entre simulacion y efectos reales.
- `docker compose down` apaga conexiones limpiamente.

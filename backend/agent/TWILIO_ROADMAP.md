# Roadmap de Twilio Voice + OpenAI

## Objetivo

Realizar una llamada saliente al trabajador, transcribir su respuesta con
Twilio `<Gather>`, obtener la siguiente respuesta desde OpenAI y publicar un
`call.finished` valido al terminar.

Twilio Voice no depende de Twilio WhatsApp. No hay que esperar aprobacion de
WhatsApp para hacer llamadas.

## Arquitectura decidida

```text
evento -> caller.start -> Twilio Voice -> /twilio/voice
                                      -> /twilio/gather -> OpenAI
                                      -> /twilio/status -> call.finished
```

Se conserva `<Gather input="speech">`. OpenAI Realtime y Media Streams quedan
fuera del MVP porque agregan streaming, WebSockets y mas puntos de fallo.

## Estado actual

Ya existen:

- Llamada saliente en `app/agent/caller.py`.
- Sesion de llamada en Redis con TTL de una hora.
- Webhooks `voice`, `gather` y `status`.
- TwiML con `<Say>`, `<Gather>` y `<Hangup>`.
- Brain OpenAI, modo simulado, costos e idempotencia de cierre.

Pendiente antes de una llamada real:

- Probar credenciales, numero y permisos geograficos.
- Evitar que el cliente Twilio sincronico bloquee el event loop.
- Cerrar correctamente si `calls.create` falla.
- Validar firmas de webhooks.
- Confirmar callbacks para `failed`, `busy` y `no-answer`.
- Probar la URL publica desde ngrok en Compose.

## Fase 1: preparar Twilio - P0

En Twilio Console:

1. Crear o usar un proyecto.
2. Comprar un numero con capacidad `Voice`.
3. Habilitar permisos geograficos para el pais destino.
4. Si la cuenta es trial, verificar el telefono receptor.
5. Copiar Account SID, Auth Token y numero origen.

Configurar `.env` sin commitearlo:

```dotenv
SIMULATE_CALLS=0
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_FROM=+15551234567
OPENAI_API_KEY=sk-xxxxxxxx
OPENAI_MODEL=gpt-4o-mini
NGROK_AUTHTOKEN=xxxxxxxx
NGROK_DOMAIN=example.ngrok-free.app
PUBLIC_URL=https://example.ngrok-free.app
```

El telefono del trabajador viene del evento enriquecido en formato E.164.

Criterio de salida:

- Twilio Console permite llamar al pais y telefono de prueba.
- `PUBLIC_URL/health` responde por HTTPS desde fuera de Docker.

## Fase 2: endurecer el inicio de llamada - P0

Cambios en `caller.py`:

1. Validar evento y telefono antes de crear la llamada en Twilio.
2. Ejecutar el SDK sincronico con `await asyncio.to_thread(...)`.
3. Capturar excepciones de `calls.create`.
4. Ante error, llamar `finish(call_id, status="failed")`.
5. Guardar el SID devuelto por Twilio para trazabilidad.
6. Configurar callback terminal y metodo `POST` explicitamente.

No loggear el telefono completo. Mostrar solo los ultimos cuatro digitos.

Criterio de salida:

- Un fallo al marcar produce `call.finished` con status `failed`.
- El consumer del bus no queda bloqueado durante la llamada a la API.

## Fase 3: asegurar webhooks - P0

Cambios en `twilio_hooks.py`:

1. Validar `X-Twilio-Signature` con `RequestValidator`.
2. Reconstruir la URL usando `PUBLIC_URL`, no el hostname interno de Docker.
3. Rechazar firma invalida con HTTP 403.
4. Permitir desactivar validacion solo con una variable explicita para tests:

```dotenv
VALIDATE_TWILIO_SIGNATURE=1
```

5. Manejar sesion inexistente sin excepciones y cerrar con TwiML valido.
6. Limitar repreguntas vacias para evitar un loop de `<Gather>`.

Criterio de salida:

- Requests falsos reciben 403.
- Los callbacks reales de Twilio reciben 200 y XML valido.
- Todo texto dentro de `<Say>` esta escapado.

## Fase 4: estados terminales e idempotencia - P0

El callback `/status/{call_id}` mapea:

| Twilio | Interno |
|---|---|
| `completed` | `done` |
| `failed` | `failed` |
| `no-answer` | `no_answer` |
| `busy` | `busy` |

Acciones:

- Confirmar en una llamada real que llega el callback terminal.
- Mantener `state.once("call:{call_id}:finish", ttl=86400)`.
- Hacer que un callback repetido devuelva 200 sin duplicar reporte.
- Conservar la sesion hasta terminar de construir `call.finished`.
- Guardar `CallSid`, `CallDuration` y status recibido.

Criterio de salida:

- Cada intento produce exactamente un reporte.
- Repetir manualmente el callback no crea otro `call.finished`.

## Fase 5: calidad de conversacion - P1

- Mantener maximo dos preguntas.
- Usar frases breves y sin markdown.
- Probar `language="es-AR"` en `<Gather>`.
- Comparar la voz actual `Polly.Mia` con una voz disponible en la cuenta.
- Medir latencia entre fin de voz y respuesta del agente.
- Si OpenAI falla, cerrar con fallback y `needs_human=true`.

No migrar a Realtime aunque la pausa entre turnos sea visible. Para la demo,
priorizar un flujo predecible sobre una conversacion perfectamente natural.

## Fase 6: smoke tests - P0

Ejecutar en este orden:

1. `SIMULATE_CALLS=1`: escenario completo sin Twilio.
2. `SIMULATE_CALLS=0`: llamada atendida y una respuesta.
3. No atender: debe terminar `no_answer`.
4. Telefono invalido: debe terminar `failed`.
5. Desactivar OpenAI: debe usar fallback sin perder el reporte.
6. Reenviar callback de status: no debe duplicar el cierre.

Verificar despues de cada caso:

- `/ops/calls` contiene status, transcript y costo.
- El timeline contiene `call.finished`.
- Un caso de riesgo publica `alert.raised`.
- Los logs correlacionan `event_id`, `call_id` y `CallSid`.

## Plan de contingencia para la demo

- Mantener `SIMULATE_CALLS=1` listo para activar.
- Grabar una llamada real exitosa antes de presentar.
- Tener un telefono verificado y con senal.
- Revisar saldo, geo permissions y ngrok 30 minutos antes.
- No cambiar prompts ni voces despues del ensayo final.

## Definicion de terminado

- Una llamada real atendida genera un reporte completo.
- `failed`, `busy` y `no_answer` tambien generan reporte.
- Webhooks rechazan firmas invalidas.
- No existe dependencia con Twilio WhatsApp.
- El modo simulado sigue funcionando sin credenciales.

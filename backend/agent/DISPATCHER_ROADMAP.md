# Roadmap del dispatcher

## Objetivo

Consumir `alert.raised`, guardar la alerta para el dashboard y enviar por email
los casos relevantes. WhatsApp queda fuera del MVP: Twilio se usa solo para
llamadas de voz.

## Estado actual

`backend/app/dispatcher/worker.py` ya:

- Consume `alert.raised`.
- Persiste alertas en SQLite.
- Enruta por severidad.
- Simula email con un log.

Problemas a resolver:

- La rama WhatsApp usa `ALERT_EMAIL` como telefono y no debe ejecutarse.
- Email todavia no tiene proveedor real.
- No hay validacion formal de `alert.raised`.
- No se registra si el envio termino, fallo o fue simulado.
- `_send` es sincronica y mezcla todos los canales.

## Alcance decidido

| Severidad | Dashboard | Email |
|---|---|---|
| `baja` | si | no |
| `media` | si | si |
| `alta` | si | si |

El dashboard equivale a persistir la alerta. El email real se envia con Resend
usando HTTP y `httpx`; no hace falta agregar otro SDK.

## Contrato de entrada

Agregar `alert.raised` a `backend/agent/event.schema.json`:

```json
{
  "schema_version": 1,
  "event_id": "evt_alert_001",
  "type": "alert.raised",
  "payload": {
    "trip_id": "op_123",
    "severity": "alta",
    "title": "Posible fatiga del trabajador",
    "body": "El agente recomienda intervencion humana.",
    "call_id": "call_789",
    "report_id": "report_abc123"
  },
  "ts": 1787990460.0
}
```

Requeridos: `trip_id`, `severity`, `title`, `body`. `call_id` y `report_id` son
opcionales para alertas que no nacen de una llamada.

## Fase 1: limpiar responsabilidades - P0

1. Eliminar WhatsApp de `ROUTING` y de `_send`.
2. Separar funciones: `_save`, `_send_email` y `on_alert`.
3. Validar los campos requeridos antes de persistir.
4. Escapar o truncar texto excesivo antes del email.
5. Mantener el handler async y usar `httpx.AsyncClient`.

Criterio de salida:

- `baja` solo aparece en `/ops/alerts`.
- `media` y `alta` intentan email una sola vez.
- Un payload invalido se loggea y no tumba el bus.

## Fase 2: integrar Resend - P0

Agregar a `config.py` y `.env.example`:

```dotenv
SIMULATE_DISPATCH=1
RESEND_API_KEY=
ALERT_EMAIL_FROM="NextWave <onboarding@resend.dev>"
ALERT_EMAIL_TO=equipo@example.com
```

Reglas:

- `SIMULATE_DISPATCH=1` es el default y solo loggea.
- Sin API key o destinatario, usar fallback simulado y emitir `warning`.
- En modo real, hacer `POST https://api.resend.com/emails` con timeout corto.
- Nunca loggear `RESEND_API_KEY` ni el body completo si contiene datos sensibles.
- Durante la demo se puede usar `onboarding@resend.dev` y el email propietario
  de la cuenta. Un destinatario externo requiere verificar dominio en Resend.

Criterio de salida:

- Un `alert.raised` de severidad alta llega al email configurado.
- Un error de Resend no revierte la alerta persistida.
- El flujo funciona sin internet con `SIMULATE_DISPATCH=1`.

## Fase 3: idempotencia y estado - P0

Antes de enviar:

```python
await state.once(f"dispatch:{event_id}:email", ttl=86400)
```

Guardar o publicar el resultado del intento:

```json
{
  "channel": "email",
  "status": "sent",
  "provider_id": "resend_message_id"
}
```

Para la hackathon alcanza con agregar al log `event_id`, canal y estado. Si la
UI necesita mostrar entrega, acordar con backend columnas `delivery_status` y
`provider_id`, o un evento `alert.dispatched`; no implementar ambos.

Criterio de salida:

- Redelivery del mismo `event_id` no duplica emails.
- Se distingue `sent`, `failed` y `simulated` en logs.

## Fase 4: pruebas - P0

Casos minimos:

| Caso | Resultado |
|---|---|
| alerta `baja` | persiste, no envia email |
| alerta `media` | persiste y envia/simula email |
| alerta `alta` | persiste y envia/simula email |
| evento duplicado | un solo email |
| Resend devuelve error | alerta persiste, handler sigue vivo |
| falta API key | fallback simulado |

Smoke test manual:

1. Levantar Compose con `SIMULATE_DISPATCH=1`.
2. Ejecutar el escenario `parada`.
3. Verificar `/ops/alerts` y logs del dispatcher.
4. Cambiar a `SIMULATE_DISPATCH=0` y repetir con Resend configurado.

## Fuera del MVP

- Twilio WhatsApp.
- SMS, Slack y escalamiento multicanal.
- Reintentos complejos o colas por proveedor.
- Templates HTML avanzados.
- Preferencias de notificacion por usuario.

## Definicion de terminado

- Dashboard siempre conserva la alerta.
- Alertas `media` y `alta` generan como maximo un email.
- La demo funciona con Resend real y con fallback simulado.
- Ninguna credencial queda en codigo, logs o commits.

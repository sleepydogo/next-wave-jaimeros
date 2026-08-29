"""Persiste alertas y las entrega por email cuando corresponde.

El dashboard es SQLite. Resend es opcional y queda simulado por defecto.
"""
import logging
import time

import httpx

from .. import bus, db, events
from ..config import ALERT_EMAIL_FROM, ALERT_EMAIL_TO, RESEND_API_KEY, SIMULATE_DISPATCH
from ..state import once

log = logging.getLogger("dispatcher")

# que canales se usan segun severidad
ROUTING = {"alta": ["email", "dashboard"], "media": ["email", "dashboard"],
           "baja": ["dashboard"]}


def _text(value, limit):
    return str(value or "").strip()[:limit]


def _save(payload, severity):
    db.x("INSERT INTO alerts (trip_id,severity,title,body,channels,ts) VALUES (?,?,?,?,?,?)",
         (payload.get("trip_id"), severity, _text(payload.get("title"), 240),
          _text(payload.get("body"), 2000), "email,dashboard" if severity in ("alta", "media") else "dashboard", time.time()))


async def _send_email(payload, event_id):
    if not await once(f"dispatch:{event_id}:email", ttl=86400):
        return "duplicate", None
    if SIMULATE_DISPATCH or not RESEND_API_KEY or not ALERT_EMAIL_TO:
        log.warning("EMAIL simulado a %s | [%s] %s", ALERT_EMAIL_TO or "sin destinatario",
                    payload["severity"], _text(payload["title"], 240))
        return "simulated", None
    body = {"from": ALERT_EMAIL_FROM, "to": [ALERT_EMAIL_TO],
            "subject": f"[{payload['severity'].upper()}] {_text(payload['title'], 160)}",
            "text": _text(payload.get("body"), 4000)}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post("https://api.resend.com/emails",
                                         headers={"Authorization": f"Bearer {RESEND_API_KEY}"}, json=body)
            response.raise_for_status()
        provider_id = response.json().get("id")
        log.info("email enviado event_id=%s provider_id=%s", event_id, provider_id)
        return "sent", provider_id
    except Exception:
        log.exception("resend fallo event_id=%s", event_id)
        return "failed", None


@bus.on(events.ALERT_RAISED)
async def on_alert(p, msg=None):
    sev = p.get("severity", "media")
    if sev not in ROUTING or not p.get("trip_id") or not p.get("title") or "body" not in p:
        log.error("alerta invalida event_id=%s", (msg or {}).get("event_id"))
        return
    event_id = (msg or {}).get("event_id", events.new_id("alert"))
    _save(p, sev)
    if "email" in ROUTING[sev]:
        status, provider_id = await _send_email(p, event_id)
        log.info("dispatch event_id=%s channel=email status=%s provider_id=%s",
                 event_id, status, provider_id or "-")

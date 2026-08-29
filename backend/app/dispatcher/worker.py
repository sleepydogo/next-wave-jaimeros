"""Saca las alertas por los canales que no son voz: mail, whatsapp, etc.

En MVP todo queda registrado en SQLite y se ve en el dashboard. WhatsApp sale
de verdad si hay credenciales de Twilio y SIMULATE_CALLS=0.
"""
import logging
import time

from .. import bus, db, events
from ..config import (ALERT_EMAIL, SIMULATE_CALLS, TWILIO_ACCOUNT_SID,
                      TWILIO_AUTH_TOKEN, TWILIO_FROM)

log = logging.getLogger("dispatcher")

# que canales se usan segun severidad
ROUTING = {"alta": ["email", "whatsapp", "dashboard"],
           "media": ["email", "dashboard"],
           "baja": ["dashboard"]}


@bus.on(events.ALERT_RAISED)
async def on_alert(p, msg=None):
    sev = p.get("severity", "media")
    channels = ROUTING.get(sev, ["dashboard"])
    db.x("INSERT INTO alerts (trip_id,severity,title,body,channels,ts) VALUES (?,?,?,?,?,?)",
         (p.get("trip_id"), sev, p["title"], p.get("body", ""), ",".join(channels), time.time()))
    for ch in channels:
        _send(ch, p)


def _send(channel, p):
    if channel == "email":
        # MVP: log. En prod -> SES/Resend.
        log.warning("EMAIL a %s | [%s] %s :: %s", ALERT_EMAIL, p["severity"], p["title"], p.get("body", ""))
    elif channel == "whatsapp":
        if SIMULATE_CALLS or not TWILIO_ACCOUNT_SID:
            log.warning("WHATSAPP (simulado) | [%s] %s", p["severity"], p["title"])
            return
        try:
            from twilio.rest import Client
            Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN).messages.create(
                from_=f"whatsapp:{TWILIO_FROM}", to=f"whatsapp:{ALERT_EMAIL}",
                body=f"[{p['severity'].upper()}] {p['title']}\n{p.get('body', '')}")
        except Exception:
            log.exception("whatsapp fallo")

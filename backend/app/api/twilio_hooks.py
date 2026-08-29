"""Webhooks de Twilio: aca ocurre la conversacion real por telefono.

Flujo: Twilio llama -> /voice devuelve TwiML con <Gather input="speech">
-> el conductor habla -> Twilio postea el texto a /gather -> el brain responde
-> se repite hasta done -> /status cierra y calcula el costo.
"""
import time
from xml.sax.saxutils import escape

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from ..agent import caller
from ..config import PUBLIC_URL

router = APIRouter(prefix="/twilio", tags=["twilio"])

VOICE = 'voice="Polly.Mia" language="es-MX"'


def _twiml(xml: str):
    return Response(content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{xml}</Response>',
                    media_type="application/xml")


def _ask(call_id: str, text: str):
    return _twiml(
        f'<Gather input="speech" language="es-AR" speechTimeout="auto" '
        f'action="{PUBLIC_URL}/twilio/gather/{call_id}" method="POST">'
        f'<Say {VOICE}>{escape(text)}</Say></Gather>'
        f'<Say {VOICE}>No te escuche. Te vuelvo a llamar en un rato.</Say>')


def _bye(text: str):
    return _twiml(f'<Say {VOICE}>{escape(text)}</Say><Hangup/>')


@router.post("/voice/{call_id}")
async def voice(call_id: str):
    s = await caller.load_session(call_id)
    if not s:
        return _bye("Hubo un problema con la llamada. Perdon.")
    s["last_ts"] = time.time()
    await caller.save_session(call_id, s)
    return _ask(call_id, s["history"][0]["content"])


@router.post("/gather/{call_id}")
async def gather(call_id: str, SpeechResult: str = Form(default=""),
                 Confidence: float = Form(default=0.0)):
    s = await caller.load_session(call_id)
    latency = time.time() - s["last_ts"] if s else 2.0
    if not SpeechResult:
        return _ask(call_id, "Perdon, no te escuche bien. Me repetis?")
    reply, done = await caller.turn(call_id, SpeechResult, latency, Confidence or None)
    return _bye(reply) if done else _ask(call_id, reply)


@router.post("/status/{call_id}")
async def status(call_id: str, request: Request):
    form = await request.form()
    dur = float(form.get("CallDuration") or 0) or None
    await caller.finish(call_id, dur)
    return {"ok": True}

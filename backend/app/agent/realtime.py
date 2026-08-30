"""Puente de audio entre Twilio Media Streams y OpenAI Realtime.

El conductor habla -> Twilio manda audio g711 ulaw por WebSocket -> lo reenviamos
a OpenAI Realtime -> OpenAI responde con audio -> lo devolvemos a Twilio.

La diferencia con `<Gather>` es que no hay turnos rigidos: OpenAI detecta cuando
el conductor empieza a hablar (server VAD) y ahi cortamos el audio que estabamos
reproduciendo. Por eso se lo puede interrumpir en cualquier momento.
"""
import asyncio
import base64
import json
import logging

import websockets

from ..config import (AGENT_NAME, OPENAI_API_KEY, OPENAI_REALTIME_MODEL,
                      REALTIME_VOICE)

log = logging.getLogger("realtime")

URL = "wss://api.openai.com/v1/realtime?model={}"

INSTRUCCIONES = """Sos {agente}, de la oficina de logistica de una empresa de
transporte de contenedores en Argentina. Estas llamando por telefono a {nombre},
un camionero. Hablas castellano rioplatense, de vos.

Objetivo de la llamada: {objetivo}
Datos del viaje: contenedor {contenedor}, puerto {puerto}. {detalle}

Como hablas:
- Arranca diciendo solamente "Hola?" y espera a que te conteste. No te presentes
  todavia. Reciendespues de que responda, presentate: "Hola {nombre}, como estas?
  Te hablo de la empresa, soy {agente}."
- Una idea por frase. Frases cortas, como habla la gente por telefono.
- Si te interrumpe, callate y escuchalo. Nunca sigas hablando encima.
- Reacciona a lo que te dice antes de preguntar otra cosa. Si te dice que esta
  cansado, reconocelo primero.
- No leas direcciones completas, codigos postales ni el contenedor letra por
  letra. Decilo natural: "en Corrientes al mil".
- Nunca digas que sos una inteligencia artificial, un bot ni un asistente.
- Maximo dos preguntas. Cuando tengas la respuesta, despedite y cerra.
"""

OBJETIVOS = {
    "arrival_check": "saber si ya esta disponible para recibir la carga, y si no, en cuantos minutos.",
    "load_authorized": "avisarle que el puerto habilito la carga y que puede pasar a cargar.",
    "emergency": "entender por que se detuvo o freno, si necesita ayuda, y si puede seguir.",
}


def _instructions(session):
    ctx = session.get("ctx", {})
    nombre = str(ctx.get("name", "")).split()[0] if ctx.get("name") else "el conductor"
    return INSTRUCCIONES.format(
        agente=AGENT_NAME, nombre=nombre,
        objetivo=OBJETIVOS.get(session.get("reason"), OBJETIVOS["arrival_check"]),
        contenedor=ctx.get("container", ""), puerto=ctx.get("port", ""),
        detalle=ctx.get("detail", ""))


def _session_update(session):
    """Config de la sesion: audio telefonico en los dos sentidos y VAD del server."""
    return {"type": "session.update", "session": {
        "type": "realtime",
        "output_modalities": ["audio"],
        "audio": {
            # pcmu == g711 ulaw 8kHz, que es exactamente lo que manda Twilio:
            # asi no hay que transcodificar nada en el medio
            "input": {"format": {"type": "audio/pcmu"},
                      "turn_detection": {"type": "server_vad", "silence_duration_ms": 500},
                      "transcription": {"model": "whisper-1"}},
            "output": {"format": {"type": "audio/pcmu"}, "voice": REALTIME_VOICE},
        },
        "instructions": _instructions(session),
    }}


async def bridge(twilio_ws, session):
    """Conecta los dos WebSockets hasta que se corte la llamada.

    Devuelve el transcript de la conversacion para armar el reporte.
    """
    if not OPENAI_API_KEY:
        log.error("no hay OPENAI_API_KEY, no se puede usar realtime")
        return []

    transcript = []
    stream_sid = None

    async with websockets.connect(
        URL.format(OPENAI_REALTIME_MODEL),
        additional_headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        max_size=None,
    ) as oai:
        await oai.send(json.dumps(_session_update(session)))
        # que hable primero el agente, sin esperar a que el conductor diga nada
        await oai.send(json.dumps({"type": "response.create"}))

        async def de_twilio_a_openai():
            nonlocal stream_sid
            async for raw in twilio_ws.iter_text():
                msg = json.loads(raw)
                if msg["event"] == "start":
                    stream_sid = msg["start"]["streamSid"]
                    log.info("stream %s abierto", stream_sid)
                elif msg["event"] == "media":
                    await oai.send(json.dumps({"type": "input_audio_buffer.append",
                                               "audio": msg["media"]["payload"]}))
                elif msg["event"] == "stop":
                    log.info("stream %s cerrado", stream_sid)
                    break

        async def de_openai_a_twilio():
            async for raw in oai:
                ev = json.loads(raw)
                tipo = ev.get("type", "")

                # audio del agente -> Twilio (los dos nombres segun version de la API)
                if tipo in ("response.output_audio.delta", "response.audio.delta"):
                    if stream_sid:
                        await twilio_ws.send_json({
                            "event": "media", "streamSid": stream_sid,
                            "media": {"payload": ev["delta"]}})

                # el conductor empezo a hablar: cortar lo que estabamos diciendo.
                # sin este clear, Twilio sigue reproduciendo el audio ya enviado
                # y el agente le habla encima.
                elif tipo == "input_audio_buffer.speech_started":
                    if stream_sid:
                        await twilio_ws.send_json({"event": "clear", "streamSid": stream_sid})
                    await oai.send(json.dumps({"type": "response.cancel"}))

                elif tipo in ("response.output_audio_transcript.done",
                              "response.audio_transcript.done"):
                    transcript.append(f"AGENTE: {ev.get('transcript', '')}")
                elif tipo == "conversation.item.input_audio_transcription.completed":
                    transcript.append(f"CONDUCTOR: {ev.get('transcript', '')}")
                elif tipo == "error":
                    log.error("openai realtime: %s", ev.get("error"))

        try:
            await asyncio.gather(de_twilio_a_openai(), de_openai_a_twilio())
        except Exception:
            log.exception("el puente de audio se corto")

    return transcript


def base64_len(payload):
    """Bytes de audio reales detras del base64. 8000 bytes = 1 segundo en ulaw."""
    return len(base64.b64decode(payload))

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
                      INTERRUPT_AFTER_S, REALTIME_EAGERNESS,
                      REALTIME_SPEED, REALTIME_VOICE)
from . import voice_signals

log = logging.getLogger("realtime")

# Whisper, cuando le mandan silencio o ruido, inventa frases que vio en su
# entrenamiento: subtitulos, creditos, URLs. No son cosas que dijo el conductor.
ALUCINACIONES = ("www.", "http", "subtitul", "amara.org", "gracias por ver",
                 "suscrib", ".com", "editor de")

# errores que son parte del flujo normal y no hay que mostrarle a nadie
ERRORES_BENIGNOS = ("response_cancel_not_active", "conversation_already_has_active_response")


def _es_alucinacion(texto):
    t = (texto or "").strip().lower()
    return not t or any(m in t for m in ALUCINACIONES)

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
- UNA sola pregunta por turno, y despues te callas. Nunca encadenes dos
  preguntas en la misma intervencion.
- Nunca agregues condicionales del tipo "y si no, decime cuanto tardas" o
  "avisame si necesitas algo": eso va en el turno siguiente, si hace falta.
  Preguntas cerradas primero; el detalle se pide despues de escuchar la respuesta.
- Maximo dos preguntas en toda la llamada. Cuando tengas la respuesta, despedite
  y cerra.

Como suena tu voz (esto es tan importante como lo que decis):
- Firme y resolutiva. Sos la que coordina la operacion y se nota: hablas con
  seguridad, vas al punto y no pedis permiso para preguntar.
- Cordial pero nunca sumisa. Nada de "perdon que te moleste", "seria posible",
  "cuando puedas", "si no es mucha molestia". Preguntas directo.
- Frases afirmativas y en presente. "Necesito saber si estas listo" antes que
  "queria consultarte si por casualidad estarias disponible".
- Igual sos humana, no un sargento: calida con el conductor, agil si son buenas
  noticias, y bajas un cambio si suena cansado o preocupado.
- Cerras vos la conversacion cuando ya tenes la respuesta. No te quedes
  esperando que el otro decida cuando termina.
- Usa pausas cortas de verdad, y arranques dubitativos donde caigan naturales:
  "eh", "mira", "dale", "bueno", "ah, perfecto".
- No pronuncies cada palabra perfecta: uni las palabras como en el habla real.
- Cuando el conductor te da una respuesta, podes reaccionar con dos o tres
  palabras ("ah, buenisimo", "dale") y seguir en la MISMA intervencion.
- Prohibido narrar lo que estas haciendo o hacer tiempo. Nada de "dejame
  ubicarme", "un segundo", "estoy viendo", "dejame chequear". Una persona no
  dice eso por telefono: o pregunta, o se calla.
- Nunca hables dos veces seguidas. Decis lo tuyo y esperas la respuesta.
- Nunca leas de corrido varias frases seguidas: decis una idea y hacés silencio
  para que el otro conteste.
"""

OBJETIVOS = {
    "arrival_check": "saber si ya esta disponible para recibir la carga. Solo si te dice"
                     " que NO, recien ahi preguntale en cuantos minutos calcula estar listo.",
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


def _session_update(session, fmt="audio/pcmu", rate=None):
    """Config de la sesion. `fmt` cambia segun quien este del otro lado:

    - audio/pcmu  -> Twilio (g711 ulaw 8kHz), el telefono
    - audio/pcm   -> el navegador, para probar por microfono sin llamar
    """
    infmt = {"type": fmt} if rate is None else {"type": fmt, "rate": rate}
    return {"type": "session.update", "session": {
        "type": "realtime",
        "output_modalities": ["audio"],
        "audio": {
            # pcmu == g711 ulaw 8kHz, que es exactamente lo que manda Twilio:
            # asi no hay que transcodificar nada en el medio
            "input": {"format": infmt,
                      # semantic_vad decide que terminaste de hablar por lo que
                      # DECIS, no por un silencio fijo: no te corta a mitad de
                      # frase cuando dudas o tomas aire
                      # interrupt_response en false: OpenAI deja de cortarse
                      # sola apenas escucha algo. Nosotros cortamos recien
                      # cuando el conductor sostiene la voz INTERRUPT_AFTER_S.
                      "turn_detection": {"type": "semantic_vad",
                                         "eagerness": REALTIME_EAGERNESS,
                                         "interrupt_response": INTERRUPT_AFTER_S <= 0},
                      "transcription": {"model": "whisper-1", "language": "es"}},
            "output": {"format": infmt, "voice": REALTIME_VOICE,
                       "speed": REALTIME_SPEED},
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
    # copia del audio del conductor mientras habla, para analizarlo aparte
    buffer_voz = bytearray()
    hablando = False
    bostezos = []
    # solo se puede cancelar una respuesta que este en curso
    respondiendo = {"v": False}
    piso = voice_signals.PisoDeRuido()

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
                    crudo = base64.b64decode(msg["media"]["payload"])
                    # El audio va COMPLETO a OpenAI: su VAD semantico maneja el
                    # ruido mejor que cualquier gate nuestro, y filtrar aca hacia
                    # que en ambientes ruidosos no se detectara la voz.
                    await oai.send(json.dumps({"type": "input_audio_buffer.append",
                                               "audio": msg["media"]["payload"]}))
                    # el piso adaptativo se usa para quedarnos solo con los
                    # tramos con voz al analizar bostezos
                    pcm = voice_signals.ulaw_a_pcm16(crudo)
                    if hablando and piso.es_voz(pcm):
                        buffer_voz.extend(crudo)
                elif msg["event"] == "stop":
                    log.info("stream %s cerrado", stream_sid)
                    break

        relojes = []

        def nonlocal_hablando(v):
            nonlocal hablando
            hablando = v

        def cancelar_reloj():
            for t in relojes:
                t.cancel()
            relojes.clear()

        async def cortar_si_sigue():
            """Corta al agente solo si el conductor sostuvo la voz el tiempo pedido."""
            try:
                await asyncio.sleep(INTERRUPT_AFTER_S)
            except asyncio.CancelledError:
                return
            if not respondiendo["v"]:
                return  # el agente ya habia terminado, no hay nada que cortar
            log.info("el conductor sostuvo la voz %ss, corto al agente", INTERRUPT_AFTER_S)
            if stream_sid:
                await twilio_ws.send_json({"event": "clear", "streamSid": stream_sid})
            await oai.send(json.dumps({"type": "response.cancel"}))

        def analizar_tramo(datos):
            if len(datos) < 8000:  # menos de 1 segundo de ulaw
                return None
            try:
                return voice_signals.analizar(voice_signals.ulaw_a_pcm16(datos), 8000)  # en thread
            except Exception:
                log.exception("fallo el analisis de voz")
                return None

        async def de_openai_a_twilio():
            async for raw in oai:
                ev = json.loads(raw)
                tipo = ev.get("type", "")

                if tipo == "response.created":
                    respondiendo["v"] = True
                elif tipo == "response.done":
                    respondiendo["v"] = False

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
                    nonlocal_hablando(True)
                    # no cortamos al agente todavia: puede ser un "aja" o un
                    # ruido. Arrancamos un reloj y cortamos solo si sigue
                    # hablando cuando se cumpla.
                    cancelar_reloj()
                    relojes.append(asyncio.create_task(cortar_si_sigue()))

                elif tipo == "input_audio_buffer.speech_stopped":
                    nonlocal_hablando(False)
                    cancelar_reloj()  # hablo poco: el agente sigue tranquilo
                    # el conductor termino su frase: si el agente todavia habla
                    # hay que cortarlo, si no OpenAI no puede crear la respuesta
                    if respondiendo["v"]:
                        await oai.send(json.dumps({"type": "response.cancel"}))
                    r = await asyncio.to_thread(analizar_tramo, bytes(buffer_voz))
                    buffer_voz.clear()
                    if r and r["bostezo"]:
                        bostezos.append(r)
                        log.info("bostezo detectado score=%s dur=%ss",
                                 r["score"], r["duracion_voz_s"])

                elif tipo in ("response.output_audio_transcript.done",
                              "response.audio_transcript.done"):
                    transcript.append(f"AGENTE: {ev.get('transcript', '')}")
                elif tipo == "conversation.item.input_audio_transcription.completed":
                    txt = ev.get("transcript", "")
                    if not _es_alucinacion(txt):
                        transcript.append(f"CONDUCTOR: {txt}")
                elif tipo == "error":
                    code = (ev.get("error") or {}).get("code", "")
                    if code in ERRORES_BENIGNOS:
                        log.debug("realtime (benigno): %s", code)
                    else:
                        log.error("openai realtime: %s", ev.get("error"))

        try:
            await asyncio.gather(de_twilio_a_openai(), de_openai_a_twilio())
        except Exception:
            log.exception("el puente de audio se corto")

    if bostezos:
        log.info("la llamada tuvo %s bostezo(s)", len(bostezos))
    return transcript


def base64_len(payload):
    """Bytes de audio reales detras del base64. 8000 bytes = 1 segundo en ulaw."""
    return len(base64.b64decode(payload))


async def bridge_browser(ws, session):
    """Igual que `bridge`, pero del otro lado hay un navegador en vez de Twilio.

    Sirve para probar el agente hablandole al microfono de la PC, sin gastar
    llamadas. El audio va en PCM16 a 24kHz, que es lo que maneja el browser.
    """
    if not OPENAI_API_KEY:
        await ws.send_json({"type": "error", "text": "falta OPENAI_API_KEY"})
        return

    buf = bytearray()
    hablando = {"v": False}
    relojes = []
    respondiendo = {"v": False}
    piso = voice_signals.PisoDeRuido()

    async with websockets.connect(
        URL.format(OPENAI_REALTIME_MODEL),
        additional_headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        max_size=None,
    ) as oai:
        await oai.send(json.dumps(_session_update(session, "audio/pcm", 24000)))
        await oai.send(json.dumps({"type": "response.create"}))

        async def cortar_si_sigue():
            try:
                await asyncio.sleep(INTERRUPT_AFTER_S)
            except asyncio.CancelledError:
                return
            if not respondiendo["v"]:
                return  # el agente ya habia terminado, no hay nada que cortar
            log.info("sostuvo la voz %ss, corto al agente", INTERRUPT_AFTER_S)
            await ws.send_json({"type": "clear"})
            await ws.send_json({"type": "info", "text":
                                f"te sostuviste {INTERRUPT_AFTER_S}s, corte al agente"})
            await oai.send(json.dumps({"type": "response.cancel"}))

        async def del_navegador():
            while True:
                msg = json.loads(await ws.receive_text())
                if msg.get("type") == "audio":
                    crudo = base64.b64decode(msg["audio"])
                    await oai.send(json.dumps({"type": "input_audio_buffer.append",
                                               "audio": msg["audio"]}))
                    if hablando["v"] and piso.es_voz(crudo):
                        buf.extend(crudo)

        async def hacia_el_navegador():
            async for raw in oai:
                ev = json.loads(raw)
                t = ev.get("type", "")
                if t == "response.created":
                    respondiendo["v"] = True
                elif t == "response.done":
                    respondiendo["v"] = False

                if t in ("response.output_audio.delta", "response.audio.delta"):
                    await ws.send_json({"type": "audio", "audio": ev["delta"]})
                elif t == "input_audio_buffer.speech_started":
                    hablando["v"] = True
                    buf.clear()
                    for r in relojes:
                        r.cancel()
                    relojes.clear()
                    relojes.append(asyncio.create_task(cortar_si_sigue()))

                elif t == "input_audio_buffer.speech_stopped":
                    hablando["v"] = False
                    await ws.send_json({"type": "ambiente", **piso.estado()})
                    for r in relojes:
                        r.cancel()
                    relojes.clear()
                    if respondiendo["v"]:
                        await oai.send(json.dumps({"type": "response.cancel"}))
                    if len(buf) > 48000:  # 1 segundo de pcm16 a 24kHz
                        try:
                            # el navegador ya manda PCM16, no hay que convertir
                            r = await asyncio.to_thread(voice_signals.analizar, bytes(buf), 24000)
                            if r["bostezo"]:
                                await ws.send_json({"type": "voz", "analisis": r})
                                log.info("bostezo detectado score=%s", r["score"])
                        except Exception:
                            log.exception("fallo el analisis de voz")
                    buf.clear()
                elif t in ("response.output_audio_transcript.done",
                           "response.audio_transcript.done"):
                    await ws.send_json({"type": "dijo", "quien": "AGENTE",
                                        "texto": ev.get("transcript", "")})
                elif t == "conversation.item.input_audio_transcription.completed":
                    txt = ev.get("transcript", "")
                    if not _es_alucinacion(txt):
                        await ws.send_json({"type": "dijo", "quien": "VOS", "texto": txt})
                elif t == "error":
                    code = (ev.get("error") or {}).get("code", "")
                    if code in ERRORES_BENIGNOS:
                        log.debug("realtime (benigno): %s", code)
                    else:
                        log.error("openai realtime: %s", ev.get("error"))
                        await ws.send_json({"type": "error", "text": str(ev.get("error"))})

        try:
            await asyncio.gather(del_navegador(), hacia_el_navegador())
        except Exception:
            log.info("se cerro la prueba por navegador")

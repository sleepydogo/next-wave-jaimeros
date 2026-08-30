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
import time
import uuid

import httpx
import websockets

from .. import bus, db, events
from ..config import (AGENT_NAME, FACTURACION_URL, OPENAI_API_KEY,
                      OPENAI_REALTIME_MODEL,
                      REALTIME_EAGERNESS,
                      REALTIME_SPEED, REALTIME_VOICE)
from . import grabacion, voice_signals

log = logging.getLogger("realtime")

# Herramientas que el agente puede usar en medio de la llamada. Consultan el
# sistema administrativo, que es un servicio aparte.
HERRAMIENTAS = [
    {"type": "function",
     "name": "consultar_factura",
     "description": "Estado de la factura de un contenedor: si esta emitida, el "
                    "numero, el monto y si falta algo. Usala cuando el conductor "
                    "pregunte por la factura.",
     "parameters": {"type": "object", "properties": {
         "contenedor": {"type": "string",
                        "description": "codigo del contenedor, ej MSCU-4471820"}},
         "required": ["contenedor"]}},
    {"type": "function",
     "name": "consultar_remito",
     "description": "Estado del remito de un contenedor: si esta listo para "
                    "retirar, por que puerta, y las observaciones. Usala cuando el "
                    "conductor pregunte por el remito o por donde retirar.",
     "parameters": {"type": "object", "properties": {
         "contenedor": {"type": "string",
                        "description": "codigo del contenedor, ej MSCU-4471820"}},
         "required": ["contenedor"]}},
]


async def _ejecutar_herramienta(nombre, args):
    """Llama al sistema administrativo y devuelve el resultado como texto."""
    contenedor = (args or {}).get("contenedor", "")
    ruta = "facturas" if nombre == "consultar_factura" else "remitos"
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(f"{FACTURACION_URL}/{ruta}/{contenedor}")
        if r.status_code == 404:
            return json.dumps({"encontrado": False,
                               "mensaje": f"no hay {ruta[:-1]} cargado para {contenedor}"})
        r.raise_for_status()
        return json.dumps({"encontrado": True, **r.json()}, ensure_ascii=False)
    except Exception:
        log.exception("fallo la consulta a facturacion")
        # el agente tiene que poder decir que no pudo consultar, no inventar
        return json.dumps({"encontrado": False,
                           "mensaje": "el sistema no responde en este momento"})

# Whisper, cuando le mandan silencio o ruido, inventa frases que vio en su
# entrenamiento: subtitulos, creditos, URLs. No son cosas que dijo el conductor.
ALUCINACIONES = ("www.", "http", "subtitul", "amara.org", "gracias por ver",
                 "suscrib", ".com", "editor de")

# errores que son parte del flujo normal y no hay que mostrarle a nadie
ERRORES_BENIGNOS = ("response_cancel_not_active", "conversation_already_has_active_response")

# si menos de esta fraccion del segmento tenia voz, lo que "transcribio" Whisper
# es invento sobre ruido
MIN_PROPORCION_VOZ = 0.15


def _es_alucinacion(texto):
    t = (texto or "").strip().lower()
    return not t or any(m in t for m in ALUCINACIONES)

URL = "wss://api.openai.com/v1/realtime?model={}"

INSTRUCCIONES = """Sos {agente}, de la oficina de logistica de una empresa de
transporte de contenedores en Argentina. Estas llamando por telefono a {nombre},
un camionero. Hablas castellano rioplatense, de vos.

Objetivo de la llamada: {objetivo}
Datos del viaje: contenedor {contenedor}, puerto {puerto}. {detalle}

SI EL CONDUCTOR ESTA EN PELIGRO (lo siguen, lo asaltan, hay armas, violencia,
pide auxilio) esto pasa por encima de TODO lo demas:
- Abandona el objetivo de la llamada en el acto. No vuelvas a preguntar por la
  carga, ni por horarios, ni por el contenedor. Nunca.
- Decile de entrada que YA se disparo una alerta y que operaciones lo esta
  viendo en este momento. Es verdad: el sistema la levanta solo.
- Vos no podes llamar al 911, pero SI avisaste a la empresa y podes quedarte
  con el.
  Ejemplo: "{nombre}, escuchame: ya avise a operaciones, lo estan viendo ahora.
  Yo no puedo llamar al 911 desde aca, llamalo vos si podes hablar."
- Priorizá su seguridad: que se aleje, que no frene, que no discuta por la carga.
- Quedate en la linea y preguntale donde esta. Una pregunta por vez.
- NUNCA digas "no puedo ayudarte" ni cortes por el tema.
- Nunca des datos del viaje, rutas ni valores de carga a alguien que no sea
  el conductor.

Como hablas:
- Arranca diciendo solamente "Hola?" y espera a que te conteste. No te presentes
  todavia. Recien despues de que responda, presentate asi:
  "Hola {nombre}, como estas? Soy {agente}, me comunico de la empresa."
- Si el conductor pregunta por la factura o el remito, consultalo con la
  herramienta. Antes de consultar decile algo corto y natural, tipo
  "dame un segundo que lo consulto con Blake de nautica", y despues le pasas
  el dato concreto. Nunca inventes numeros de factura, montos ni puertas: si
  el sistema no responde, decile que no lo pudiste ver y que lo averiguas.
- Frases de 8 a 12 palabras. Una idea por frase, y punto.
  Si una frase te queda larga, partila en dos con una pausa en el medio.
- Si te interrumpe, callate y escuchalo. Nunca sigas hablando encima.
- Reacciona a lo que te dice antes de preguntar otra cosa. Si te dice que esta
  cansado, reconocelo primero.
- No leas direcciones completas, codigos postales ni el contenedor letra por
  letra. Decilo natural: "en Corrientes al mil".
- Nunca digas que sos una inteligencia artificial, un bot ni un asistente.
- UNA sola pregunta por turno, y despues te callas y esperas la respuesta.
  Nunca encadenes dos preguntas en la misma intervencion, ni siquiera separadas
  por "y" o por una coma.
  MAL: "Necesito saber por que te detuviste, si tenes algun problema, si
       precisas asistencia."
  BIEN: "Necesito saber por que te detuviste."  (y te callas)
  Despues de escuchar lo que te contesta, reaccionas a ESO y recien ahi, si
  todavia falta algo, haces la segunda pregunta.
- Nunca agregues condicionales del tipo "y si no, decime cuanto tardas" o
  "avisame si necesitas algo": eso va en el turno siguiente, si hace falta.
  Preguntas cerradas primero; el detalle se pide despues de escuchar la respuesta.
- Maximo dos preguntas en toda la llamada. Cuando tengas la respuesta, despedite
  y cerra.
- Si te dice que no sabe cuanto va a tardar, no lo dejes ahi: explicale que
  necesitas un estimativo aunque sea aproximado para coordinar el turno con el
  puerto, y ofrecele un rango para que elija.
  Ejemplo: "Necesito darle un numero al puerto, aunque sea a ojo. Te sirve
  media hora, o lo ves mas cerca de una hora?"
  Recien si insiste en que no puede estimar, cerras y le decis que lo vas a
  llamar de nuevo en un rato.

Como suena tu voz (esto es tan importante como lo que decis):
- Tranquila y natural, como una companera de trabajo que llama para coordinar.
  Ni robotica ni autoritaria: es una charla, no un parte militar.
- Preguntas simples y directas, sin sonar a orden. Ni "necesito que me digas",
  ni "perdon que te moleste". Simplemente: "estas listo para cargar?",
  "que paso?", "todo bien?".
- Frases afirmativas y en presente, pero sin imperativos secos. Mejor
  "te queria preguntar si estas listo" que "necesito saber si estas listo".
- Calida con el conductor: agil si son buenas noticias, y bajas un cambio si
  suena cansado o preocupado.
- Cerras vos la conversacion cuando ya tenes la respuesta, sin apurarlo.
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
                     " que NO, recien ahi preguntale en cuantos minutos calcula estar listo."
                     " No cierres la llamada sin un numero aproximado: lo necesitas para"
                     " coordinar el turno con el puerto.",
    "load_authorized": "avisarle que el puerto habilito la carga y que puede pasar a cargar.",
    "emergency": "entender que le pasa. PRIMERA pregunta, sola: por que se detuvo o freno. Escucha la respuesta completa. Recien despues, y solo si hace falta, pregunta si necesita ayuda o si puede seguir.",
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
                      # la interrupcion la maneja OpenAI: corta su respuesta
                      # sola cuando detecta que el conductor empezo a hablar
                      "turn_detection": {"type": "semantic_vad",
                                         "eagerness": REALTIME_EAGERNESS,
                                         "interrupt_response": True},
                      "transcription": {"model": "whisper-1", "language": "es"}},
            "output": {"format": infmt, "voice": REALTIME_VOICE,
                       "speed": REALTIME_SPEED},
        },
        "instructions": _instructions(session),
    }}


async def bridge(twilio_ws, session, call_id="sin-id"):
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
    t0 = time.time()
    # solo se puede cancelar una respuesta que este en curso
    # guardamos el ID de la respuesta en curso, no un booleano: hay que poder
    # distinguir la respuesta que venia de antes (esa si se corta) de la que
    # OpenAI acaba de crear para contestarle (esa NO se toca, o el agente
    # queda mudo)
    activa = {"id": None}
    piso = voice_signals.PisoDeRuido()
    prop = {"v": 1.0}
    grab = grabacion.Grabador(8000)
    prop = {"v": 1.0}

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
                    # el piso se sigue calibrando con cada frame, pero NO se usa
                    # para filtrar el buffer: un bostezo es suave y sostenido, y
                    # el gate se lo comia
                    pcm = voice_signals.ulaw_a_pcm16(crudo)
                    piso.es_voz(pcm)
                    grab.del_conductor(pcm)
                    if hablando:
                        buffer_voz.extend(crudo)
                elif msg["event"] == "stop":
                    log.info("stream %s cerrado", stream_sid)
                    break

        def nonlocal_hablando(v):
            nonlocal hablando
            hablando = v

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
                    activa["id"] = (ev.get("response") or {}).get("id")
                elif tipo == "response.done":
                    activa["id"] = None

                # audio del agente -> Twilio (los dos nombres segun version de la API)
                if tipo in ("response.output_audio.delta", "response.audio.delta"):
                    grab.del_agente(voice_signals.ulaw_a_pcm16(base64.b64decode(ev["delta"])))
                    if stream_sid:
                        await twilio_ws.send_json({
                            "event": "media", "streamSid": stream_sid,
                            "media": {"payload": ev["delta"]}})

                # el conductor empezo a hablar: cortar lo que estabamos diciendo.
                # sin este clear, Twilio sigue reproduciendo el audio ya enviado
                # y el agente le habla encima.
                elif tipo == "input_audio_buffer.speech_started":
                    nonlocal_hablando(True)
                    # OpenAI ya corta su propia respuesta; a Twilio hay que
                    # decirle que tire el audio que tenia en buffer
                    if stream_sid:
                        await twilio_ws.send_json({"event": "clear",
                                                   "streamSid": stream_sid})

                elif tipo == "input_audio_buffer.speech_stopped":
                    nonlocal_hablando(False)
                    tramo = bytes(buffer_voz)
                    buffer_voz.clear()
                    prop["v"] = piso.proporcion_voz(
                        voice_signals.ulaw_a_pcm16(tramo), 8000) if tramo else 0.0
                    r = await asyncio.to_thread(analizar_tramo, tramo)
                    if r and r["bostezo"]:
                        bostezos.append(r)
                        log.info("bostezo detectado score=%s dur=%ss",
                                 r["score"], r["duracion_voz_s"])

                elif tipo in ("response.output_audio_transcript.done",
                              "response.audio_transcript.done"):
                    transcript.append(f"AGENTE: {ev.get('transcript', '')}")
                elif tipo == "conversation.item.input_audio_transcription.completed":
                    txt = ev.get("transcript", "")
                    if prop["v"] < MIN_PROPORCION_VOZ:
                        log.info("descarto transcripcion: el tramo era %.0f%% ruido (%r)",
                                 (1 - prop["v"]) * 100, txt[:60])
                    elif not _es_alucinacion(txt):
                        transcript.append(f"CONDUCTOR: {txt}")
                        frase = voice_signals.es_emergencia(txt)
                        if frase:
                            # no esperamos al final de la llamada: se escala ya
                            log.warning("EMERGENCIA en la llamada: %r", frase)
                            await bus.publish(events.ALERT_RAISED, {
                                "trip_id": session.get("trip_id", ""),
                                "severity": "alta",
                                "title": "EMERGENCIA: el conductor reporta peligro",
                                "body": f"Dijo: {txt[:200]}",
                            })

                elif tipo == "response.function_call_arguments.done":
                    nombre = ev.get("name", "")
                    log.info("el agente consulta %s(%s)", nombre, ev.get("arguments"))
                    try:
                        args = json.loads(ev.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    salida = await _ejecutar_herramienta(nombre, args)
                    await oai.send(json.dumps({
                        "type": "conversation.item.create",
                        "item": {"type": "function_call_output",
                                 "call_id": ev.get("call_id"), "output": salida}}))
                    # con el dato en mano, que retome la conversacion
                    await oai.send(json.dumps({"type": "response.create"}))
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

    voz = voice_signals.resumen(len(bostezos), (time.time() - t0) / 60)
    if bostezos:
        log.info("la llamada tuvo %s bostezo(s) -> fatiga %s",
                 len(bostezos), voz["fatiga_por_bostezos"])
    return transcript, grab.guardar(call_id), voz


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
    # guardamos el ID de la respuesta en curso, no un booleano: hay que poder
    # distinguir la respuesta que venia de antes (esa si se corta) de la que
    # OpenAI acaba de crear para contestarle (esa NO se toca, o el agente
    # queda mudo)
    activa = {"id": None}
    piso = voice_signals.PisoDeRuido()
    prop = {"v": 1.0}

    # OpenAI Realtime SOLO acepta 24 kHz en audio/pcm (48k y 16k los rechaza),
    # asi que el navegador resamplea antes de mandar. Igual leemos su rate real
    # para dejarlo en el log.
    primero = json.loads(await ws.receive_text())
    log.info("prueba por navegador: microfono a %s Hz, se envia a 24000",
             primero.get("rate"))
    rate = 24000

    # fuera del `async with` a proposito: se siguen usando despues de cerrar la
    # conexion con OpenAI, cuando se guarda la llamada
    grab = grabacion.Grabador(rate)
    dicho = []
    bostezos = []
    t0 = time.time()

    async with websockets.connect(
        URL.format(OPENAI_REALTIME_MODEL),
        additional_headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        max_size=None,
    ) as oai:
        await oai.send(json.dumps(_session_update(session, "audio/pcm", rate)))
        await oai.send(json.dumps({"type": "response.create"}))

        recibidos = [0]

        async def del_navegador():
            while True:
                msg = json.loads(await ws.receive_text())
                if msg.get("type") == "audio":
                    crudo = base64.b64decode(msg["audio"])
                    recibidos[0] += 1
                    if recibidos[0] == 1 or recibidos[0] % 50 == 0:
                        log.info("navegador -> %s chunks, ultimo %s bytes",
                                 recibidos[0], len(crudo))
                    await oai.send(json.dumps({"type": "input_audio_buffer.append",
                                               "audio": msg["audio"]}))
                    piso.es_voz(crudo)   # calibra el ambiente, no filtra
                    grab.del_conductor(crudo)
                    if hablando["v"]:
                        buf.extend(crudo)

        async def hacia_el_navegador():
            async for raw in oai:
                ev = json.loads(raw)
                t = ev.get("type", "")
                if t not in ("response.output_audio.delta", "response.audio.delta"):
                    log.info("openai <- %s", t)
                if t == "response.created":
                    activa["id"] = (ev.get("response") or {}).get("id")
                    # el navegador corta el microfono mientras suena el agente:
                    # si no, el parlante entra por el mic y se interrumpe solo
                    await ws.send_json({"type": "hablando", "v": True})
                    await ws.send_json({"type": "estado", "texto": "el agente empieza a hablar"})
                elif t == "response.done":
                    activa["id"] = None
                    await ws.send_json({"type": "hablando", "v": False})
                    await ws.send_json({"type": "estado", "texto": "el agente termino de hablar"})

                if t in ("response.output_audio.delta", "response.audio.delta"):
                    grab.del_agente(base64.b64decode(ev["delta"]))
                    await ws.send_json({"type": "audio", "audio": ev["delta"]})
                elif t == "input_audio_buffer.speech_started":
                    hablando["v"] = True
                    buf.clear()

                elif t == "input_audio_buffer.speech_stopped":
                    hablando["v"] = False
                    prop["v"] = piso.proporcion_voz(bytes(buf), rate) if buf else 0.0
                    await ws.send_json({"type": "ambiente", **piso.estado(),
                                        "voz_pct": round(prop["v"] * 100)})
                    if len(buf) > 48000:  # 1 segundo de pcm16 a 24kHz
                        try:
                            # el navegador ya manda PCM16, no hay que convertir
                            r = await asyncio.to_thread(voice_signals.analizar, bytes(buf), rate)
                            if r["bostezo"]:
                                bostezos.append(r)
                                await ws.send_json({"type": "voz", "analisis": r})
                                log.info("bostezo detectado score=%s", r["score"])
                        except Exception:
                            log.exception("fallo el analisis de voz")
                    buf.clear()
                elif t in ("response.output_audio_transcript.done",
                           "response.audio_transcript.done"):
                    dicho.append(f"AGENTE: {ev.get('transcript', '')}")
                    await ws.send_json({"type": "dijo", "quien": "AGENTE",
                                        "texto": ev.get("transcript", "")})
                elif t == "conversation.item.input_audio_transcription.completed":
                    txt = ev.get("transcript", "")
                    if prop["v"] < MIN_PROPORCION_VOZ:
                        log.info("descarto transcripcion: %.0f%% ruido (%r)",
                                 (1 - prop["v"]) * 100, txt[:60])
                        await ws.send_json({"type": "info", "text":
                                            "descarte una transcripcion: el tramo era casi todo ruido"})
                    elif not _es_alucinacion(txt):
                        await ws.send_json({"type": "dijo", "quien": "VOS", "texto": txt})
                        frase = voice_signals.es_emergencia(txt)
                        if frase:
                            # no esperamos al final de la llamada: se escala ya
                            log.warning("EMERGENCIA en la llamada: %r", frase)
                            await bus.publish(events.ALERT_RAISED, {
                                "trip_id": session.get("ctx", {}).get("trip_id", ""),
                                "severity": "alta",
                                "title": "EMERGENCIA: el conductor reporta peligro",
                                "body": f"Dijo: {txt[:200]}",
                            })

                elif t == "response.function_call_arguments.done":
                    nombre = ev.get("name", "")
                    log.info("el agente consulta %s(%s)", nombre, ev.get("arguments"))
                    try:
                        args = json.loads(ev.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    salida = await _ejecutar_herramienta(nombre, args)
                    await oai.send(json.dumps({
                        "type": "conversation.item.create",
                        "item": {"type": "function_call_output",
                                 "call_id": ev.get("call_id"), "output": salida}}))
                    # con el dato en mano, que retome la conversacion
                    await oai.send(json.dumps({"type": "response.create"}))
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
            # con log.info se perdia el traceback y el cierre del websocket
            # quedaba sin explicacion del lado del navegador (codigo 1006)
            log.exception("se corto la prueba por navegador")

    # la prueba local queda en la misma tabla que las llamadas reales, asi se
    # puede validar el circuito completo (audio + transcripcion + dashboard)
    # sin gastar un credito de Twilio
    call_id = f"local{uuid.uuid4().hex[:7]}"
    ruta = grab.guardar(call_id)
    voz = voice_signals.resumen(len(bostezos), (time.time() - t0) / 60)
    db.x("INSERT INTO calls (id,trip_id,reason,status,transcript,voice,duration_s,"
         "cost_usd,audio_path,ts) VALUES (?,?,?,?,?,?,?,?,?,?)",
         (call_id, session.get("ctx", {}).get("trip_id", "prueba-local"),
          "prueba_local", "done", "\n".join(dicho), json.dumps(voz),
          round(time.time() - t0, 1), 0.0, ruta, time.time()))
    log.info("prueba local guardada como llamada %s", call_id)

"""El cerebro del agente de voz: decide que decir y lee metricas de la voz."""
import json
import logging

from openai import AsyncOpenAI

from ..config import OPENAI_API_KEY, OPENAI_MODEL

log = logging.getLogger("brain")
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Solo el nombre de pila: decir el nombre completo suena a robot leyendo una
# ficha. Frases cortas y separadas, que es como habla una persona por telefono.
OPENERS = {
    "arrival_check": (
        "Hola {name}, que tal. Te hablo de logistica. "
        "Te vi llegando al puerto. Estas listo para cargar?"
    ),
    "load_authorized": (
        "{name}, buenas. Ya te habilitaron la carga. "
        "Podes ir entrando cuando quieras. Todo bien por ahi?"
    ),
    "emergency": (
        "Hola {name}, te hablo de logistica. "
        "Vi que {detail}. Esta todo bien?"
    ),
}

SYSTEM = """Trabajas en la oficina de logistica de una empresa de transporte de
contenedores en Argentina y estas llamando por telefono a un camionero.
Objetivo de esta llamada: {goal}

Hablas como una persona real, no como un sistema:
- Castellano rioplatense, de vos. "Dale", "perfecto", "barbaro", "ningun drama".
- Frases de menos de 15 palabras. Una idea por frase.
- Arranca reaccionando a lo que te dijo antes de preguntar lo siguiente.
  Si te dice que esta cansado, primero reconocelo, despues seguí.
- Nunca digas que sos un asistente, un bot ni una inteligencia artificial.
- Nunca leas direcciones completas, codigos postales ni codigos de contenedor
  letra por letra. Decilo como lo diria una persona: "en Corrientes al mil".
- Nada de listas, vinietas, comillas ni emojis: esto se lee en voz alta.
- No repitas el nombre en cada frase, queda raro.

Reglas duras:
- Maximo 2 preguntas. Si ya tenes la respuesta, cerra la llamada.
- Al cerrar, despedite en una frase corta y natural.
- Nunca inventes datos del viaje.

Devolve SIEMPRE JSON con esta forma:
{{"reply": "lo que decis en voz alta",
  "done": true|false,
  "outcome": {{"available": true|false|null, "eta_min": numero|null,
               "problem": "texto corto o null", "needs_human": true|false}},
  "voice": {{"stress": 0.0-1.0, "fatigue": 0.0-1.0, "clarity": 0.0-1.0,
             "notes": "que escuchaste en como hablo"}}}}
"""

GOALS = {
    "arrival_check": "confirmar si el conductor esta disponible AHORA para recibir la carga, y si no, en cuantos minutos.",
    "load_authorized": "confirmar que el conductor entendio que puede pasar a cargar y que va a avanzar.",
    "emergency": "entender por que se detuvo o freno, si necesita asistencia, y si puede continuar.",
}

FALLBACK = {"reply": "Perfecto, gracias. Cualquier cosa te vuelvo a llamar.", "done": True,
            "outcome": {"available": None, "eta_min": None, "problem": None, "needs_human": True},
            "voice": {"stress": 0.0, "fatigue": 0.0, "clarity": 0.0, "notes": "sin analisis"}}


def _valid_response(value):
    if not isinstance(value, dict) or not isinstance(value.get("reply"), str):
        return None
    outcome = value.get("outcome")
    voice = value.get("voice")
    if not isinstance(outcome, dict) or not isinstance(voice, dict):
        return None
    if not isinstance(value.get("done"), bool):
        return None
    for key in ("stress", "fatigue", "clarity"):
        if not isinstance(voice.get(key), (int, float)):
            return None
    if outcome.get("available") not in (True, False, None) or outcome.get("needs_human") not in (True, False):
        return None
    return {"reply": value["reply"][:1000], "done": value["done"],
            "outcome": {"available": outcome.get("available"), "eta_min": outcome.get("eta_min"),
                        "problem": outcome.get("problem"), "needs_human": outcome["needs_human"]},
            "voice": {**voice, **{key: max(0.0, min(1.0, float(voice[key]))) for key in ("stress", "fatigue", "clarity")}}}


def opener(reason, ctx):
    # solo el nombre de pila: "Hola Carlos Gimenez" suena a call center
    ctx = {**ctx, "name": str(ctx.get("name", "")).split()[0] if ctx.get("name") else "che"}
    return OPENERS[reason].format(**ctx)


async def respond(reason, history, ctx):
    """history: [{'role':'assistant'|'user','content':str}]. Devuelve dict + tokens usados."""
    if not client:
        return FALLBACK, (0, 0)
    msgs = [{"role": "system", "content": SYSTEM.format(goal=GOALS[reason])},
            {"role": "system", "content": f"Datos del viaje: {json.dumps(ctx, ensure_ascii=False)}"}]
    msgs += history
    try:
        res = await client.chat.completions.create(
            model=OPENAI_MODEL, messages=msgs,
            response_format={"type": "json_object"}, temperature=0.3, max_tokens=300,
        )
        u = res.usage
        parsed = _valid_response(json.loads(res.choices[0].message.content))
        return (parsed or FALLBACK), (u.prompt_tokens, u.completion_tokens)
    except Exception:
        log.exception("brain fallo")
        return FALLBACK, (0, 0)


def voice_metrics(llm_voice, transcript, latency_s, asr_confidence):
    """Combina lo que oyo el LLM con senales objetivas del canal telefonico."""
    words = len((transcript or "").split())
    rate = round(words / max(latency_s, 0.1), 2) if words else 0.0
    stress = float(llm_voice.get("stress", 0) or 0)
    fatigue = float(llm_voice.get("fatigue", 0) or 0)
    # hablar muy lento o ASR con baja confianza suma riesgo
    penalty = (0.2 if asr_confidence and asr_confidence < 0.6 else 0) + (0.2 if latency_s > 4 else 0)
    return {
        "stress": stress, "fatigue": fatigue,
        "clarity": float(llm_voice.get("clarity", 0) or 0),
        "notes": llm_voice.get("notes", ""),
        "asr_confidence": asr_confidence,
        "latency_s": round(latency_s, 2),
        "speech_rate_wps": rate,
        "risk": round(min(1.0, max(stress, fatigue) + penalty), 2),
    }

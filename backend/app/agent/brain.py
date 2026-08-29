"""El cerebro del agente de voz: decide que decir y lee metricas de la voz."""
import json
import logging

from openai import AsyncOpenAI

from ..config import OPENAI_API_KEY, OPENAI_MODEL

log = logging.getLogger("brain")
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

OPENERS = {
    "arrival_check": (
        "Hola {name}, soy el asistente automatico de logistica. "
        "Veo que llegaste al puerto {port} con el contenedor {container}. "
        "Necesito saber si ya estas disponible para recibir la carga."
    ),
    "load_authorized": (
        "Hola {name}. El puerto acaba de habilitar la carga del contenedor {container}. "
        "Ya podes pasar a cargar. Me confirmas que estas en condiciones de avanzar?"
    ),
    "emergency": (
        "Hola {name}, soy el asistente de logistica. "
        "Detectamos algo raro en tu recorrido: {detail}. Esta todo bien?"
    ),
}

SYSTEM = """Sos un agente de voz de una empresa de transporte de contenedores en Argentina.
Hablas por telefono con el conductor de un camion. Sos breve, claro y amable.
Objetivo de esta llamada: {goal}

Reglas:
- Maximo 2 preguntas. Si ya tenes la respuesta, cerra la llamada.
- Frases cortas, se van a leer en voz alta por telefono.
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


def opener(reason, ctx):
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
        return json.loads(res.choices[0].message.content), (u.prompt_tokens, u.completion_tokens)
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

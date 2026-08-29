"""Cron agent: mira como salieron las ultimas detecciones y ajusta los thresholds.

Senal de calidad: cuando el detector dispara una emergencia y el conductor dice
que no pasaba nada (outcome.problem == null), fue un falso positivo. Muchos
falsos positivos -> aflojar. Ninguno -> se puede apretar para detectar antes.
"""
import asyncio
import json
import logging

from openai import AsyncOpenAI

from .. import db
from ..config import OPENAI_API_KEY, OPENAI_MODEL
from ..detector import rules

log = logging.getLogger("threshold-agent")
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# limites duros: el agente nunca puede salirse de aca
BOUNDS = {
    "geofence_radius_m": (300, 2000),
    "stop_speed_kmh": (1, 10),
    "stop_min_seconds": (60, 900),
    "slowdown_drop_pct": (0.3, 0.9),
    "slowdown_min_kmh": (20, 80),
}

PROMPT = """Sos el que tunea un detector de eventos de camiones.

Thresholds actuales: {current}
Ultimas emergencias detectadas y que dijo el conductor: {feedback}

Falsos positivos = el agente llamo y el conductor dijo que no pasaba nada.
Si hay muchos falsos positivos, aflojá (mas conservador, detecta menos).
Si no hay ninguno, podes apretar un poco para detectar antes.
Cambios chicos, maximo 25% por vez.

Devolve JSON: {{"changes": {{"key": nuevo_valor}}, "reason": "una frase"}}
Solo incluí las keys que cambian. Si no hay que cambiar nada, changes vacio."""


def _feedback(limit=20):
    rows = db.q(
        "SELECT c.reason, c.outcome, c.voice FROM calls c "
        "WHERE c.reason='emergency' AND c.status='done' ORDER BY c.ts DESC LIMIT ?", (limit,))
    out = []
    for r in rows:
        o = json.loads(r["outcome"] or "{}")
        out.append({"problema_real": o.get("problem"), "falso_positivo": o.get("problem") is None})
    return out


async def run_once():
    fb = _feedback()
    if not fb:
        log.info("sin feedback todavia, no ajusto nada")
        return {}
    current = {k: rules.th(k) for k in BOUNDS}

    if not client:
        # heuristica sin LLM: >50% falsos positivos -> aflojar 20%
        fp = sum(1 for f in fb if f["falso_positivo"]) / len(fb)
        if fp <= 0.5:
            return {}
        changes = {"stop_min_seconds": current["stop_min_seconds"] * 1.2,
                   "slowdown_drop_pct": current["slowdown_drop_pct"] * 1.1}
        reason = f"{int(fp * 100)}% de falsos positivos (heuristica sin LLM)"
    else:
        res = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": PROMPT.format(
                current=json.dumps(current), feedback=json.dumps(fb, ensure_ascii=False))}],
            response_format={"type": "json_object"}, temperature=0.2, max_tokens=300)
        data = json.loads(res.choices[0].message.content)
        changes, reason = data.get("changes", {}), data.get("reason", "ajuste automatico")

    applied = {}
    for k, v in changes.items():
        if k not in BOUNDS:
            continue
        lo, hi = BOUNDS[k]
        v = max(lo, min(hi, float(v)))
        rules.set_th(k, v, reason)
        applied[k] = v
    if applied:
        log.info("thresholds ajustados: %s (%s)", applied, reason)
    return applied


async def loop(every_seconds=300):
    while True:
        await asyncio.sleep(every_seconds)
        try:
            await run_once()
        except Exception:
            log.exception("threshold agent fallo")

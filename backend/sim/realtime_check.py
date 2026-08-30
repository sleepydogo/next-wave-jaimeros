"""Valida la sesion de OpenAI Realtime sin gastar una llamada de Twilio.

Conecta al mismo endpoint y con la misma config que usa la llamada real, deja
que el agente diga su primera frase y muestra que respondio. Sirve para
verificar el modelo, la voz y las instrucciones antes de levantar el telefono.

    cd backend
    .venv/bin/python -m sim.realtime_check
    .venv/bin/python -m sim.realtime_check emergency

Dura unos segundos y consume muy pocos tokens de audio.
"""
import asyncio
import json
import sys

import websockets

from app.agent import realtime
from app.config import (OPENAI_API_KEY, OPENAI_REALTIME_MODEL, REALTIME_VOICE)

SESSION = {"reason": "arrival_check",
           "ctx": {"name": "Tomas Schattmann", "port": "Puerto Buenos Aires - Terminal 4",
                   "container": "MSCU-4471820", "detail": "estas detenido hace 7 minutos"}}


async def main():
    if not OPENAI_API_KEY:
        print("falta OPENAI_API_KEY")
        return
    SESSION["reason"] = sys.argv[1] if len(sys.argv) > 1 else "arrival_check"

    print(f"\nmodelo: {OPENAI_REALTIME_MODEL} | voz: {REALTIME_VOICE} | "
          f"escenario: {SESSION['reason']}\n")

    audio_bytes = 0
    dicho = []
    async with websockets.connect(
        realtime.URL.format(OPENAI_REALTIME_MODEL),
        additional_headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        max_size=None,
    ) as oai:
        await oai.send(json.dumps(realtime._session_update(SESSION)))
        await oai.send(json.dumps({"type": "response.create"}))

        try:
            async with asyncio.timeout(25):
                async for raw in oai:
                    ev = json.loads(raw)
                    t = ev.get("type", "")
                    if t == "error":
                        print("  ERROR:", json.dumps(ev.get("error"), ensure_ascii=False))
                        return
                    if t == "session.updated":
                        print("  sesion configurada OK")
                    elif t in ("response.output_audio.delta", "response.audio.delta"):
                        audio_bytes += realtime.base64_len(ev["delta"])
                    elif t in ("response.output_audio_transcript.done",
                               "response.audio_transcript.done"):
                        dicho.append(ev.get("transcript", ""))
                    elif t == "response.done":
                        break
        except TimeoutError:
            print("  se corto por timeout")

    print(f"\n  el agente arranca diciendo: {' '.join(dicho) or '(sin transcript)'}")
    print(f"  audio generado: {audio_bytes / 8000:.1f} segundos\n")
    print("  si esto anduvo, la parte de OpenAI esta lista y solo falta")
    print("  probar el audio de Twilio con UNA llamada real.\n")


if __name__ == "__main__":
    asyncio.run(main())

"""Conversa con el agente por texto, sin gastar un solo credito de Twilio.

Usa el mismo brain que la llamada real: los mismos prompts, el mismo modelo y
las mismas metricas de voz. Lo unico que cambia es que en vez de hablar,
escribis. Sirve para ajustar el guion sin llamar por telefono.

    cd backend
    .venv/bin/python -m sim.chat                # arrival_check
    .venv/bin/python -m sim.chat emergency
    .venv/bin/python -m sim.chat load_authorized

Solo necesita OPENAI_API_KEY. No levanta el backend ni toca la base.
"""
import asyncio
import sys

from app.agent import brain

CTX = {"name": "Carlos Gimenez", "phone": "+5492920577046",
       "port": "Puerto Buenos Aires - Terminal 4", "container": "MSCU-4471820",
       "detail": "estas detenido hace 7 minutos", "trip_id": "demo"}

GRIS, VERDE, AMARILLO, RESET = "\033[90m", "\033[92m", "\033[93m", "\033[0m"


async def main():
    reason = sys.argv[1] if len(sys.argv) > 1 else "arrival_check"
    if reason not in brain.OPENERS:
        print(f"razon invalida. Opciones: {', '.join(brain.OPENERS)}")
        return

    print(f"\n{GRIS}--- {reason} | escribi como si fueras el conductor, "
          f"Ctrl+C para salir ---{RESET}\n")

    history = []
    texto = brain.opener(reason, CTX)
    history.append({"role": "assistant", "content": texto})
    print(f"{VERDE}AGENTE:{RESET} {texto}\n")

    tok_in = tok_out = 0
    while True:
        try:
            dicho = input(f"{AMARILLO}VOS:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not dicho:
            continue

        history.append({"role": "user", "content": dicho})
        out, (ti, to) = await brain.respond(reason, history, CTX)
        tok_in += ti
        tok_out += to
        history.append({"role": "assistant", "content": out["reply"]})

        print(f"\n{VERDE}AGENTE:{RESET} {out['reply']}")
        vm = brain.voice_metrics(out.get("voice", {}), dicho, 1.8, 0.9)
        print(f"{GRIS}   voz: riesgo={vm['risk']} estres={vm['stress']} "
              f"fatiga={vm['fatigue']} | {vm['notes']}{RESET}")
        print(f"{GRIS}   outcome: {out.get('outcome')}{RESET}\n")

        if out.get("done"):
            print(f"{GRIS}--- el agente corto la llamada ---{RESET}")
            break

    # lo que habria costado en tokens; la telefonia es aparte
    from app import costs
    llm = tok_in / 1e6 * costs.PRICES["llm_in_per_mtok"] + \
        tok_out / 1e6 * costs.PRICES["llm_out_per_mtok"]
    print(f"{GRIS}tokens: {tok_in} in / {tok_out} out  (~USD {llm:.5f} de LLM){RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())

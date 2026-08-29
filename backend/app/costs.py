"""Modelo de costos. Todos los precios son parametros -> el dashboard muestra
costo real acumulado y docs/COSTS.md explica el esquema completo.

OJO: los precios de lista cambian y varian por pais y volumen. Verificar en
   Twilio Voice Pricing y OpenAI Pricing antes de la demo.
   Se pisan por env sin tocar codigo (P_VOICE_MIN, P_LLM_IN, etc).

La unidad de comparacion es el EVENTO GESTIONADO (una llegada a puerto, una
habilitacion de carga, una emergencia). El humano y el agente cuestan distinto
por evento, y esa es la comparacion honesta: el monitorista no gasta el tiempo
hablando, lo gasta mirando pantallas y reintentando llamadas.
"""
import os

PRICES = {
    # --- lo que gasta el agente ---
    # Twilio voz saliente a movil AR (USD/min, se factura por minuto iniciado)
    "twilio_voice_per_min": float(os.getenv("P_VOICE_MIN", "0.18")),
    # Twilio ASR en <Gather input="speech"> (USD por request de reconocimiento)
    "twilio_asr_per_request": float(os.getenv("P_ASR_REQ", "0.02")),
    # OpenAI gpt-4o-mini (USD por 1M tokens)
    "llm_in_per_mtok": float(os.getenv("P_LLM_IN", "0.15")),
    "llm_out_per_mtok": float(os.getenv("P_LLM_OUT", "0.60")),
    # WhatsApp Business (USD por conversacion de servicio)
    "whatsapp_per_msg": float(os.getenv("P_WA_MSG", "0.005")),

    # --- lo que cuesta el humano ---
    "human_per_hour": float(os.getenv("P_HUMAN_HOUR", "6.0")),
    # minutos de monitorista por evento: mirar la pantalla, marcar, que no
    # atienda, reintentar, anotar en la planilla
    "human_min_per_event": float(os.getenv("P_HUMAN_MIN_EVENT", "6.0")),
}


def call_cost(duration_s: float, asr_turns: int = 0, tok_in: int = 0, tok_out: int = 0) -> float:
    """Costo real de una llamada del agente, con lo que efectivamente consumio."""
    minutes = max(1, -(-int(duration_s) // 60))  # se cobra por minuto iniciado
    return round(
        minutes * PRICES["twilio_voice_per_min"]
        + asr_turns * PRICES["twilio_asr_per_request"]
        + tok_in / 1e6 * PRICES["llm_in_per_mtok"]
        + tok_out / 1e6 * PRICES["llm_out_per_mtok"],
        4,
    )


def human_cost_per_event() -> float:
    return round(PRICES["human_min_per_event"] / 60 * PRICES["human_per_hour"], 4)


def human_cost(events: int) -> float:
    """Lo que costaria el monitorista gestionando esos mismos eventos a mano."""
    return round(events * human_cost_per_event(), 4)

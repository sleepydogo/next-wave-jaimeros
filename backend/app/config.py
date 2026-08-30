import os
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(ROOT, ".env"))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL") or None
# absoluto a proposito: si no, cambia de archivo segun desde donde arranques
DB_PATH = os.path.abspath(os.path.join(ROOT, os.getenv("DB_PATH", "nextwave.db")))
# donde quedan los wav de las llamadas; junto a la base para que sobreviva igual
AUDIO_DIR = os.getenv("AUDIO_DIR", os.path.join(os.path.dirname(DB_PATH), "audio"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_FROM", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# "gather"   -> Twilio transcribe, el brain responde, voz de Polly (turnos rigidos)
# "realtime" -> audio bidireccional con OpenAI Realtime, voz de OpenAI, se lo
#               puede interrumpir. Mas natural y bastante mas caro.
VOICE_MODE = os.getenv("VOICE_MODE", "gather")
OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini")
REALTIME_VOICE = os.getenv("REALTIME_VOICE", "marin")
AGENT_NAME = os.getenv("AGENT_NAME", "Marina")
# velocidad de habla: 1.0 es el default, 0.9 suena mas pausado y humano
REALTIME_SPEED = float(os.getenv("REALTIME_SPEED", "1.25"))
# cuanto se apura en contestar: low deja hablar mas, high interrumpe antes
REALTIME_EAGERNESS = os.getenv("REALTIME_EAGERNESS", "low")
# cuanto tiene que sostener la voz el conductor para cortar al agente. Con 0 se
# comporta como antes: cualquier ruido lo interrumpe.
INTERRUPT_AFTER_S = float(os.getenv("INTERRUPT_AFTER_S", "3.0"))
# puerta de ruido: por debajo de este RMS (0..1) se considera ruido de fondo
NOISE_GATE = float(os.getenv("NOISE_GATE", "0.02"))

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
# sistema administrativo: facturas y remitos
FACTURACION_URL = os.getenv("FACTURACION_URL", "http://localhost:8100")

# Con 0, el detector guarda los pings pero NO dispara eventos por su cuenta:
# las alertas salen solo desde los botones de la app. Es lo que se usa en la
# demo, para que el GPS real del telefono no genere llamadas sorpresa.
DETECCION_AUTOMATICA = os.getenv("DETECCION_AUTOMATICA", "0") == "1"

SIMULATE_CALLS = os.getenv("SIMULATE_CALLS", "1") == "1"
SIMULATE_DISPATCH = os.getenv("SIMULATE_DISPATCH", "1") == "1"
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "ops@demo.com")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "NextWave <onboarding@resend.dev>")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", ALERT_EMAIL)
VALIDATE_TWILIO_SIGNATURE = os.getenv("VALIDATE_TWILIO_SIGNATURE", "1") == "1"
DEMO_WORKER_PHONE = os.getenv("DEMO_WORKER_PHONE", "+5491100000000")

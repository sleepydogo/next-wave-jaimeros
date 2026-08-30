import os
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(ROOT, ".env"))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL") or None
# absoluto a proposito: si no, cambia de archivo segun desde donde arranques
DB_PATH = os.path.abspath(os.path.join(ROOT, os.getenv("DB_PATH", "nextwave.db")))
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
REALTIME_VOICE = os.getenv("REALTIME_VOICE", "coral")
AGENT_NAME = os.getenv("AGENT_NAME", "Marina")

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

SIMULATE_CALLS = os.getenv("SIMULATE_CALLS", "1") == "1"
SIMULATE_DISPATCH = os.getenv("SIMULATE_DISPATCH", "1") == "1"
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "ops@demo.com")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "NextWave <onboarding@resend.dev>")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", ALERT_EMAIL)
VALIDATE_TWILIO_SIGNATURE = os.getenv("VALIDATE_TWILIO_SIGNATURE", "1") == "1"
DEMO_WORKER_PHONE = os.getenv("DEMO_WORKER_PHONE", "+5491100000000")

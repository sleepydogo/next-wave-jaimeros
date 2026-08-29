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

SIMULATE_CALLS = os.getenv("SIMULATE_CALLS", "1") == "1"
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "ops@demo.com")

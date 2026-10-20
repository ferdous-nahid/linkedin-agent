"""Central configuration, loaded from .env in the project root."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def env(key, default=""):
    return os.getenv(key, default).strip()


# --- Free LLM providers (tried in order) ---
GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "auto")          # "auto" = pick newest free Flash model
GROQ_API_KEY = env("GROQ_API_KEY")
GROQ_MODEL = env("GROQ_MODEL", "auto")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY")
OPENROUTER_MODEL = env("OPENROUTER_MODEL", "auto")  # "auto" = first ":free" model found

# --- LinkedIn ---
LINKEDIN_CLIENT_ID = env("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = env("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = env("LINKEDIN_REDIRECT_URI", "http://localhost:8765/callback")
LINKEDIN_VERSION = env("LINKEDIN_VERSION", "auto")  # e.g. 202608, or auto

# --- Branding on images ---
BRAND_NAME = env("BRAND_NAME", "Md. Ferdous Hasan")
BRAND_TITLE = env("BRAND_TITLE", "Digital Growth & Marketing")
BRAND_HANDLE = env("BRAND_HANDLE", "Follow for daily marketing intel")
BRAND_ACCENT = env("BRAND_ACCENT", "#22D3EE")
BRAND_ACCENT_2 = env("BRAND_ACCENT_2", "#A78BFA")

# --- Schedule (local time, Asia/Dhaka) ---
TIMEZONE = env("TIMEZONE", "Asia/Dhaka")
MORNING_POST_AT = env("MORNING_POST_AT", "10:00")
AFTERNOON_POST_AT = env("AFTERNOON_POST_AT", "16:30")

# --- Optional failure alerts via Telegram ---
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")

DRY_RUN = env("DRY_RUN", "0") == "1"

DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logs"
TOKEN_FILE = DATA_DIR / "linkedin_token.json"
DB_FILE = DATA_DIR / "agent.db"
for d in (DATA_DIR, OUT_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

import os
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env", override=True)


def _read_file(path: Path) -> str:
    try:
        for enc in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
            try:
                t = path.read_text(encoding=enc, errors="ignore").strip()
                if t:
                    return t
            except Exception:
                continue
    except Exception:
        pass
    return ""

BOT_TOKEN: str = os.getenv("BOT_TOKEN") or _read_file(BASE / "bot_token.txt")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
CRYPTO_PAY_TOKEN: str = os.getenv("CRYPTO_PAY_TOKEN") or _read_file(BASE / "cryptobot_token.txt")

ADMIN_TG_ID: int = int(os.getenv("ADMIN_TG_ID", "0"))
ADMIN_TG_ID_2: int = 8579686950

UAH_PER_50_STARS = 39
STARS_PER_PACK = 50
UAH_PER_1_USDT = 40

CRYPTO_PAY_API_BASE = "https://pay.crypt.bot/api"

APP_URL = "https://dia1.pages.dev/"
SIGNATURE_WEBAPP_URL = "https://dia1.pages.dev/signature/"

MANAGER = "@feestwork"
MANAGER2 = "@Tseven_menenger"
MANAGER3 = "@Tseven_meneger2"

# Обов'язкові канали для підписки
REQUIRED_CHANNELS = [
    {"id": "@TSevenDia", "title": "📣 T-Seven Dia", "url": "https://t.me/TSevenDia"},
    {"id": "@tsevenDiavigyku", "title": "⭐ Відгуки", "url": "https://t.me/tsevenDiavigyku"},
]

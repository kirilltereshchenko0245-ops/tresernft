import os
from dotenv import load_dotenv

load_dotenv()

def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

API_ID = int(required("API_ID"))
API_HASH = required("API_HASH")
BOT_TOKEN = required("BOT_TOKEN")
GROUP_ID = int(required("GROUP_ID"))
POLL_INTERVAL = max(15, int(os.getenv("POLL_INTERVAL", "60")))
SESSION_NAME = os.getenv("SESSION_NAME", "tracker_session")
GIFT_IDS = [int(x.strip()) for x in os.getenv("GIFT_IDS", "").split(",") if x.strip()]
SEED_EXISTING = os.getenv("SEED_EXISTING", "true").lower() in {"1", "true", "yes", "y"}
MAX_PAGES_PER_GIFT = max(1, int(os.getenv("MAX_PAGES_PER_GIFT", "5")))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

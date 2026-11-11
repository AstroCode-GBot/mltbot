import os
from dataclasses import dataclass

def _int(name, default=0):
    try: return int(os.getenv(name, str(default)))
    except ValueError: return default

@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    owner_id: int = _int("OWNER_ID")
    admin_ids: tuple = tuple(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit())
    database_url: str = os.getenv("DATABASE_URL", "")
    storage_channel_id: int = _int("STORAGE_CHANNEL_ID")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "")
    telegram_api_mode: str = os.getenv("TELEGRAM_API_MODE", "official").lower()
    max_file_size_gb: int = _int("MAX_FILE_SIZE_GB", 10)

settings = Settings()
if not settings.bot_token:
    raise RuntimeError("BOT_TOKEN is required")
if not settings.database_url:
    raise RuntimeError("DATABASE_URL is required")
if not settings.storage_channel_id:
    raise RuntimeError("STORAGE_CHANNEL_ID is required")

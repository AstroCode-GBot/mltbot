import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException
from aiogram.types import Update
from bot import bot, dp
from config import settings
from database import init_db, close_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mlt-vault")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if settings.public_base_url and settings.webhook_secret:
        await bot.set_webhook(
            url=f"{settings.public_base_url.rstrip('/')}/telegram/{settings.webhook_secret}",
            secret_token=settings.webhook_secret,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=False,
        )
    yield
    await bot.delete_webhook()
    await close_db()
    await bot.session.close()

app = FastAPI(title="MLT CLASSES VAULT", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "project": "MLT CLASSES VAULT"}

@app.post("/telegram/{secret}")
async def telegram_webhook(request: Request, secret: str, x_telegram_bot_api_secret_token: str = Header(default="")):
    if secret != settings.webhook_secret or x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    payload = await request.json()
    update = Update.model_validate(payload, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

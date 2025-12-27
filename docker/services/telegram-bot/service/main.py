"""Telegram bot microservice for the Dementia Support Bot project."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Add the main application code path
sys.path.insert(0, "/app")

from src.bot.telegram_bot import DementiaSupportBot
from src.core.config import settings

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/logs/telegram-bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("telegram-bot-service")

# Global bot instance
bot_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global bot_instance

    # Startup
    logger.info("Starting Telegram Bot Service...")

    try:
        # Create bot instance
        bot_instance = DementiaSupportBot()

        # Webhook setup (optional)
        webhook_url = settings.get("telegram.webhook_url", "")
        if webhook_url:
            await bot_instance.setup_webhook(webhook_url)
            logger.info(f"Webhook configured: {webhook_url}")
        else:
            logger.warning("Webhook URL is not configured; using polling mode")
            # Start polling in background
            asyncio.create_task(bot_instance.start_polling())

        logger.info("Telegram Bot Service started successfully")

    except Exception as e:
        logger.error(f"Telegram Bot Service startup error: {e}")
        raise

    yield

    # Shutdown
    logger.info("Stopping Telegram Bot Service...")
    if bot_instance:
        await bot_instance.stop()
    logger.info("Telegram Bot Service stopped")


# FastAPI application
app = FastAPI(
    title="Dementia Support Telegram Bot Service",
    description="Telegram bot microservice for the Dementia Support Bot project",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check."""
    return {"status": "healthy", "service": "telegram-bot"}


@app.post("/webhook/{bot_token}")
async def webhook_handler(
    bot_token: str, request: Request, background_tasks: BackgroundTasks
):
    """Telegram webhook handler."""
    global bot_instance

    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # Token check (use the last part of the token for webhook path)
    expected_token = settings.telegram_bot_token
    if bot_token != expected_token.split(":")[-1]:
        raise HTTPException(status_code=401, detail="Invalid bot token")

    try:
        # Parse update payload
        update_data = await request.json()
        logger.debug(f"Received update: {update_data}")

        # Process update in background
        background_tasks.add_task(bot_instance.process_update, update_data)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/send-message")
async def send_message(request: Request):
    """API endpoint for sending messages through the bot."""
    global bot_instance

    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        message = data.get("message")

        if not telegram_id or not message:
            raise HTTPException(
                status_code=400, detail="telegram_id and message are required"
            )

        # Send message
        result = await bot_instance.send_message(telegram_id, message)

        return {"status": "sent", "message_id": result.message_id}

    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get bot statistics."""
    global bot_instance

    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # TODO: implement stats reporting
    return {"active_users": 0, "messages_sent_today": 0, "uptime": "running"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", 8001))

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, access_log=True)

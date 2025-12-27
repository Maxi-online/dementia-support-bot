"""Messaging microservice (auto-messages) for the Dementia Support Bot project."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict

import httpx
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add the main application code path
sys.path.insert(0, "/app")

from src.core.config import settings
from src.db.user_data import get_all_active_users
from src.utils.auto_messaging_generator import AutoMessagingGenerator

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/logs/messaging-service.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("messaging-service")

# Global state
scheduler = None
messaging_generator = None


class MessageRequest(BaseModel):
    message_type: str
    telegram_id: str = None
    day: int = None


class ScheduleMessageRequest(BaseModel):
    message_type: str
    telegram_id: str
    schedule_time: str  # ISO format
    day: int = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global scheduler, messaging_generator

    # Startup
    logger.info("Starting Messaging Service...")

    try:
        # Initialize message generator
        messaging_generator = AutoMessagingGenerator()

        # Initialize scheduler
        scheduler = AsyncIOScheduler()

        # Configure auto-messaging schedule
        await setup_auto_messaging_schedule()

        # Start scheduler
        scheduler.start()
        logger.info("Auto-messaging scheduler started")

        logger.info("Messaging Service started successfully")

    except Exception as e:
        logger.error(f"Messaging Service startup error: {e}")
        raise

    yield

    # Shutdown
    logger.info("Stopping Messaging Service...")
    if scheduler:
        scheduler.shutdown()
    logger.info("Messaging Service stopped")


async def setup_auto_messaging_schedule():
    """Configure the schedule for automated messages."""
    global scheduler

    # Schedule definitions (cron)
    message_schedules = [
        ("morning_post", "0 7 * * *"),  # 07:00 daily
        ("morning_ritual", "20 7 * * *"),  # 07:20 daily
        ("noon_health", "0 12 * * *"),  # 12:00 daily
        ("noon_task", "12 12 * * *"),  # 12:12 daily
        ("cognitive_task", "0 15 * * *"),  # 15:00 daily
        ("evening_ritual", "0 19 * * *"),  # 19:00 daily
        ("good_night", "0 20 * * *"),  # 20:00 daily
    ]

    for message_type, cron_expression in message_schedules:
        scheduler.add_job(
            send_scheduled_messages,
            CronTrigger.from_crontab(cron_expression),
            args=[message_type],
            id=f"auto_{message_type}",
            replace_existing=True,
        )
        logger.info(f"Added schedule for {message_type}: {cron_expression}")


async def send_scheduled_messages(message_type: str):
    """Send scheduled messages to all active users."""
    try:
        logger.info(f"Starting {message_type} delivery for all users")

        # Fetch all active users
        active_users = await get_all_active_users()

        for user in active_users:
            try:
                # Compute user's day number (days since registration)
                registration_date = user.created_at.date()
                current_date = datetime.now().date()
                day_number = (current_date - registration_date).days + 1

                # Limit to 30 days and then cycle
                day_number = ((day_number - 1) % 30) + 1

                # Generate message
                message_result = await messaging_generator.generate_message(
                    message_type=message_type,
                    telegram_id=str(user.telegram_id),
                    day=day_number,
                )

                if "error" in message_result:
                    logger.error(
                        f"Failed to generate {message_type} for user {user.telegram_id}: {message_result['error']}"
                    )
                    continue

                # Send via Telegram Bot Service
                await send_to_telegram_bot(
                    telegram_id=str(user.telegram_id), message=message_result["text"]
                )

                logger.debug(
                    f"Sent {message_type} to user {user.telegram_id} (day {day_number})"
                )

            except Exception as e:
                logger.error(
                    f"Failed to send {message_type} to user {user.telegram_id}: {e}"
                )
                continue

        logger.info(f"Finished sending {message_type} to {len(active_users)} users")

    except Exception as e:
        logger.error(f"send_scheduled_messages error for {message_type}: {e}")


async def send_to_telegram_bot(telegram_id: str, message: str):
    """Send a message via Telegram Bot Service."""
    telegram_bot_url = os.getenv("TELEGRAM_BOT_SERVICE_URL", "http://telegram-bot:8001")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{telegram_bot_url}/api/send-message",
            json={"telegram_id": telegram_id, "message": message},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


# FastAPI application
app = FastAPI(
    title="Dementia Support Messaging Service",
    description="Messaging microservice for the Dementia Support Bot project",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check."""
    return {"status": "healthy", "service": "messaging"}


@app.post("/generate-message")
async def generate_message(request: MessageRequest):
    """Generate a message on request."""
    global messaging_generator

    if not messaging_generator:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        result = await messaging_generator.generate_message(
            message_type=request.message_type,
            telegram_id=request.telegram_id,
            day=request.day,
        )

        return result

    except Exception as e:
        logger.error(f"Message generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send-message")
async def send_message(request: MessageRequest, background_tasks: BackgroundTasks):
    """Generate and send a message."""
    if not request.telegram_id:
        raise HTTPException(status_code=400, detail="telegram_id is required")

    try:
        # Generate message
        message_result = await generate_message(request)

        if "error" in message_result:
            raise HTTPException(status_code=500, detail=message_result["error"])

        # Background send
        background_tasks.add_task(
            send_to_telegram_bot, request.telegram_id, message_result["text"]
        )

        return {"status": "scheduled", "message": message_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Message send error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/schedule-message")
async def schedule_message(request: ScheduleMessageRequest):
    """Schedule sending a message at a specific time."""
    global scheduler

    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    try:
        schedule_time = datetime.fromisoformat(request.schedule_time)

        # Create a scheduler job
        job_id = f"scheduled_{request.telegram_id}_{schedule_time.isoformat()}"

        scheduler.add_job(
            send_scheduled_message_to_user,
            "date",
            run_date=schedule_time,
            args=[request.message_type, request.telegram_id, request.day],
            id=job_id,
            replace_existing=True,
        )

        return {
            "status": "scheduled",
            "job_id": job_id,
            "schedule_time": schedule_time.isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to schedule message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def send_scheduled_message_to_user(
    message_type: str, telegram_id: str, day: int = None
):
    """Send a scheduled message to a specific user."""
    try:
        message_result = await messaging_generator.generate_message(
            message_type=message_type, telegram_id=telegram_id, day=day
        )

        if "error" not in message_result:
            await send_to_telegram_bot(telegram_id, message_result["text"])
            logger.info(f"Sent scheduled message {message_type} to user {telegram_id}")
        else:
            logger.error(
                f"Failed to generate scheduled message: {message_result['error']}"
            )

    except Exception as e:
        logger.error(f"Failed to send scheduled message: {e}")


@app.get("/jobs")
async def get_scheduled_jobs():
    """Get scheduled jobs/tasks."""
    global scheduler

    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "next_run": (
                    job.next_run_time.isoformat() if job.next_run_time else None
                ),
                "trigger": str(job.trigger),
            }
        )

    return {"jobs": jobs}


@app.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a scheduled job."""
    global scheduler

    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    try:
        scheduler.remove_job(job_id)
        return {"status": "cancelled", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=404, detail="Job not found")


if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", 8002))

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, access_log=True)

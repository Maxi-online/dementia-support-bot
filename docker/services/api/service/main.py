"""API microservice for the Dementia Support Bot project."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Add the main application code path
sys.path.insert(0, "/app")

from src.core.config import settings
from src.db.user_data import get_all_active_users, get_user_by_telegram_id

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/logs/api-service.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("api-service")

# Authentication
security = HTTPBearer()


class UserInfo(BaseModel):
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MessageRequest(BaseModel):
    message_type: str
    telegram_id: str
    day: Optional[int] = None


class BulkMessageRequest(BaseModel):
    message_type: str
    telegram_ids: List[str]
    day: Optional[int] = None


class SystemStats(BaseModel):
    total_users: int
    active_users: int
    messages_sent_today: int
    uptime: str
    services_status: Dict[str, str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting API Service...")

    try:
        logger.info("API Service started successfully")

    except Exception as e:
        logger.error(f"API Service startup error: {e}")
        raise

    yield

    # Shutdown
    logger.info("Stopping API Service...")
    logger.info("API Service stopped")


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API token (if configured)."""
    api_key = settings.get("security.api_key", "")
    if not api_key:
        # If no API key is configured, allow access (development mode)
        return True

    if credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


async def call_service(
    service_name: str, endpoint: str, method: str = "GET", data: dict = None
):
    """Call another microservice."""
    service_urls = {
        "messaging": settings.get(
            "services.messaging_service_url", "http://messaging-service:8002"
        ),
        "agent": settings.get(
            "services.agent_service_url", "http://agent-service:8003"
        ),
        "telegram": settings.get(
            "services.telegram_bot_url", "http://telegram-bot:8001"
        ),
    }

    if service_name not in service_urls:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service_name}")

    url = f"{service_urls[service_name]}{endpoint}"

    async with httpx.AsyncClient() as client:
        if method.upper() == "GET":
            response = await client.get(url, timeout=30.0)
        elif method.upper() == "POST":
            response = await client.post(url, json=data, timeout=30.0)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported method: {method}")

        response.raise_for_status()
        return response.json()


# FastAPI application
app = FastAPI(
    title="Dementia Support API Service",
    description="External API for the Dementia Support Bot project",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check."""
    return {"status": "healthy", "service": "api"}


# Users
@app.get("/users", response_model=List[UserInfo])
async def get_users(
    active_only: bool = Query(True, description="Only active users"),
    limit: int = Query(100, description="Maximum number of users"),
    _: bool = Depends(verify_token),
):
    """Get a list of users."""
    try:
        if active_only:
            users = await get_all_active_users()
        else:
            # TODO: add a function for fetching all users
            users = await get_all_active_users()

        users = users[:limit]

        return [
            UserInfo(
                telegram_id=user.telegram_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            for user in users
        ]

    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{telegram_id}", response_model=UserInfo)
async def get_user(telegram_id: int, _: bool = Depends(verify_token)):
    """Get user details."""
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return UserInfo(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Messages
@app.post("/messages/send")
async def send_message(request: MessageRequest, _: bool = Depends(verify_token)):
    """Send a message to a user (via the messaging service)."""
    try:
        result = await call_service(
            "messaging",
            "/send-message",
            "POST",
            {
                "message_type": request.message_type,
                "telegram_id": request.telegram_id,
                "day": request.day,
            },
        )

        return result

    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/messages/send-bulk")
async def send_bulk_messages(
    request: BulkMessageRequest, _: bool = Depends(verify_token)
):
    """Send messages in bulk."""
    try:
        results = []

        for telegram_id in request.telegram_ids:
            try:
                result = await call_service(
                    "messaging",
                    "/send-message",
                    "POST",
                    {
                        "message_type": request.message_type,
                        "telegram_id": telegram_id,
                        "day": request.day,
                    },
                )
                results.append(
                    {"telegram_id": telegram_id, "status": "sent", "result": result}
                )
            except Exception as e:
                results.append(
                    {"telegram_id": telegram_id, "status": "error", "error": str(e)}
                )

        return {"results": results}

    except Exception as e:
        logger.error(f"Failed to send bulk messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/messages/generate")
async def generate_message(request: MessageRequest, _: bool = Depends(verify_token)):
    """Generate a message without sending it."""
    try:
        result = await call_service(
            "messaging",
            "/generate-message",
            "POST",
            {
                "message_type": request.message_type,
                "telegram_id": request.telegram_id,
                "day": request.day,
            },
        )

        return result

    except Exception as e:
        logger.error(f"Failed to generate message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Agents
@app.get("/agents")
async def get_agents(_: bool = Depends(verify_token)):
    """Get a list of available agents."""
    try:
        result = await call_service("agent", "/agents", "GET")
        return result

    except Exception as e:
        logger.error(f"Failed to get agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_key}/run")
async def run_agent(
    agent_key: str, user_id: str, message: str, _: bool = Depends(verify_token)
):
    """Run an agent."""
    try:
        result = await call_service(
            "agent",
            "/run-agent",
            "POST",
            {"agent_key": agent_key, "user_id": user_id, "message": message},
        )

        return result

    except Exception as e:
        logger.error(f"Failed to run agent {agent_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Scheduler
@app.get("/scheduler/jobs")
async def get_scheduled_jobs(_: bool = Depends(verify_token)):
    """Get scheduled jobs/tasks."""
    try:
        result = await call_service("messaging", "/jobs", "GET")
        return result

    except Exception as e:
        logger.error(f"Failed to get tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Stats
@app.get("/stats", response_model=SystemStats)
async def get_system_stats(_: bool = Depends(verify_token)):
    """Get system statistics."""
    try:
        # User statistics
        active_users = await get_all_active_users()

        # Service health checks
        services_status = {}
        for service_name in ["messaging", "agent", "telegram"]:
            try:
                await call_service(service_name, "/health", "GET")
                services_status[service_name] = "healthy"
            except:
                services_status[service_name] = "unhealthy"

        return SystemStats(
            total_users=len(active_users),
            active_users=len(active_users),
            messages_sent_today=0,
            uptime="running",
            services_status=services_status,
        )

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", 8004))

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, access_log=True)

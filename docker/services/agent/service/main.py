"""LLM agent microservice for the Dementia Support Bot project."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add the main application code path
sys.path.insert(0, "/app")

from src.core.config import settings
from src.core.orchestrator import MessageOrchestrator

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/logs/agent-service.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("agent-service")

# Global orchestrator instance
orchestrator = None


class AgentRequest(BaseModel):
    agent_key: str
    user_id: str
    message: str
    extra_context: Optional[List[Dict[str, str]]] = None


class AgentResponse(BaseModel):
    content: str
    agent_type: str
    usage: Optional[Dict[str, Any]] = None


class AvailableAgent(BaseModel):
    key: str
    name: str
    description: str
    system_prompt: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global orchestrator

    # Startup
    logger.info("Starting Agent Service...")

    try:
        # Initialize orchestrator
        orchestrator = MessageOrchestrator()

        logger.info("Agent Service started successfully")

    except Exception as e:
        logger.error(f"Agent Service startup error: {e}")
        raise

    yield

    # Shutdown
    logger.info("Stopping Agent Service...")
    logger.info("Agent Service stopped")


# FastAPI application
app = FastAPI(
    title="Dementia Support Agent Service",
    description="LLM agent microservice for the Dementia Support Bot project",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check."""
    return {"status": "healthy", "service": "agent"}


@app.post("/run-agent", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """Run an agent."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        logger.info(f"Running agent {request.agent_key} for user {request.user_id}")

        result = await orchestrator.run_agent_message(
            agent_key=request.agent_key,
            user_id=request.user_id,
            message=request.message,
            extra_context=request.extra_context or [],
        )

        logger.debug(f"Agent result {request.agent_key}: {result}")

        return AgentResponse(
            content=result.get("content", ""),
            agent_type=request.agent_key,
            usage=result.get("usage"),
        )

    except Exception as e:
        logger.error(f"Agent execution error {request.agent_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents", response_model=List[AvailableAgent])
async def get_available_agents():
    """Get a list of available agents."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        agents = []

        for agent_key, agent_instance in orchestrator.agents.items():
            agents.append(
                AvailableAgent(
                    key=agent_key,
                    name=getattr(agent_instance, "name", agent_key),
                    description=getattr(
                        agent_instance, "description", f"Agent {agent_key}"
                    ),
                    system_prompt=agent_instance.get_system_prompt(),
                )
            )

        return agents

    except Exception as e:
        logger.error(f"Failed to get agent list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents/{agent_key}")
async def get_agent_info(agent_key: str):
    """Get information about a specific agent."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    if agent_key not in orchestrator.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        agent = orchestrator.agents[agent_key]

        return {
            "key": agent_key,
            "name": getattr(agent, "name", agent_key),
            "description": getattr(agent, "description", f"Agent {agent_key}"),
            "system_prompt": agent.get_system_prompt(),
            "available_functions": list(getattr(agent, "functions", {}).keys()),
        }

    except Exception as e:
        logger.error(f"Failed to get agent info {agent_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/{user_id}")
async def get_user_conversation(user_id: str, limit: int = 50):
    """Get user conversation history."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        # TODO: load history from the database
        # Placeholder response for now
        return {"user_id": user_id, "messages": [], "total_messages": 0}

    except Exception as e:
        logger.error(f"Failed to get user history {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/conversations/{user_id}")
async def clear_user_conversation(user_id: str):
    """Clear user conversation history."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        # TODO: implement clearing history
        logger.info(f"Clearing conversation history for user {user_id}")

        return {"status": "cleared", "user_id": user_id}

    except Exception as e:
        logger.error(f"Failed to clear user history {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_service_stats():
    """Get service statistics."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        return {
            "available_agents": len(orchestrator.agents),
            "agent_keys": list(orchestrator.agents.keys()),
            "uptime": "running",
            "openai_configured": bool(settings.openai_api_key),
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", 8003))

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, access_log=True)

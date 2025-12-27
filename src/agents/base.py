import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.agents.handoff import handoff
from src.core.http_client import async_client

from ..core.config import settings

logger = logging.getLogger(__name__)


def convert_functions_to_tools(functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert legacy function schemas to OpenAI's tools schema.

    This helper normalizes multiple historical representations of function/tool
    definitions into the current tools format expected by the OpenAI Chat
    Completions API:

    - Already-normalized tools: {"type": "function", "function": {...}}
    - Legacy flat functions: {"type": "function", "name": ..., "parameters": ...}

    Args:
        functions: Function/tool schemas in mixed legacy/current formats.

    Returns:
        A list of tool schemas in the tools format.
    """
    tools = []
    for func in functions:
        if func.get("type") == "function" and isinstance(func.get("function"), dict):
            tools.append(func)
            continue

        if func.get("type") == "function" and (
            "name" in func or "parameters" in func or "description" in func
        ):
            new_func = {
                "type": "function",
                "function": {
                    "name": func.get("name", "function"),
                    "description": func.get("description", ""),
                    "parameters": func.get(
                        "parameters",
                        {"type": "object", "properties": {}, "required": []},
                    ),
                },
            }
            tools.append(new_func)
            continue

        tools.append(
            {
                "type": "function",
                "function": func,
            }
        )
    return tools


class BaseAgent(ABC):
    def __init__(self, name: str = None, handoffs: Optional[List[Any]] = None):
        """Initialize the base agent."""
        self.name = name or self.__class__.__name__
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.functions = []
        self.handoffs = handoffs or []

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    async def handle_message(
        self,
        message: str,
        context: Optional[List[Dict[str, Any]]] = None,
        image: Optional[str] = None,
    ) -> str:
        """Handle a user message and return a response, optionally triggering a handoff."""
        context = context or []
        base_system_prompt = self.get_system_prompt()
        addressing_note = "Respond in English. Use a friendly, professional tone and address the user as “you”."
        messages = [
            {"role": "system", "content": f"{base_system_prompt}\n\n{addressing_note}"}
        ]
        for msg in context:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append(msg)

        messages.append({"role": "user", "content": message})

        tools = convert_functions_to_tools(self.functions) + [
            handoff.get_schema() for handoff in self.handoffs
        ]

        logger.info(f"{self.name} processing message: {message[:50]}...")
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL, messages=messages, tools=tools
        )

        reply = response.choices[0].message

        if reply.tool_calls:
            for tool_call in reply.tool_calls:
                function_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if function_name.startswith("transfer_to_"):
                    target_agent = function_name.replace("transfer_to_", "")
                    logger.info(f"{self.name} initiating handoff to {target_agent}")
                    return f"[Handoff] {target_agent}"
            # If no handoff occurred, return content
            return reply.content or "I processed your request."

        # No tool calls; just return content
        return reply.content or "I could not process your request."

    async def process_message(self, message: str) -> Dict[str, Any]:
        """Process an incoming message using the model and return structured output."""
        addressing_note = "Respond in English. Use a friendly, professional tone and address the user as “you”."
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": f"{self.get_system_prompt()}\n\n{addressing_note}",
                },
                {"role": "user", "content": message},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "process_message",
                        "description": "Processes a user message and returns an appropriate response",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "message_type": {
                                    "type": "string",
                                    "description": "Message type",
                                },
                                "response": {
                                    "type": "string",
                                    "description": "Response text",
                                },
                                "suggested_actions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Suggested actions",
                                },
                                "additional_info": {
                                    "type": "object",
                                    "description": "Additional info",
                                },
                            },
                            "required": [
                                "message_type",
                                "response",
                                "suggested_actions",
                            ],
                        },
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "process_message"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "process_message":
                raw_args = tool_call.function.arguments
                return json.loads(raw_args) if isinstance(raw_args, str) else raw_args

        # If no tool call is present, return a basic response.
        return {
            "message_type": "general",
            "response": response.choices[0].message.content
            or "Failed to process the request.",
            "suggested_actions": [],
        }

    @abstractmethod
    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (if relevant for this agent)."""
        pass

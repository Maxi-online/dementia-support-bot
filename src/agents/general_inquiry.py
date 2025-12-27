import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent

logger = logging.getLogger(__name__)


class GeneralInquiryAgent(BaseAgent):
    def __init__(self, name: str = "General Inquiry Agent"):
        """Initialize the general inquiry agent."""
        super().__init__(name=name)
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.functions = [
            {
                "type": "function",
                "function": {
                    "name": "process_message",
                    "description": "Handles general questions and ambiguous requests",
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
                            "additional_info": {
                                "type": "object",
                                "description": "Additional info",
                            },
                        },
                        "required": ["message_type", "response"],
                    },
                },
            }
        ]

    def get_system_prompt(self) -> str:
        return """You are a general inquiry assistant.
Your job is to clarify ambiguous requests and answer general questions when the user's intent is not yet clear.

Rules:
- Respond in English.
- Ask concise clarifying questions when needed.
- If the request becomes specific, trigger a handoff using the appropriate `transfer_to_` tool."""

    async def process_message(self, message: str) -> Dict[str, Any]:
        """Process a general inquiry and return structured output."""
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": message},
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "process_message",
                            "description": "Handles general questions and ambiguous requests",
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
                                    "additional_info": {
                                        "type": "object",
                                        "description": "Additional info",
                                    },
                                },
                                "required": ["message_type", "response"],
                            },
                        },
                    }
                ],
                tool_choice={
                    "type": "function",
                    "function": {"name": "process_message"},
                },
            )

            if response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                if tool_call.function.name == "process_message":
                    raw_args = tool_call.function.arguments
                    return (
                        json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    )

            # If no tool call is present, return a basic response.
            return {
                "message_type": "general",
                "response": response.choices[0].message.content
                or "Failed to process the request.",
            }
        except Exception as e:
            logger.error(f"Error processing general inquiry: {e}")
            return {
                "message_type": "error",
                "response": "An error occurred while processing the request. Please try again later.",
                "additional_info": {},
            }

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (not expected for this agent)."""
        return {
            "is_crisis": False,
            "severity": 0.0,
            "message": "This request does not appear to be a crisis.",
            "next_agent": "general",
        }

    async def handle_message(
        self,
        message: str,
        context: Optional[List[Dict[str, Any]]] = None,
        image: Optional[str] = None,
    ) -> str:
        """Handle a message and perform handoff if needed."""
        context = context or []
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        for msg in context:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append(msg)
        messages.append({"role": "user", "content": message})

        # Prepare tools (including handoff tools)
        from .base import convert_functions_to_tools

        tools = convert_functions_to_tools(self.functions) + [
            handoff.get_schema() for handoff in self.handoffs
        ]

        # Send model request
        logger.info(f"{self.name} processing message: {message[:50]}...")
        resp = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL, messages=messages, tools=tools
        )

        reply = resp.choices[0].message

        # If there is a tool call
        if reply.tool_calls:
            for tool_call in reply.tool_calls:
                function_name = tool_call.function.name

                # Check for handoff
                if function_name.startswith("transfer_to_"):
                    target_agent = function_name.replace("transfer_to_", "")
                    logger.info(f"{self.name} initiating handoff to {target_agent}")
                    return f"[Handoff] {target_agent}"

                # Handle process_message tool call
                if function_name == "process_message":
                    try:
                        args = json.loads(tool_call.function.arguments)

                        # Return response from tool call
                        return args.get("response", "I could not process your request.")
                    except Exception as e:
                        logger.error(f"Error handling general inquiry tool call: {e}")
                        return "An error occurred while processing the request. Please try again later."

        # If there is no tool call, return the message content
        content = reply.content
        logger.info(
            f"{self.name} replied to user: {content[:50] if content else 'No content'}..."
        )

        # Check for an explicit handoff marker in content
        if content and "[Handoff]" in content:
            parts = content.split("[Handoff]")
            if len(parts) > 1:
                target = parts[1].strip()
                return f"[Handoff] {target}"

        return content or "I could not process your general request."

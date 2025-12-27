import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.agents.handoff import handoff
from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent

logger = logging.getLogger(__name__)


class SleepAgent(BaseAgent):
    def __init__(self, name: str = "Sleep Agent"):
        """Initialize the sleep agent."""
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
                    "name": "provide_sleep_guidance",
                    "description": "Provides sleep routine and sleep quality recommendations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sleep_habit_recommendations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Healthy sleep habit recommendations",
                            },
                            "improvement_tips": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tips to improve sleep quality",
                            },
                        },
                        "required": ["sleep_habit_recommendations", "improvement_tips"],
                    },
                },
            }
        ]

    def get_system_prompt(self) -> str:
        return """You are a sleep assistant for people living with dementia and their caregivers.
Your job is to help establish healthy sleep routines and improve sleep quality with gentle, practical tips.

Rules:
- Respond in English.
- Keep advice safe and non-clinical; suggest consulting a clinician for severe or persistent symptoms.
- If the request is outside your scope, trigger a handoff using the appropriate `transfer_to_` tool."""

    async def provide_sleep_guidance(self, user_context: str) -> Dict[str, Any]:
        """Provide sleep guidance based on user context."""
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {
                        "role": "user",
                        "content": f"Provide sleep guidance in English, taking into account: {user_context}",
                    },
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "provide_sleep_guidance",
                            "description": "Provides sleep routine and sleep quality recommendations",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "sleep_habit_recommendations": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Healthy sleep habit recommendations",
                                    },
                                    "improvement_tips": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Tips to improve sleep quality",
                                    },
                                },
                                "required": [
                                    "sleep_habit_recommendations",
                                    "improvement_tips",
                                ],
                            },
                        },
                    }
                ],
                tool_choice={
                    "type": "function",
                    "function": {"name": "provide_sleep_guidance"},
                },
            )

            if response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                if tool_call.function.name == "provide_sleep_guidance":
                    function_args = tool_call.function.arguments
                    if isinstance(function_args, str):
                        return json.loads(function_args)
                    return function_args

            # If no tool call is present, return basic recommendations.
            return {
                "sleep_habit_recommendations": [
                    "Maintain a consistent sleep schedule."
                ],
                "improvement_tips": ["Create a comfortable sleep environment."],
            }
        except Exception as e:
            logger.error(f"Error providing sleep guidance: {e}")
            return {
                "sleep_habit_recommendations": [
                    "An error occurred while generating recommendations."
                ],
                "improvement_tips": ["Please try again later."],
            }

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (sleep-related)."""
        return {
            "is_crisis": False,
            "severity": 0.1,
            "message": "This situation does not appear to be a sleep-related crisis.",
            "next_agent": "primary",
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

                # Handle provide_sleep_guidance tool call
                if function_name == "provide_sleep_guidance":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        guidance = args

                        # Format response
                        response_text = "Here are sleep recommendations:\n\n"

                        if (
                            "sleep_habit_recommendations" in guidance
                            and guidance["sleep_habit_recommendations"]
                        ):
                            response_text += "**Healthy sleep habits**:\n"
                            for rec in guidance["sleep_habit_recommendations"]:
                                response_text += f"- {rec}\n"
                            response_text += "\n"

                        if (
                            "improvement_tips" in guidance
                            and guidance["improvement_tips"]
                        ):
                            response_text += "**Tips to improve sleep quality**:\n"
                            for tip in guidance["improvement_tips"]:
                                response_text += f"- {tip}\n"

                        return response_text
                    except Exception as e:
                        logger.error(f"Error handling sleep guidance tool call: {e}")
                        return "An error occurred while processing recommendations. Please try again later."

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

        return content or "I could not process your request related to sleep."

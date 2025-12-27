import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent

logger = logging.getLogger(__name__)


class NutritionHydrationAgent(BaseAgent):
    def __init__(self, name: str = "Nutrition and Hydration Agent"):
        """Initialize the nutrition and hydration agent."""
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
                    "name": "provide_nutrition_and_hydration_info",
                    "description": "Provides nutrition and hydration recommendations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "diet_recommendations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Balanced diet recommendations",
                            },
                            "product_suggestions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Food suggestions to support cognitive and physical health",
                            },
                            "hydration_reminders": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Hydration reminders",
                            },
                        },
                        "required": [
                            "diet_recommendations",
                            "product_suggestions",
                            "hydration_reminders",
                        ],
                    },
                },
            }
        ]

    def get_system_prompt(self) -> str:
        return """You are a nutrition and hydration assistant for people living with dementia and their caregivers.
Your job is to suggest simple, realistic diet ideas and gentle hydration reminders.

Rules:
- Respond in English.
- Avoid medical claims; encourage consulting a clinician for specific conditions or diets.
- If the request is outside your scope, trigger a handoff using the appropriate `transfer_to_` tool."""

    async def provide_nutrition_and_hydration_info(
        self, user_context: str
    ) -> Dict[str, Any]:
        """Provide nutrition and hydration recommendations based on user context."""
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {
                        "role": "user",
                        "content": f"Provide nutrition and hydration recommendations in English, taking into account: {user_context}",
                    },
                ],
                tools=self.functions,
                tool_choice={
                    "type": "function",
                    "function": {"name": "provide_nutrition_and_hydration_info"},
                },
            )

            function_args = response.choices[0].message.tool_calls[0].function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        except Exception as e:
            logger.error(f"Error providing nutrition and hydration info: {e}")
            return {
                "diet_recommendations": [
                    "An error occurred while processing your request. Please try again later."
                ],
                "product_suggestions": ["Technical issue"],
                "hydration_reminders": ["Please try again later"],
            }

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (nutrition/hydration related)."""
        return {
            "is_crisis": False,
            "severity": 0.1,
            "message": "This situation does not appear to be a nutrition/hydration-related crisis.",
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
        # Ensure handoff schemas include `type: function`
        handoff_tools = []
        for handoff in self.handoffs:
            tool = handoff.get_schema()
            if "type" not in tool:
                tool["type"] = "function"
            handoff_tools.append(tool)

        tools = self.functions + handoff_tools

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

                # Handle provide_nutrition_and_hydration_info tool call
                if function_name == "provide_nutrition_and_hydration_info":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        info = args

                        # Format response
                        response_text = (
                            "Here are nutrition and hydration recommendations:\n\n"
                        )

                        if (
                            "diet_recommendations" in info
                            and info["diet_recommendations"]
                        ):
                            response_text += "**Balanced diet**:\n"
                            for rec in info["diet_recommendations"]:
                                response_text += f"- {rec}\n"
                            response_text += "\n"

                        if (
                            "product_suggestions" in info
                            and info["product_suggestions"]
                        ):
                            response_text += "**Food suggestions**:\n"
                            for suggestion in info["product_suggestions"]:
                                response_text += f"- {suggestion}\n"
                            response_text += "\n"

                        if (
                            "hydration_reminders" in info
                            and info["hydration_reminders"]
                        ):
                            response_text += "**Hydration reminders**:\n"
                            for reminder in info["hydration_reminders"]:
                                response_text += f"- {reminder}\n"

                        return response_text
                    except Exception as e:
                        logger.error(
                            f"Error handling nutrition and hydration info tool call: {e}"
                        )
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

        return (
            content
            or "I could not process your request related to nutrition and hydration."
        )

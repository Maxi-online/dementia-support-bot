import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent, convert_functions_to_tools

logger = logging.getLogger(__name__)


class PhysicalActivityAgent(BaseAgent):
    def __init__(self, name: str = "Physical Activity Agent"):
        """Initialize the physical activity agent."""
        super().__init__(name=name)
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.functions = [
            {
                "type": "function",
                "name": "provide_physical_activity_tips",
                "description": "Provides physical activity tips",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "motivation": {
                            "type": "string",
                            "description": "Motivational text for a gentle workout",
                        },
                        "video_links": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Links to exercise videos",
                        },
                        "personalized_advice": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Personalized activity advice based on preferences",
                        },
                    },
                    "required": ["motivation", "video_links", "personalized_advice"],
                },
            }
        ]

    def get_system_prompt(self) -> str:
        return """You are a physical activity assistant for people living with dementia and their caregivers.
Your job is to encourage safe, gentle movement and provide practical activity suggestions (walking, stretching, light yoga, physiotherapy-style exercises).

Rules:
- Respond in English.
- Always prioritize safety (no risky advice; suggest consulting a clinician when needed).
- If the request is outside your scope, trigger a handoff using the appropriate `transfer_to_` tool."""

    async def provide_physical_activity_tips(self, preferences: str) -> Dict[str, Any]:
        """Provide physical activity tips based on user preferences."""
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {
                        "role": "user",
                        "content": f"Provide physical activity tips in English based on these preferences: {preferences}",
                    },
                ],
                tools=convert_functions_to_tools(self.functions),
                tool_choice={
                    "type": "function",
                    "function": {"name": "provide_physical_activity_tips"},
                },
            )

            if response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                function_args = tool_call.function.arguments
                if isinstance(function_args, str):
                    return json.loads(function_args)
                return function_args
            return {}
        except Exception as e:
            logger.error(f"Error providing physical activity tips: {e}")
            return {
                "motivation": "An error occurred while processing your request. Please try again later.",
                "video_links": ["Technical issue"],
                "personalized_advice": ["Please try again later"],
            }

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (physical-activity-related)."""
        return {
            "is_crisis": False,
            "severity": 0.1,
            "message": "This situation does not appear to be a physical-activity-related crisis.",
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

                # Handle provide_physical_activity_tips tool call
                if function_name == "provide_physical_activity_tips":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        tips = args

                        # Format response
                        response_text = (
                            "Here are physical activity recommendations:\n\n"
                        )

                        if "motivation" in tips and tips["motivation"]:
                            response_text += (
                                f"**Motivation**:\n{tips['motivation']}\n\n"
                            )

                        if "video_links" in tips and tips["video_links"]:
                            response_text += "**Exercise videos**:\n"
                            for link in tips["video_links"]:
                                response_text += f"- {link}\n"
                            response_text += "\n"

                        if (
                            "personalized_advice" in tips
                            and tips["personalized_advice"]
                        ):
                            response_text += "**Personalized advice**:\n"
                            for advice in tips["personalized_advice"]:
                                response_text += f"- {advice}\n"

                        return response_text
                    except Exception as e:
                        logger.error(
                            f"Error handling physical activity tips tool call: {e}"
                        )
                        return "An error occurred while processing tips. Please try again later."

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
            content or "I could not process your request related to physical activity."
        )

import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent, convert_functions_to_tools

logger = logging.getLogger(__name__)


class SocialActivityAgent(BaseAgent):
    def __init__(self, name: str = "Social Activity Agent"):
        """Initialize the social activity agent."""
        super().__init__(name=name)
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.functions = [
            {
                "type": "function",
                "name": "provide_social_activity_tips",
                "description": "Provides tips for social activity and maintaining social connections",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "importance_of_communication": {
                            "type": "string",
                            "description": "A reminder about why communication matters",
                        },
                        "social_activity_recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Social activity recommendations",
                        },
                        "event_recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Event recommendations",
                        },
                    },
                    "required": [
                        "importance_of_communication",
                        "social_activity_recommendations",
                        "event_recommendations",
                    ],
                },
            }
        ]

    def get_system_prompt(self) -> str:
        return """You are a social activity assistant for people living with dementia and their caregivers.
Your job is to encourage safe, realistic social connection and suggest simple social activities.

Rules:
- Respond in English.
- Keep recommendations practical, low-pressure, and tailored to the user's context.
- If the request is outside your scope, trigger a handoff using the appropriate `transfer_to_` tool."""

    async def provide_social_activity_tips(self, user_context: str) -> Dict[str, Any]:
        """Provide social activity tips based on user context."""
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {
                        "role": "user",
                        "content": f"Provide social activity tips in English, taking into account: {user_context}",
                    },
                ],
                tools=convert_functions_to_tools(self.functions),
                tool_choice={
                    "type": "function",
                    "function": {"name": "provide_social_activity_tips"},
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
            logger.error(f"Error providing social activity tips: {e}")
            return {
                "importance_of_communication": "An error occurred while processing your request. Please try again later.",
                "social_activity_recommendations": ["Technical issue"],
                "event_recommendations": ["Please try again later"],
            }

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (social-activity-related)."""
        return {
            "is_crisis": False,
            "severity": 0.1,
            "message": "This situation does not appear to be a social-activity-related crisis.",
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

                # Handle provide_social_activity_tips tool call
                if function_name == "provide_social_activity_tips":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        tips = args

                        # Format response
                        response_text = "Here are social activity recommendations:\n\n"

                        if (
                            "importance_of_communication" in tips
                            and tips["importance_of_communication"]
                        ):
                            response_text += f"**Why communication matters**:\n{tips['importance_of_communication']}\n\n"

                        if (
                            "social_activity_recommendations" in tips
                            and tips["social_activity_recommendations"]
                        ):
                            response_text += "**Social activity ideas**:\n"
                            for rec in tips["social_activity_recommendations"]:
                                response_text += f"- {rec}\n"
                            response_text += "\n"

                        if (
                            "event_recommendations" in tips
                            and tips["event_recommendations"]
                        ):
                            response_text += "**Event ideas**:\n"
                            for event in tips["event_recommendations"]:
                                response_text += f"- {event}\n"

                        return response_text
                    except Exception as e:
                        logger.error(
                            f"Error handling social activity tips tool call: {e}"
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

        return content or "I could not process your request related to social activity."

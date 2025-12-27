import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.agents.handoff import handoff
from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent, convert_functions_to_tools

logger = logging.getLogger(__name__)


class EmotionalWellbeingAgent(BaseAgent):
    def __init__(
        self,
        name: str = "Emotional Wellbeing Agent",
        handoffs: Optional[List[Any]] = None,
    ):
        """Initialize the emotional wellbeing agent."""
        super().__init__(name=name, handoffs=handoffs)
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.functions = [
            {
                "type": "function",
                "name": "provide_emotional_wellbeing_tips",
                "description": "Provides emotional wellbeing tips",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meditation_practices": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Meditation practices",
                        },
                        "affirmations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Affirmations",
                        },
                        "positive_messages": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Positive messages",
                        },
                        "anecdotes_and_jokes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Short jokes and light anecdotes to lift the mood",
                        },
                    },
                    "required": [
                        "meditation_practices",
                        "affirmations",
                        "positive_messages",
                        "anecdotes_and_jokes",
                    ],
                },
            }
        ]

    def get_system_prompt(self) -> str:
        return """You are an emotional wellbeing assistant for people living with dementia and their caregivers.
Your job is to support emotional comfort and provide gentle, uplifting content (simple meditation, affirmations, positive messages, light jokes).

Rules:
- Respond in English.
- Keep the tone warm, calm, and non-judgmental.
- Use the available function/tool schema to output structured information.
- If the request is outside your scope, trigger a handoff using the appropriate `transfer_to_` tool."""

    async def provide_emotional_wellbeing_tips(
        self, user_context: str
    ) -> Dict[str, Any]:
        """Provide emotional wellbeing tips based on user context."""
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {
                        "role": "user",
                        "content": f"Provide emotional wellbeing tips in English, taking into account: {user_context}",
                    },
                ],
                tools=convert_functions_to_tools(self.functions),
                tool_choice={
                    "type": "function",
                    "function": {"name": "provide_emotional_wellbeing_tips"},
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
            logger.error(f"Error providing emotional wellbeing tips: {e}")
            return {
                "meditation_practices": ["An error occurred while generating tips."],
                "affirmations": ["Please try again later."],
                "positive_messages": ["Sorry for the inconvenience."],
                "anecdotes_and_jokes": ["Technical issue"],
            }

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (emotional wellbeing related)."""
        return {
            "is_crisis": False,
            "severity": 0.1,
            "message": "This situation does not appear to be an emotional wellbeing crisis.",
            "next_agent": "primary",
        }

    async def handle_message(
        self,
        message: str,
        context: Optional[List[dict]] = None,
        image: Optional[str] = None,
    ) -> str:
        """Handle a user message and return either a response or a handoff directive."""
        context = context or []
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        # Include previous context if present
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

                # Handle provide_emotional_wellbeing_tips tool call
                if function_name == "provide_emotional_wellbeing_tips":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        tips = args

                        # Format response
                        response_text = "Here are emotional wellbeing tips:\n\n"

                        if (
                            "meditation_practices" in tips
                            and tips["meditation_practices"]
                        ):
                            response_text += "**Meditation practices**:\n"
                            for practice in tips["meditation_practices"]:
                                response_text += f"- {practice}\n"
                            response_text += "\n"

                        if "affirmations" in tips and tips["affirmations"]:
                            response_text += "**Affirmations**:\n"
                            for affirmation in tips["affirmations"]:
                                response_text += f"- {affirmation}\n"
                            response_text += "\n"

                        if "positive_messages" in tips and tips["positive_messages"]:
                            response_text += "**Positive messages**:\n"
                            for message in tips["positive_messages"]:
                                response_text += f"- {message}\n"
                            response_text += "\n"

                        if (
                            "anecdotes_and_jokes" in tips
                            and tips["anecdotes_and_jokes"]
                        ):
                            response_text += "**Jokes and light anecdotes**:\n"
                            for joke in tips["anecdotes_and_jokes"]:
                                response_text += f"- {joke}\n"

                        return response_text
                    except Exception as e:
                        logger.error(
                            f"Error handling emotional wellbeing tips tool call: {e}"
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
            content
            or "I could not process your request related to emotional wellbeing."
        )

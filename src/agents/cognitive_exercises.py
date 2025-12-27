import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.agents.handoff import handoff
from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent, convert_functions_to_tools

logger = logging.getLogger(__name__)


class CognitiveExercisesAgent(BaseAgent):
    def __init__(
        self,
        name: str = "Cognitive Exercises Agent",
        handoffs: Optional[List[Any]] = None,
    ):
        """Initialize the cognitive exercises agent."""
        super().__init__(name=name, handoffs=handoffs)
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.functions = [
            {
                "type": "function",
                "function": {
                    "name": "provide_cognitive_exercises",
                    "description": "Provides cognitive tasks and brain exercises",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "daily_puzzles": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Daily puzzles",
                            },
                            "attention_exercises": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Attention exercises",
                            },
                            "memory_exercises": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Memory exercises",
                            },
                            "logical_exercises": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Logic exercises",
                            },
                            "reading_recommendations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Reading recommendations",
                            },
                        },
                        "required": [
                            "daily_puzzles",
                            "attention_exercises",
                            "memory_exercises",
                            "logical_exercises",
                            "reading_recommendations",
                        ],
                    },
                },
            }
        ]

    def get_system_prompt(self) -> str:
        return """You are a cognitive exercises assistant for people living with dementia and their caregivers.
Your job is to provide simple, friendly brain exercises (attention, memory, logic) and reading suggestions.

Rules:
- Respond in English.
- Keep tasks short, encouraging, and adjusted to the user's level.
- Use the available function/tool schema to output structured information.
- If the request is outside your scope, trigger a handoff using the appropriate `transfer_to_` tool."""

    async def provide_cognitive_exercises(self, user_context: str) -> Dict[str, Any]:
        """Provide cognitive exercises based on user context."""
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {
                        "role": "user",
                        "content": f"Provide cognitive exercises in English, taking into account: {user_context}",
                    },
                ],
                tools=convert_functions_to_tools(self.functions),
                tool_choice={
                    "type": "function",
                    "function": {"name": "provide_cognitive_exercises"},
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
            logger.error(f"Error providing cognitive exercises: {e}")
            return {
                "daily_puzzles": ["An error occurred while generating exercises."],
                "attention_exercises": ["Please try again later."],
                "memory_exercises": ["Sorry for the inconvenience."],
                "logical_exercises": ["Technical issue"],
                "reading_recommendations": ["Please try again later."],
            }

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (not expected for this agent)."""
        return {
            "is_crisis": False,
            "severity": 0.1,
            "message": "This situation does not appear to be a cognitive-exercises-related crisis.",
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

                # Handle provide_cognitive_exercises tool call
                if function_name == "provide_cognitive_exercises":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        exercises = args

                        # Format response
                        response_text = "Here are cognitive exercises for you:\n\n"

                        if "daily_puzzles" in exercises and exercises["daily_puzzles"]:
                            response_text += "**Daily puzzles**:\n"
                            for puzzle in exercises["daily_puzzles"]:
                                response_text += f"- {puzzle}\n"
                            response_text += "\n"

                        if (
                            "attention_exercises" in exercises
                            and exercises["attention_exercises"]
                        ):
                            response_text += "**Attention exercises**:\n"
                            for ex in exercises["attention_exercises"]:
                                response_text += f"- {ex}\n"
                            response_text += "\n"

                        if (
                            "memory_exercises" in exercises
                            and exercises["memory_exercises"]
                        ):
                            response_text += "**Memory exercises**:\n"
                            for ex in exercises["memory_exercises"]:
                                response_text += f"- {ex}\n"
                            response_text += "\n"

                        if (
                            "logical_exercises" in exercises
                            and exercises["logical_exercises"]
                        ):
                            response_text += "**Logic exercises**:\n"
                            for ex in exercises["logical_exercises"]:
                                response_text += f"- {ex}\n"
                            response_text += "\n"

                        if (
                            "reading_recommendations" in exercises
                            and exercises["reading_recommendations"]
                        ):
                            response_text += "**Reading recommendations**:\n"
                            for rec in exercises["reading_recommendations"]:
                                response_text += f"- {rec}\n"

                        return response_text
                    except Exception as e:
                        logger.error(
                            f"Error handling cognitive exercises tool call: {e}"
                        )
                        return "An error occurred while processing exercises. Please try again later."

        # If there is no tool call, return the message content
        content = reply.content
        logger.info(f"{self.name} replied to user: {content[:50]}...")

        # Check for an explicit handoff marker in content
        if content and "[Handoff]" in content:
            parts = content.split("[Handoff]")
            if len(parts) > 1:
                target = parts[1].strip()
                return f"[Handoff] {target}"

        return (
            content
            or "I could not process your request related to cognitive exercises."
        )

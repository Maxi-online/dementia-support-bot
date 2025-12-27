import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.agents.handoff import handoff
from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent, convert_functions_to_tools

logger = logging.getLogger(__name__)


class MemorySupportAgent(BaseAgent):
    def __init__(
        self, name: Optional[str] = None, handoffs: Optional[List[Any]] = None
    ):
        """Initialize the memory support agent."""
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
                    "name": "create_memory_exercise",
                    "description": "Creates a memory training exercise",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "exercise_type": {
                                "type": "string",
                                "description": "Exercise type",
                            },
                            "difficulty": {
                                "type": "string",
                                "description": "Difficulty level",
                            },
                            "instructions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Exercise instructions",
                            },
                            "materials_needed": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Materials needed",
                            },
                        },
                        "required": [
                            "exercise_type",
                            "difficulty",
                            "instructions",
                            "materials_needed",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_reminder",
                    "description": "Creates a reminder",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Reminder title",
                            },
                            "content": {
                                "type": "string",
                                "description": "Reminder content",
                            },
                            "priority": {
                                "type": "integer",
                                "description": "Priority (1-5)",
                            },
                            "frequency": {
                                "type": "string",
                                "description": "Reminder frequency",
                            },
                        },
                        "required": ["title", "content", "priority", "frequency"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "provide_orientation",
                    "description": "Provides orientation support",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "current_time": {
                                "type": "string",
                                "description": "Current time",
                            },
                            "current_date": {
                                "type": "string",
                                "description": "Current date",
                            },
                            "location": {
                                "type": "string",
                                "description": "Current location",
                            },
                            "next_activities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Next activities",
                            },
                            "orientation_tips": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Orientation tips",
                            },
                        },
                        "required": [
                            "current_time",
                            "current_date",
                            "location",
                            "next_activities",
                            "orientation_tips",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "process_message",
                    "description": "Processes a message and returns an appropriate response",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_type": {
                                "type": "string",
                                "description": "Message type (exercise, orientation, reminder, etc.)",
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
                                "description": "Additional information",
                            },
                        },
                        "required": ["message_type", "response", "suggested_actions"],
                    },
                },
            },
        ]

    def get_system_prompt(self) -> str:
        return """You are a memory support assistant for people living with dementia and their caregivers.
Your job is to offer simple memory exercises, create reminders, and provide gentle orientation support.

Rules:
- Respond in English.
- Keep instructions short, clear, and friendly.
- Adapt difficulty to the user's level and avoid frustration."""

    async def create_memory_exercise(self) -> Dict[str, Any]:
        """Create a memory training exercise using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": "Create a new memory training exercise in English.",
                },
            ],
            tools=convert_functions_to_tools(self.functions),
            tool_choice={
                "type": "function",
                "function": {"name": "create_memory_exercise"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def create_reminder(self, task: str) -> Dict[str, Any]:
        """Create a reminder using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Create a reminder in English for this task: {task}",
                },
            ],
            tools=convert_functions_to_tools(self.functions),
            tool_choice={"type": "function", "function": {"name": "create_reminder"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (not expected for this agent)."""
        return {
            "is_crisis": False,
            "severity": 0.3,
            "message": "This situation does not appear to be a crisis, but it may require attention.",
            "next_agent": "primary_care",
        }

    async def generate_memory_exercise(
        self, difficulty: str = "medium"
    ) -> Dict[str, Any]:
        """Generate a memory training exercise using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Create a memory training exercise in English. Difficulty: {difficulty}",
                },
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "create_exercise",
                        "description": "Creates a memory training exercise",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Exercise title",
                                },
                                "difficulty": {
                                    "type": "string",
                                    "description": "Difficulty level",
                                },
                                "instructions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Instructions",
                                },
                                "content": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Exercise content",
                                },
                                "expected_duration": {
                                    "type": "string",
                                    "description": "Expected duration",
                                },
                            },
                            "required": [
                                "title",
                                "difficulty",
                                "instructions",
                                "content",
                                "expected_duration",
                            ],
                        },
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "create_exercise"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def provide_orientation_help(self) -> Dict[str, Any]:
        """Provide orientation assistance using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": "Provide orientation assistance in English.",
                },
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "provide_orientation",
                        "description": "Provides orientation support",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "current_time": {
                                    "type": "string",
                                    "description": "Current time",
                                },
                                "current_date": {
                                    "type": "string",
                                    "description": "Current date",
                                },
                                "location": {
                                    "type": "string",
                                    "description": "Current location",
                                },
                                "next_activities": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Next activities",
                                },
                                "orientation_tips": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Orientation tips",
                                },
                            },
                            "required": [
                                "current_time",
                                "current_date",
                                "location",
                                "next_activities",
                                "orientation_tips",
                            ],
                        },
                    },
                }
            ],
            tool_choice={
                "type": "function",
                "function": {"name": "provide_orientation"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def process_message(self, message: str) -> Dict[str, Any]:
        """Process an incoming message using the model."""
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
                        "description": "Processes a message and returns an appropriate response",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "message_type": {
                                    "type": "string",
                                    "description": "Message type (exercise, orientation, reminder, etc.)",
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
                                    "description": "Additional information",
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
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {
            "message_type": "general",
            "response": response.choices[0].message.content
            or "Failed to process the request.",
            "suggested_actions": [],
        }

    async def handle_message(
        self,
        message: str,
        context: Optional[List[Dict[str, Any]]] = None,
        image: Optional[str] = None,
    ) -> str:
        """Handle a message and return a response, optionally triggering a handoff."""
        return await super().handle_message(message, context, image)

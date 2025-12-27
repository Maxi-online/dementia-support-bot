import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.agents.handoff import handoff
from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent, convert_functions_to_tools

logger = logging.getLogger(__name__)


class PrimaryCareAgent(BaseAgent):
    def __init__(
        self, name: Optional[str] = None, handoffs: Optional[List[Any]] = None
    ):
        """Initialize the primary care agent."""
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
                    "name": "assess_state",
                    "description": "Assesses the patient's current state",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "physical_state": {
                                "type": "object",
                                "properties": {
                                    "vital_signs": {
                                        "type": "object",
                                        "description": "Vital signs",
                                    },
                                    "symptoms": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Symptoms",
                                    },
                                },
                            },
                            "mental_state": {
                                "type": "object",
                                "properties": {
                                    "orientation": {
                                        "type": "string",
                                        "description": "Orientation in time and place",
                                    },
                                    "mood": {"type": "string", "description": "Mood"},
                                    "behavior": {
                                        "type": "string",
                                        "description": "Behavior",
                                    },
                                },
                            },
                            "recommendations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Recommendations",
                            },
                        },
                        "required": [
                            "physical_state",
                            "mental_state",
                            "recommendations",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monitor_changes",
                    "description": "Tracks changes in the patient's condition",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "changes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Detected changes",
                            },
                            "significance": {
                                "type": "string",
                                "description": "Significance of changes",
                            },
                            "actions_needed": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Actions needed",
                            },
                        },
                        "required": ["changes", "significance", "actions_needed"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "provide_care_tips",
                    "description": "Provides caregiving tips",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "daily_routine": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Daily routine tips",
                            },
                            "safety_tips": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Safety tips",
                            },
                            "communication_tips": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Communication tips",
                            },
                        },
                        "required": [
                            "daily_routine",
                            "safety_tips",
                            "communication_tips",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "emergency_response",
                    "description": "Provides instructions for an emergency situation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "severity": {
                                "type": "string",
                                "description": "Severity assessment",
                            },
                            "immediate_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Immediate actions",
                            },
                            "contact_emergency": {
                                "type": "boolean",
                                "description": "Whether emergency services should be contacted",
                            },
                            "additional_instructions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Additional instructions",
                            },
                        },
                        "required": [
                            "severity",
                            "immediate_actions",
                            "contact_emergency",
                            "additional_instructions",
                        ],
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
                            "current_context": {
                                "type": "object",
                                "properties": {
                                    "time": {
                                        "type": "string",
                                        "description": "Current time",
                                    },
                                    "date": {
                                        "type": "string",
                                        "description": "Current date",
                                    },
                                    "location": {
                                        "type": "string",
                                        "description": "Current location",
                                    },
                                },
                            },
                            "orientation_status": {
                                "type": "string",
                                "description": "Orientation status assessment",
                            },
                            "support_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Actions to support orientation",
                            },
                            "reassurance_message": {
                                "type": "string",
                                "description": "Reassuring message",
                            },
                        },
                        "required": [
                            "current_context",
                            "orientation_status",
                            "support_actions",
                            "reassurance_message",
                        ],
                    },
                },
            },
        ]

    def get_system_prompt(self) -> str:
        return """You are a primary care support assistant for people living with dementia and their caregivers.
Your job is to help assess basic state, track changes, provide general caregiving recommendations, and prioritize safety.

Rules:
- Respond in English.
- Avoid diagnosing or prescribing. Encourage contacting a licensed clinician when needed.
- In emergencies, instruct the user to contact local emergency services immediately."""

    async def assess_state(self, observations: str) -> Dict[str, Any]:
        """Assess the patient's current state using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Assess the patient's state based on these observations (English): {observations}",
                },
            ],
            tools=convert_functions_to_tools(self.functions),
            tool_choice={"type": "function", "function": {"name": "assess_state"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def monitor_changes(
        self, previous_state: Dict[str, Any], current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Track changes in condition using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Analyze changes between previous state: {previous_state} and current state: {current_state} (English).",
                },
            ],
            tools=convert_functions_to_tools(self.functions),
            tool_choice={"type": "function", "function": {"name": "monitor_changes"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation by handing off to the crisis agent."""
        return {
            "is_crisis": True,
            "severity": 0.8,
            "message": "A potential crisis situation was detected. Handing off to the crisis agent.",
            "next_agent": "crisis_intervention",
        }

    async def provide_daily_tips(self) -> Dict[str, Any]:
        """Provide daily caregiving tips using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": "Provide daily caregiving tips for a person living with dementia (English).",
                },
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "provide_care_tips",
                        "description": "Provides caregiving tips",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "daily_routine": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Daily routine tips",
                                },
                                "safety_tips": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Safety tips",
                                },
                                "communication_tips": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Communication tips",
                                },
                            },
                            "required": [
                                "daily_routine",
                                "safety_tips",
                                "communication_tips",
                            ],
                        },
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "provide_care_tips"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def help_with_orientation(self, message: str) -> Dict[str, Any]:
        """Provide orientation support using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Provide orientation support (English). User message: {message}",
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
                                "current_context": {
                                    "type": "object",
                                    "properties": {
                                        "time": {
                                            "type": "string",
                                            "description": "Current time",
                                        },
                                        "date": {
                                            "type": "string",
                                            "description": "Current date",
                                        },
                                        "location": {
                                            "type": "string",
                                            "description": "Current location",
                                        },
                                    },
                                },
                                "orientation_status": {
                                    "type": "string",
                                    "description": "Orientation status assessment",
                                },
                                "support_actions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Actions to support orientation",
                                },
                                "reassurance_message": {
                                    "type": "string",
                                    "description": "Reassuring message",
                                },
                            },
                            "required": [
                                "current_context",
                                "orientation_status",
                                "support_actions",
                                "reassurance_message",
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

    async def handle_emergency(self, situation: str) -> Dict[str, Any]:
        """Handle emergency situations using the model (general guidance)."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Emergency situation: {situation}. Provide immediate safety-first guidance in English.",
                },
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "emergency_response",
                        "description": "Provides instructions for an emergency situation",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "severity": {
                                    "type": "string",
                                    "description": "Severity assessment",
                                },
                                "immediate_actions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Immediate actions",
                                },
                                "contact_emergency": {
                                    "type": "boolean",
                                    "description": "Whether emergency services should be contacted",
                                },
                                "additional_instructions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Additional instructions",
                                },
                            },
                            "required": [
                                "severity",
                                "immediate_actions",
                                "contact_emergency",
                                "additional_instructions",
                            ],
                        },
                    },
                }
            ],
            tool_choice={
                "type": "function",
                "function": {"name": "emergency_response"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def handle_message(
        self,
        message: str,
        context: Optional[List[Dict[str, Any]]] = None,
        image: Optional[str] = None,
    ) -> str:
        """Handle a message and return a response, optionally triggering a handoff."""
        return await super().handle_message(message, context, image)

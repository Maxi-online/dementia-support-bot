import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent, convert_functions_to_tools


class FamilySupportAgent(BaseAgent):
    def __init__(
        self, name: Optional[str] = None, handoffs: Optional[List[Any]] = None
    ):
        """Initialize the family support agent."""
        super().__init__(name=name, handoffs=handoffs)
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.functions = [
            {
                "type": "function",
                "name": "provide_emotional_support",
                "description": "Provides emotional support",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "situation": {
                            "type": "string",
                            "description": "Situation description",
                        },
                        "emotional_response": {
                            "type": "string",
                            "description": "Empathetic response",
                        },
                        "coping_strategies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Coping strategies",
                        },
                        "resources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Suggested resources",
                        },
                    },
                    "required": [
                        "situation",
                        "emotional_response",
                        "coping_strategies",
                        "resources",
                    ],
                },
            },
            {
                "type": "function",
                "name": "provide_care_training",
                "description": "Provides caregiving training",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Training topic"},
                        "key_points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key points",
                        },
                        "practical_tips": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Practical tips",
                        },
                        "common_mistakes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Common mistakes",
                        },
                    },
                    "required": [
                        "topic",
                        "key_points",
                        "practical_tips",
                        "common_mistakes",
                    ],
                },
            },
            {
                "type": "function",
                "name": "help_with_organization",
                "description": "Helps organize caregiving",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "care_aspects": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Care aspects",
                        },
                        "daily_schedule": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Daily schedule",
                        },
                        "responsibilities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Responsibilities",
                        },
                        "coordination_tips": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Coordination tips",
                        },
                    },
                    "required": [
                        "care_aspects",
                        "daily_schedule",
                        "responsibilities",
                        "coordination_tips",
                    ],
                },
            },
        ]

    def get_system_prompt(self) -> str:
        return """You are a family support assistant for caregivers of people living with dementia.
Your job is to help families cope with emotional and practical aspects of caregiving.

Rules:
- Respond in English.
- Be empathetic and practical.
- Offer concrete, actionable steps.
- Encourage professional help when appropriate."""

    async def provide_emotional_support(self, situation: str) -> Dict[str, Any]:
        """Provide emotional support using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Provide emotional support in English for this situation: {situation}",
                },
            ],
            tools=[convert_functions_to_tools([self.functions[0]])[0]],
            tool_choice={
                "type": "function",
                "function": {"name": "provide_emotional_support"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def provide_care_training(self, topic: str) -> Dict[str, Any]:
        """Provide caregiving training using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Provide caregiving training in English for this topic: {topic}",
                },
            ],
            tools=[convert_functions_to_tools([self.functions[1]])[0]],
            tool_choice={
                "type": "function",
                "function": {"name": "provide_care_training"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def help_with_organization(self, request: str) -> Dict[str, Any]:
        """Help organize caregiving using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Help with organizing caregiving (English): {request}",
                },
            ],
            tools=[convert_functions_to_tools([self.functions[2]])[0]],
            tool_choice={
                "type": "function",
                "function": {"name": "help_with_organization"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Handle a crisis situation (caregiver/family context)."""
        return {
            "is_crisis": False,
            "severity": 0.4,
            "message": "This situation requires attention, but it does not appear critical.",
            "next_agent": "primary_care",
        }

    async def provide_care_guidance(self, situation: str) -> Dict[str, Any]:
        """Provide caregiving guidance using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Provide caregiving guidance in English for this situation: {situation}",
                },
            ],
            functions=[
                {
                    "name": "provide_guidance",
                    "description": "Provides caregiving guidance",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "situation_analysis": {
                                "type": "string",
                                "description": "Situation analysis",
                            },
                            "immediate_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Immediate actions",
                            },
                            "long_term_plan": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Long-term plan",
                            },
                            "support_resources": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Support resources",
                            },
                        },
                        "required": [
                            "situation_analysis",
                            "immediate_actions",
                            "long_term_plan",
                            "support_resources",
                        ],
                    },
                }
            ],
            function_call={"name": "provide_guidance"},
        )

        return response.choices[0].message.function_call.arguments

    async def suggest_household_organization(self) -> Dict[str, Any]:
        """Suggest household organization ideas using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": "Suggest household organization ideas for caregivers of a person living with dementia (English).",
                },
            ],
            functions=[
                {
                    "name": "suggest_organization",
                    "description": "Suggests household organization",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "home_adaptations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Living space adaptations",
                            },
                            "daily_routines": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Daily routines",
                            },
                            "safety_measures": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Safety measures",
                            },
                            "task_distribution": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Task assignment",
                            },
                            "organization_tips": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Organization tips",
                            },
                        },
                        "required": [
                            "home_adaptations",
                            "daily_routines",
                            "safety_measures",
                            "task_distribution",
                            "organization_tips",
                        ],
                    },
                }
            ],
            function_call={"name": "suggest_organization"},
        )

        return response.choices[0].message.function_call.arguments

    async def provide_resources(self, category: str) -> Dict[str, Any]:
        """Provide resources by category using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Provide resources (English) for category: {category}",
                },
            ],
            functions=[
                {
                    "name": "provide_resources",
                    "description": "Provides resources by category",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Resource category",
                            },
                            "description": {
                                "type": "string",
                                "description": "Category description",
                            },
                            "resources": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "contact": {"type": "string"},
                                        "availability": {"type": "string"},
                                    },
                                },
                                "description": "Resource list",
                            },
                            "additional_info": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Additional information",
                            },
                        },
                        "required": [
                            "category",
                            "description",
                            "resources",
                            "additional_info",
                        ],
                    },
                }
            ],
            function_call={"name": "provide_resources"},
        )

        return response.choices[0].message.function_call.arguments

    async def help_with_decision_making(self, situation: str) -> Dict[str, Any]:
        """Assist with decision-making using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Help make a decision in English for this situation: {situation}",
                },
            ],
            functions=[
                {
                    "name": "help_decision",
                    "description": "Helps with decision-making",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "situation_analysis": {
                                "type": "string",
                                "description": "Situation analysis",
                            },
                            "factors_to_consider": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Factors to consider",
                            },
                            "options": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "option": {"type": "string"},
                                        "pros": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "cons": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "impact": {"type": "string"},
                                    },
                                },
                                "description": "Decision options",
                            },
                            "recommendation": {
                                "type": "string",
                                "description": "Recommendation",
                            },
                        },
                        "required": [
                            "situation_analysis",
                            "factors_to_consider",
                            "options",
                            "recommendation",
                        ],
                    },
                }
            ],
            function_call={"name": "help_decision"},
        )

        return response.choices[0].message.function_call.arguments

    async def find_support_resources(self, needs: str) -> Dict[str, Any]:
        """Find support resources using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Find support resources in English for these needs: {needs}",
                },
            ],
            functions=[
                {
                    "name": "find_resources",
                    "description": "Finds support resources",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "needs_assessment": {
                                "type": "string",
                                "description": "Needs assessment",
                            },
                            "local_resources": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Local resources",
                            },
                            "online_resources": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Online resources",
                            },
                            "support_groups": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Support groups",
                            },
                        },
                        "required": [
                            "needs_assessment",
                            "local_resources",
                            "online_resources",
                            "support_groups",
                        ],
                    },
                }
            ],
            function_call={"name": "find_resources"},
        )

        return response.choices[0].message.function_call.arguments

    async def help_with_decision(self, situation: str) -> Dict[str, Any]:
        """Help with decision-making using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Help make a decision in English for this situation: {situation}",
                },
            ],
            functions=[
                {
                    "name": "assist_decision",
                    "description": "Helps make a decision",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "situation_summary": {
                                "type": "string",
                                "description": "Brief situation summary",
                            },
                            "options": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "option": {"type": "string"},
                                        "pros": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "cons": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                                "description": "Decision options",
                            },
                            "recommendation": {
                                "type": "string",
                                "description": "Recommendation",
                            },
                            "next_steps": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Next steps",
                            },
                        },
                        "required": [
                            "situation_summary",
                            "options",
                            "recommendation",
                            "next_steps",
                        ],
                    },
                }
            ],
            function_call={"name": "assist_decision"},
        )

        return response.choices[0].message.function_call.arguments

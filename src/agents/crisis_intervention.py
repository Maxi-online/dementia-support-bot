import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.agents.handoff import handoff
from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent, convert_functions_to_tools

logger = logging.getLogger(__name__)


class CrisisInterventionAgent(BaseAgent):
    def __init__(
        self, name: Optional[str] = None, handoffs: Optional[List[Any]] = None
    ):
        """Initialize the crisis intervention agent."""
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
                    "name": "assess_risk",
                    "description": "Assesses risk severity in a crisis situation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "severity": {
                                "type": "number",
                                "description": "Risk severity from 0 to 1",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "recommended_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Recommended actions",
                            },
                            "requires_emergency": {
                                "type": "boolean",
                                "description": "Whether emergency services are required",
                            },
                            "complications": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Possible complications",
                            },
                            "caregiver_recommendations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Recommendations for caregivers",
                            },
                        },
                        "required": [
                            "severity",
                            "recommended_actions",
                            "requires_emergency",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "provide_emergency_instructions",
                    "description": "Provides emergency instructions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instructions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Instructions list",
                            },
                            "priority": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "Priority values for each instruction",
                            },
                        },
                        "required": ["instructions", "priority"],
                    },
                },
            },
        ]

    def get_system_prompt(self) -> str:
        return """You are a crisis intervention assistant for people living with dementia and their caregivers.
Your job is to quickly assess crisis situations and provide immediate, safety-first guidance.

Rules:
- Respond in English.
- Be calm, concise, and explicit about safety steps.
- If there is any sign of imminent danger, urge contacting local emergency services immediately."""

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        """Analyze a crisis situation using the model and return structured risk assessment."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Analyze this crisis situation in English and assess risk: {message}",
                },
            ],
            tools=convert_functions_to_tools(self.functions),
            tool_choice={"type": "function", "function": {"name": "assess_risk"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            risk_assessment = json.loads(tool_call.function.arguments)

            if risk_assessment["severity"] >= 0.7:  # High risk
                return {
                    "is_crisis": True,
                    "severity": risk_assessment["severity"],
                    "actions": risk_assessment["recommended_actions"],
                    "requires_emergency": True,
                    "message": "Immediate intervention is required. Contact local emergency services now.",
                }
            elif risk_assessment["severity"] >= 0.4:  # Medium risk
                return {
                    "is_crisis": True,
                    "severity": risk_assessment["severity"],
                    "actions": risk_assessment["recommended_actions"],
                    "requires_emergency": False,
                    "message": "This situation requires attention and monitoring.",
                }
            else:  # Low risk
                return {
                    "is_crisis": False,
                    "severity": risk_assessment["severity"],
                    "actions": risk_assessment["recommended_actions"],
                    "requires_emergency": False,
                    "message": "This situation does not appear critical, but it still requires attention.",
                }

        # If we failed to obtain a risk assessment
        return {
            "is_crisis": False,
            "severity": 0.0,
            "actions": [],
            "requires_emergency": False,
            "message": "Unable to assess the situation. Consider contacting a qualified professional.",
        }

    async def provide_emergency_instructions(self, situation: str) -> List[str]:
        """Provide emergency instructions using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Provide emergency instructions in English for this situation: {situation}",
                },
            ],
            tools=convert_functions_to_tools(self.functions),
            tool_choice={
                "type": "function",
                "function": {"name": "provide_emergency_instructions"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            instructions = json.loads(tool_call.function.arguments)
            return instructions.get("instructions", [])

        return [
            "Unable to generate instructions. Contact a qualified medical professional."
        ]

    async def support_caregivers(self, situation: str) -> str:
        """Provide support for caregivers in a crisis situation using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Provide caregiver support in English for this situation: {situation}",
                },
            ],
        )

        return response.choices[0].message.content or "Unable to generate support."

    async def handle_message(
        self,
        message: str,
        context: Optional[List[Dict[str, Any]]] = None,
        image: Optional[str] = None,
    ) -> str:
        """Handle a message and return a response, optionally triggering a handoff."""
        return await super().handle_message(message, context, image)

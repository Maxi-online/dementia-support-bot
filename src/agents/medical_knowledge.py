import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.core.config import settings
from src.core.http_client import async_client

from .base import BaseAgent, convert_functions_to_tools


class MedicalKnowledgeAgent(BaseAgent):
    def __init__(
        self, name: Optional[str] = None, handoffs: Optional[List[Any]] = None
    ):
        """Initialize the medical knowledge agent."""
        super().__init__(name=name, handoffs=handoffs)
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.functions = [
            {
                "type": "function",
                "name": "provide_medical_info",
                "description": "Provides medical information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "condition": {
                            "type": "string",
                            "description": "Condition or symptom",
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Plain-language explanation",
                        },
                        "symptoms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Symptoms",
                        },
                        "treatments": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Treatment options (general)",
                        },
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Warnings / when to seek medical help",
                        },
                    },
                    "required": [
                        "condition",
                        "explanation",
                        "symptoms",
                        "treatments",
                        "warnings",
                    ],
                },
            },
            {
                "type": "function",
                "name": "provide_medication_info",
                "description": "Provides medication information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "medication_name": {
                            "type": "string",
                            "description": "Medication name",
                        },
                        "purpose": {
                            "type": "string",
                            "description": "Purpose / what it is used for",
                        },
                        "usage_guidelines": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Usage guidelines (general, non-prescriptive)",
                        },
                        "side_effects": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Common side effects",
                        },
                        "interactions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Potential interactions with other medications",
                        },
                    },
                    "required": [
                        "medication_name",
                        "purpose",
                        "usage_guidelines",
                        "side_effects",
                        "interactions",
                    ],
                },
            },
            {
                "type": "function",
                "name": "explain_term",
                "description": "Explains a medical term",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string", "description": "Medical term"},
                        "simple_explanation": {
                            "type": "string",
                            "description": "Simple explanation",
                        },
                        "usage_context": {
                            "type": "string",
                            "description": "Usage context",
                        },
                        "related_terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Related terms",
                        },
                    },
                    "required": [
                        "term",
                        "simple_explanation",
                        "usage_context",
                        "related_terms",
                    ],
                },
            },
            {
                "type": "function",
                "name": "provide_treatment_guidelines",
                "description": "Provides general treatment guidance",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "condition": {"type": "string", "description": "Condition"},
                        "general_approach": {
                            "type": "string",
                            "description": "General approach",
                        },
                        "specific_recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific recommendations (general)",
                        },
                        "lifestyle_changes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lifestyle changes",
                        },
                        "monitoring": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "What to monitor",
                        },
                    },
                    "required": [
                        "condition",
                        "general_approach",
                        "specific_recommendations",
                        "lifestyle_changes",
                        "monitoring",
                    ],
                },
            },
            {
                "type": "function",
                "name": "check_interactions",
                "description": "Checks medication interactions (general)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "medications": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of medications",
                        },
                        "interactions_found": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "drugs": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Interacting drugs",
                                    },
                                    "severity": {
                                        "type": "string",
                                        "description": "Interaction severity",
                                    },
                                    "effect": {
                                        "type": "string",
                                        "description": "Interaction effect",
                                    },
                                },
                            },
                            "description": "Interactions found",
                        },
                        "recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Recommendations",
                        },
                    },
                    "required": [
                        "medications",
                        "interactions_found",
                        "recommendations",
                    ],
                },
            },
        ]

    def get_system_prompt(self) -> str:
        return """You are a medical knowledge assistant for people living with dementia and their caregivers.
Your job is to provide clear, plain-language medical information and general guidance.

Rules:
- Respond in English.
- Avoid diagnosing or prescribing. Encourage consulting a licensed clinician for medical decisions.
- Include safety warnings and “when to seek urgent help” guidance when appropriate.
- Use simple language and clear structure."""

    async def explain_condition(self, condition: str) -> Dict[str, Any]:
        """Explain a medical condition using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Explain this condition in English (plain language): {condition}",
                },
            ],
            tools=[convert_functions_to_tools([self.functions[0]])[0]],
            tool_choice={
                "type": "function",
                "function": {"name": "provide_medical_info"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def provide_medication_info(self, medication: str) -> Dict[str, Any]:
        """Provide medication information using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Provide medication information in English (general, non-prescriptive): {medication}",
                },
            ],
            tools=[convert_functions_to_tools([self.functions[1]])[0]],
            tool_choice={
                "type": "function",
                "function": {"name": "provide_medication_info"},
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
        """Handle a crisis situation from a medical-information perspective."""
        return {
            "is_crisis": False,
            "severity": 0.3,
            "message": "This situation may require a medical assessment.",
            "next_agent": "crisis_intervention",
        }

    async def analyze_symptoms(self, symptoms: List[str]) -> Dict[str, Any]:
        """Analyze symptoms using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Analyze these symptoms in English (general info, no diagnosis): {', '.join(symptoms)}",
                },
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "analyze_symptoms",
                        "description": "Analyzes symptoms",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "symptoms": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Symptom list",
                                },
                                "potential_conditions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Potential conditions (informational)",
                                },
                                "severity": {
                                    "type": "string",
                                    "description": "Severity assessment",
                                },
                                "recommendations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Recommendations",
                                },
                            },
                            "required": [
                                "symptoms",
                                "potential_conditions",
                                "severity",
                                "recommendations",
                            ],
                        },
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "analyze_symptoms"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def explain_medical_term(self, term: str) -> Dict[str, Any]:
        """Explain a medical term using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Explain this medical term in English (plain language): {term}",
                },
            ],
            tools=[convert_functions_to_tools([self.functions[2]])[0]],
            tool_choice={"type": "function", "function": {"name": "explain_term"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def provide_treatment_guidelines(self, condition: str) -> Dict[str, Any]:
        """Provide general treatment guidance using the model."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Provide general (non-prescriptive) guidance in English for: {condition}",
                },
            ],
            tools=[convert_functions_to_tools([self.functions[3]])[0]],
            tool_choice={
                "type": "function",
                "function": {"name": "provide_treatment_guidelines"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

    async def check_drug_interactions(self, medications: List[str]) -> Dict[str, Any]:
        """Check potential drug interactions using the model (general information)."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": f"Check potential interactions (general info) for: {', '.join(medications)}",
                },
            ],
            tools=[convert_functions_to_tools([self.functions[4]])[0]],
            tool_choice={
                "type": "function",
                "function": {"name": "check_interactions"},
            },
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = tool_call.function.arguments
            if isinstance(function_args, str):
                return json.loads(function_args)
            return function_args
        return {}

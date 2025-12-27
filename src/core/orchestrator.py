import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.agents.handoff import handoff
from src.core.http_client import async_client

from ..agents.base import BaseAgent
from ..agents.cognitive_exercises import CognitiveExercisesAgent
from ..agents.crisis_intervention import CrisisInterventionAgent
from ..agents.emotional_wellbeing import EmotionalWellbeingAgent
from ..agents.evening_ritual import EveningRitualAgent
from ..agents.family_support import FamilySupportAgent
from ..agents.general_inquiry import GeneralInquiryAgent
from ..agents.good_night import GoodNightAgent
from ..agents.medical_knowledge import MedicalKnowledgeAgent
from ..agents.memory_support import MemorySupportAgent
from ..agents.morning_post import MorningPostAgent
from ..agents.noon_health_series import NoonHealthSeriesAgent
from ..agents.noon_task import NoonTaskAgent
from ..agents.nutrition_hydration import NutritionHydrationAgent
from ..agents.physical_activity import PhysicalActivityAgent
from ..agents.primary_care import PrimaryCareAgent
from ..agents.ritual_morning import MorningRitualAgent
from ..agents.sleep import SleepAgent
from ..agents.social_activity import SocialActivityAgent
from ..agents.stress_management import StressManagementAgent
from .config import settings

logger = logging.getLogger(__name__)


class Response(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    agent: "BaseAgent"
    messages: List[Dict[str, Any]]
    content: str


class MessageOrchestrator:
    def __init__(self):
        """Initialize the message orchestrator (agent router + conversation history)."""
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.default_agent = "general"
        self.min_routing_confidence = 0.6
        # Initialize agents
        self.init_agents()
        # Per-user dialog history storage
        self.conversation_history = []
        self.functions = [
            {
                "type": "function",
                "function": {
                    "name": "route_message",
                    "description": "Routes an incoming message to the most suitable agent",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "agent_type": {
                                "type": "string",
                                "enum": [
                                    "crisis",
                                    "memory",
                                    "medical",
                                    "family",
                                    "primary",
                                    "general",
                                    "physical_activity",
                                    "nutrition_hydration",
                                    "social_activity",
                                    "cognitive_exercises",
                                    "emotional_wellbeing",
                                    "sleep",
                                    "stress_management",
                                    "morning_post",
                                    "morning_ritual",
                                    "noon_health",
                                    "noon_task",
                                    "evening_ritual",
                                    "good_night",
                                ],
                                "description": "Agent type selected to handle the message",
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Routing confidence (0-1)",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Short explanation of why this agent was selected",
                            },
                        },
                        "required": ["agent_type", "confidence", "reasoning"],
                    },
                },
            }
        ]

    async def run_agent_message(
        self,
        agent_key: str,
        user_id: str,
        message: str,
        extra_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run a specific agent for a user message, supporting handoff and history.

        Args:
            agent_key: agent key from `self.agents`
            user_id: user identifier (telegram_id)
            message: user message
            extra_context: extra message context (role/content)

        Returns:
            dict with: content, agent_name, agent_key
        """
        if agent_key not in self.agents:
            agent_key = self.default_agent

        # Build context: recent dialog + external context
        history = self.get_conversation_history(user_id)
        context: List[Dict[str, Any]] = []
        for exchange in history[-3:]:
            context.append({"role": "user", "content": exchange.get("message", "")})
            context.append(
                {"role": "assistant", "content": exchange.get("response", "")}
            )
        if extra_context:
            context.extend(extra_context)

        # Run a full turn with the selected agent (with handoff support)
        result = await self._run_full_turn(
            self.agents[agent_key], message, context, user_id
        )

        # Save to in-memory history
        self.conversation_history.append(
            {
                "user_id": user_id,
                "message": message,
                "response": result.content,
                "agent": result.agent.name,
            }
        )

        # Find the final agent key by agent object identity
        final_key = None
        for k, a in self.agents.items():
            if a is result.agent:
                final_key = k
                break

        return {
            "content": result.content,
            "agent_name": result.agent.name,
            "agent_key": final_key or agent_key,
        }

    def init_agents(self):
        """Initialize all agents and configure their mutual handoffs."""
        # Create agents
        self.agents = {
            "crisis": CrisisInterventionAgent(name="Crisis Intervention Agent"),
            "memory": MemorySupportAgent(name="Memory Support Agent"),
            "medical": MedicalKnowledgeAgent(name="Medical Knowledge Agent"),
            "family": FamilySupportAgent(name="Family Support Agent"),
            "primary": PrimaryCareAgent(name="Primary Care Agent"),
            "general": GeneralInquiryAgent(name="General Inquiry Agent"),
            "physical_activity": PhysicalActivityAgent(name="Physical Activity Agent"),
            "nutrition_hydration": NutritionHydrationAgent(
                name="Nutrition and Hydration Agent"
            ),
            "social_activity": SocialActivityAgent(name="Social Activity Agent"),
            "cognitive_exercises": CognitiveExercisesAgent(
                name="Cognitive Exercises Agent"
            ),
            "emotional_wellbeing": EmotionalWellbeingAgent(
                name="Emotional Wellbeing Agent"
            ),
            "sleep": SleepAgent(name="Sleep Agent"),
            "stress_management": StressManagementAgent(name="Stress Management Agent"),
            "morning_post": MorningPostAgent(name="Morning Post Agent"),
            "morning_ritual": MorningRitualAgent(name="Morning Ritual Agent"),
            "noon_health": NoonHealthSeriesAgent(name="Noon Health Series Agent"),
            "noon_task": NoonTaskAgent(name="Noon Task Agent"),
            "evening_ritual": EveningRitualAgent(name="Evening Ritual Agent"),
            "good_night": GoodNightAgent(name="Good Night Agent"),
        }

        # Create handoff tools for each agent
        self.handoff_tools = {}
        for key, agent in self.agents.items():
            self.handoff_tools[key] = {}
            for target_key, target_agent in self.agents.items():
                if key != target_key:
                    self.handoff_tools[key][target_key] = handoff(
                        target_agent,
                        f"transfer_to_{target_key}",
                        f"Hand off the conversation to agent {target_agent.name}. Use this tool when the request belongs to: {target_key}.",
                    )

        # Assign handoff tools to each agent
        for key, agent in self.agents.items():
            agent.handoffs = list(self.handoff_tools[key].values())

    def get_system_prompt(self) -> str:
        return """You are the message orchestrator for a dementia support system.
Your job is to choose the best agent to handle an incoming user message.

Rules:
- Output your routing decision using the `route_message` tool.
- Keep `reasoning` short and concrete.

Available agents:
1) crisis - Crisis situations and emergency guidance
2) memory - Memory support and cognitive exercises
3) medical - Medical information and general guidance
4) family - Family/caregiver support
5) primary - Primary care support and caregiving tips
6) general - General questions and clarification
7) physical_activity - Physical activity and exercises
8) nutrition_hydration - Nutrition and hydration
9) social_activity - Social activity and connection
10) cognitive_exercises - Cognitive tasks and brain exercises
11) emotional_wellbeing - Emotional wellbeing
12) sleep - Sleep routines and improvement
13) stress_management - Stress reduction and relaxation
"""

    async def process_message(self, message: str, user_id: str) -> Dict[str, Any]:
        """Process an incoming message and route it to the appropriate agent."""
        # First, summarize recent dialog for routing context
        summary = await self.summarize_conversation(user_id)
        logger.info(f"Conversation summary for user {user_id}: {summary}")

        # Determine the best agent for this message
        current_agent = await self._determine_agent(message, summary)
        logger.info(f"Selected agent: {current_agent.name}")

        # Build context from recent history
        history = self.get_conversation_history(user_id)
        context = []
        for exchange in history[-3:]:
            context.append({"role": "user", "content": exchange.get("message", "")})
            context.append(
                {"role": "assistant", "content": exchange.get("response", "")}
            )

        # Process message with the selected agent
        response = await self._run_full_turn(current_agent, message, context, user_id)

        # Save exchange to history
        self.conversation_history.append(
            {
                "user_id": user_id,
                "message": message,
                "response": response.content,
                "agent": response.agent.name,
            }
        )

        return {"content": response.content, "agent": response.agent.name}

    async def _determine_agent(self, message: str, summary: str = "") -> BaseAgent:
        """Determine the best agent to handle the message."""
        # Build routing messages with summary context
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {
                "role": "system",
                "content": f"Short summary of the previous dialog: {summary}",
            },
            {"role": "user", "content": message},
        ]
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "route_message",
                        "description": "Determines the routing decision for a message",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "agent_type": {
                                    "type": "string",
                                    "enum": [
                                        "crisis",
                                        "memory",
                                        "medical",
                                        "family",
                                        "primary",
                                        "general",
                                        "physical_activity",
                                        "nutrition_hydration",
                                        "social_activity",
                                        "cognitive_exercises",
                                        "emotional_wellbeing",
                                        "sleep",
                                        "stress_management",
                                        "morning_post",
                                        "morning_ritual",
                                        "noon_health",
                                        "noon_task",
                                        "evening_ritual",
                                        "good_night",
                                    ],
                                    "description": "Agent type to handle the message",
                                },
                                "confidence": {
                                    "type": "number",
                                    "description": "Confidence score (0-1)",
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Short rationale",
                                },
                            },
                            "required": ["agent_type", "confidence", "reasoning"],
                        },
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "route_message"}},
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "route_message":
                raw_args = tool_call.function.arguments
                route = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

                # Check confidence score
                confidence = route.get("confidence", 0)
                agent_type = route.get("agent_type")

                if confidence < self.min_routing_confidence:
                    logger.warning(
                        f"Low routing confidence {confidence}, falling back to '{self.default_agent}' agent"
                    )
                    agent_type = self.default_agent

                return self.agents[agent_type]

        # If routing fails, use the default agent
        logger.warning(
            f"Failed to determine agent, falling back to '{self.default_agent}' agent"
        )
        return self.agents[self.default_agent]

    async def _run_full_turn(
        self,
        agent: BaseAgent,
        message: str,
        context: List[Dict[str, Any]],
        user_id: str,
    ) -> Response:
        """Run a full agent turn, including possible handoffs."""
        current_agent = agent
        messages = []
        content = await current_agent.handle_message(message, context)

        # Check whether the response is a handoff directive
        if isinstance(content, str) and content.startswith("[Handoff]"):
            # Handoff to another agent
            target_agent_key = content.replace("[Handoff]", "").strip()
            if target_agent_key in self.agents:
                logger.info(f"Handoff from {current_agent.name} to {target_agent_key}")
                current_agent = self.agents[target_agent_key]
                # Re-run processing with the new agent
                content = await current_agent.handle_message(message, context)
            else:
                logger.warning(
                    f"Invalid handoff target: {target_agent_key}, staying with {current_agent.name}"
                )

        # Append processed messages to the context
        messages.append({"role": "user", "content": message})
        messages.append({"role": "assistant", "content": content})

        return Response(agent=current_agent, messages=messages, content=content)

    def get_conversation_history(self, user_id: str) -> list:
        """Return the conversation history for a user."""
        return [
            exchange
            for exchange in self.conversation_history
            if exchange["user_id"] == user_id
        ]

    async def analyze_conversation(self, user_id: str) -> Dict[str, Any]:
        """Analyze conversation history and provide recommendations."""
        history = self.get_conversation_history(user_id)

        # Analyze using the medical agent
        medical_agent = self.agents["medical"]

        # Collect all user messages
        user_messages = [exchange["message"] for exchange in history]

        # Analyze symptoms and overall state
        analysis = await medical_agent.analyze_symptoms(user_messages)

        return {
            "analysis": analysis,
            "recommendations": {
                "next_agent": self._determine_next_agent(analysis),
                "actions": self._get_recommended_actions(analysis),
            },
        }

    def _determine_next_agent(self, analysis: Dict[str, Any]) -> str:
        """Determine the next agent based on analysis."""
        severity = analysis.get("severity", "")

        if severity == "high":
            return "crisis"
        elif severity == "medium":
            return "medical"
        else:
            return "primary"

    def _get_recommended_actions(self, analysis: Dict[str, Any]) -> list:
        """Determine recommended actions based on analysis."""
        return analysis.get("recommendations", [])

    async def get_agent_capabilities(self) -> Dict[str, list]:
        """Return a description of each agent's capabilities."""
        return {
            agent_key: [f"Handles requests related to {agent.name}"]
            for agent_key, agent in self.agents.items()
        }

    async def summarize_conversation(
        self, user_id: str, model: Optional[str] = None
    ) -> str:
        """Compress a user's conversation history into a short routing summary."""
        history = self.get_conversation_history(user_id)
        logger.info(
            f"Summarize_conversation called for user {user_id}. History entries: {len(history)}"
        )
        if not history:
            return ""
        # Take the last 10 exchanges
        formatted = []
        for exchange in history[-10:]:
            formatted.append(f"User: {exchange['message']}")
            formatted.append(
                f"Assistant ({exchange.get('agent', 'unknown')}): {exchange.get('response', '')}"
            )
        history_text = "\n".join(formatted)
        logger.debug(f"History text for summarization: {history_text[:200]}...")
        prompt_messages = [
            {
                "role": "system",
                "content": "You create short summaries of user/assistant dialogs for routing. Summarize the key points of the following exchanges.",
            },
            {"role": "user", "content": f"Dialog history:\n{history_text}"},
        ]
        resp = await self.client.chat.completions.create(
            model=model or settings.OPENAI_MODEL,
            messages=prompt_messages,
            # temperature=0.3,
            max_completion_tokens=200,
        )
        summary = resp.choices[0].message.content
        logger.info(f"Summary generated for user {user_id}: {summary[:100]}...")
        return summary

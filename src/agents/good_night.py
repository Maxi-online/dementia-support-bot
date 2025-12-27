from typing import Any, Dict, List, Optional

from .base import BaseAgent


class GoodNightAgent(BaseAgent):
    def __init__(
        self, name: str = "Good Night Agent", handoffs: Optional[List[Any]] = None
    ):
        super().__init__(name=name, handoffs=handoffs)

    def get_system_prompt(self) -> str:
        return (
            "You are the assistant for the 20:00 “Good night” message. "
            "Write in English: 2–4 warm supportive sentences (e.g., “You did well today. You showed care.”), "
            "and a gentle closing. No tasks and no reminders."
        )

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        return {
            "message_type": "crisis",
            "content": "If this is an emergency, contact local emergency services immediately. I can hand off to the crisis specialist.",
            "actions": ["transfer_to_crisis"],
            "additional_info": {},
        }

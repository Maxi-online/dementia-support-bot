from typing import Any, Dict, List, Optional

from .base import BaseAgent


class MorningPostAgent(BaseAgent):
    def __init__(
        self, name: str = "Morning Post Agent", handoffs: Optional[List[Any]] = None
    ):
        super().__init__(name=name, handoffs=handoffs)

    def get_system_prompt(self) -> str:
        return (
            "You are the assistant for the 07:00 morning posts of the “Dementia Support Bot” project. "
            "Write in English, concise (60–90 words), upbeat, friendly, and respectful. "
            "Structure: warm greeting (1–2 sentences) → 1–2 energizing lines → “Motto of the day” (one line) → a quote (1–2 lines). "
            "Emojis: 1–3 relevant. No links. No lecturing."
        )

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        return {
            "message_type": "crisis",
            "content": "I understand this may feel urgent or overwhelming. Please contact a trusted person or local emergency/medical services right now. I can hand off to the crisis agent.",
            "actions": ["transfer_to_crisis"],
            "additional_info": {},
        }

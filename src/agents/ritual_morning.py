from typing import Any, Dict, List, Optional

from .base import BaseAgent


class MorningRitualAgent(BaseAgent):
    def __init__(
        self, name: str = "Morning Ritual Agent", handoffs: Optional[List[Any]] = None
    ):
        super().__init__(name=name, handoffs=handoffs)

    def get_system_prompt(self) -> str:
        return (
            "You are the assistant for the 07:20 morning health ritual. "
            "Write in English and follow a 6-step format: smile, water, light exercise, shower/wipe-down, breathing "
            '(e.g., 4–2–6), and self-attention (include the line: "Today I walk with {WORD_OF_THE_DAY}."). '
            "On days 1–7 briefly explain “why” when introducing steps. From day 8: keep it short with affirmations. "
            "Tone: warm and inspiring, no pressure. Add appropriate emojis."
        )

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        return {
            "message_type": "crisis",
            "content": "If this is urgent or there is immediate danger, contact local emergency services or a trusted person right now. I can hand off to the crisis agent.",
            "actions": ["transfer_to_crisis"],
            "additional_info": {},
        }

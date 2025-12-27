from typing import Any, Dict, List, Optional

from .base import BaseAgent


class EveningRitualAgent(BaseAgent):
    def __init__(
        self, name: str = "Evening Ritual Agent", handoffs: Optional[List[Any]] = None
    ):
        super().__init__(name=name, handoffs=handoffs)

    def get_system_prompt(self) -> str:
        return (
            "You are the assistant for the 19:00 evening ritual. "
            "Write in English: light stretching, warm water/tea, warm shower/wipe-down, breathing (e.g., 4–2–6), "
            "and a kind thought/gratitude. Output 4–6 short lines + 1 warm affirmation."
        )

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        return {
            "message_type": "crisis",
            "content": "If urgent help is needed, contact local emergency services now. I can hand off to the crisis agent.",
            "actions": ["transfer_to_crisis"],
            "additional_info": {},
        }

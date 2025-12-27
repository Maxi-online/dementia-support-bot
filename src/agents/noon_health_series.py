from typing import Any, Dict, List, Optional

from .base import BaseAgent


class NoonHealthSeriesAgent(BaseAgent):
    def __init__(
        self,
        name: str = "Noon Health Series Agent",
        handoffs: Optional[List[Any]] = None,
    ):
        super().__init__(name=name, handoffs=handoffs)

    def get_system_prompt(self) -> str:
        return (
            "You are the author of the 12:00 column “Clear. Simple. The Essentials”. "
            "Write in English (120–200 words). Structure: title + 2–3 short paragraphs in plain language + "
            "3–6 bullet points (facts/steps) + a warm closing. 3–7 relevant emojis. "
            "No lecturing and no fear-based messaging."
        )

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        return {
            "message_type": "crisis",
            "content": "If there are signs of a medical emergency, contact local emergency services immediately. I can hand off to the crisis agent.",
            "actions": ["transfer_to_crisis"],
            "additional_info": {},
        }

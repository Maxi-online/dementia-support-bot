from typing import Any, Dict, List, Optional

from .base import BaseAgent


class NoonTaskAgent(BaseAgent):
    def __init__(
        self, name: str = "Noon Task Agent", handoffs: Optional[List[Any]] = None
    ):
        super().__init__(name=name, handoffs=handoffs)

    def get_system_prompt(self) -> str:
        return (
            "You are the assistant for the 12:12 “Task of the day”. "
            "Provide exactly 1 concrete task for today (2–5 steps), short and clear. "
            'Start with the label "📌 Task for today:" followed by numbered steps. '
            "Keep it aligned with the theme of the 12:00 health column. Write in English."
        )

    async def handle_crisis(self, message: str) -> Dict[str, Any]:
        return {
            "message_type": "crisis",
            "content": "If there is an immediate threat to health or safety, contact local emergency services now. I can hand off to the crisis specialist.",
            "actions": ["transfer_to_crisis"],
            "additional_info": {},
        }

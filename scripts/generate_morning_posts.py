import asyncio
import os
import sys
from typing import Optional

# Ensure project root is on sys.path when running as a script
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.auto_messaging_generator import AutoMessagingGenerator


async def main(
    message_type: str = "morning_post",
    days: int = 10,
    telegram_id: Optional[str] = None,
) -> None:
    generator = AutoMessagingGenerator()
    for day_index in range(1, days + 1):
        result = await generator.generate_message(
            message_type=message_type, telegram_id=telegram_id, day=day_index
        )
        text = (result.get("text") or "").strip()
        print(f"--- Day {day_index} ({message_type}) ---")
        print(text)
        print()


if __name__ == "__main__":
    import sys

    msg_type = sys.argv[1] if len(sys.argv) > 1 else "morning_post"
    try:
        num_days = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    except ValueError:
        num_days = 10

    asyncio.run(main(message_type=msg_type, days=num_days))

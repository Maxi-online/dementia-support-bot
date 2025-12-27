import logging
from typing import Optional

import httpx
from openai import OpenAI

from src.core.config import settings

logger = logging.getLogger(__name__)

# Initialize a synchronous OpenAI client once at module level
_openai_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Lazily initialize and return an OpenAI client."""
    global _openai_client
    if _openai_client is None:
        try:
            # Use a dedicated HTTP client for the synchronous OpenAI SDK.
            http_client = httpx.Client(timeout=30.0)
            _openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.openai_base_url,
                http_client=http_client,
            )
        except Exception as exc:
            logger.exception("Failed to initialize OpenAI client: %s", exc)
            raise
    return _openai_client


def generate_reminder_text(theme: str, category_key: str, default_title: str) -> str:
    """Generate reminder text using the model.

    Args:
        theme: Weekly theme (e.g. "Exercise").
        category_key: Category key (e.g. "good_morning", "education").
        default_title: Default title (also provided to the model).

    Returns:
        Generated reminder text. If generation fails, returns `default_title`.
    """
    system_prompt = (
        "You are an assistant for the “Dementia Support Bot” program. "
        "Your task is to create short (1–2 sentences, up to 40 words) motivational or educational "
        "reminder messages. The final message MUST be in English. "
        "The message must match the weekly theme and the category. Avoid repetition."
    )

    user_prompt = (
        f"Weekly theme: {theme}. Category: {category_key}. "
        f"Default title: {default_title}. Generate the reminder text in English."
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            # temperature=0.7,
            max_completion_tokens=120,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("Failed to generate reminder text: %s", exc)
        # Fallback: return default title
        return default_title

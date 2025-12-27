"""Auto-messaging content generator (routes generation through agents via the orchestrator + handoff)."""

import json
import logging
import os
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.core.orchestrator import MessageOrchestrator
from src.db.models import Conversation, TelegramUser

logger = logging.getLogger(__name__)


class AutoMessagingGenerator:
    def __init__(self):
        """Initialize the automated messaging generator."""
        # Use the orchestrator so all generation goes through agents with handoff support
        self.orchestrator = MessageOrchestrator()
        # Load auto-messaging configuration
        config_path = os.path.join(
            os.path.dirname(__file__), "auto_messaging_config.json"
        )
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                self.config = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load auto-messaging config: {e}")
            self.config = {"auto_messages": []}

        # Per-user context for continuing a conversation after an automated message
        self.user_context = {}

    async def generate_message(
        self, message_type: str, telegram_id: str = None, day: int = None
    ) -> Dict[str, Any]:
        """
        Return a ready-made message from config or generate one via an agent.

        Args:
            message_type: Message type identifier from config
            telegram_id: Telegram user ID (optional)
            day: Day number (used to select a ready-made text)

        Returns:
            Dict with message text and metadata
        """
        # Find message config by ID
        message_config = None
        for msg in self.config["auto_messages"]:
            if msg["id"] == message_type:
                message_config = msg
                break

        if not message_config:
            logger.error(f"Config not found for message type: {message_type}")
            return {"text": "Message generation error", "error": "config_not_found"}

        # Pick a random topic
        topic = random.choice(message_config["topics"])

        # Use ready-made texts when available for a given day
        if day and "ready_texts" in message_config:
            day_key = f"day_{day}"
            if day_key in message_config["ready_texts"]:
                ready_text = message_config["ready_texts"][day_key]
                logger.info(f"Using ready-made text for {message_type}, day {day}")

                # Persist context for follow-up replies
                if telegram_id:
                    self.user_context[telegram_id] = {
                        "agent_type": message_config["agent_type"],
                        "last_topic": topic,
                        "message_type": message_type,
                        "day": day,
                        "timestamp": datetime.now().isoformat(),
                    }

                return {
                    "text": ready_text,
                    "type": message_type,
                    "agent_type": message_config["agent_type"],
                    "topic": topic,
                    "media_type": message_config["media_type"],
                    "ready_text": True,
                    "day": day,
                }

        # If no ready-made text is found, generate via an agent
        system_prompt = message_config["template"]["system_prompt"]
        user_prompt = message_config["template"]["user_prompt"].format(topic=topic)
        agent_key = message_config["agent_type"]

        try:
            # Generate text through the selected agent with handoff support
            user_id = telegram_id or f"broadcast:{message_type}"
            result = await self.orchestrator.run_agent_message(
                agent_key=agent_key,
                user_id=user_id,
                message=user_prompt,
                extra_context=[{"role": "system", "content": system_prompt}],
            )
            generated_text = (result.get("content") or "").strip()
            # If the response is a handoff directive, retry on the target agent
            if generated_text.startswith("[Handoff] "):
                target_key = generated_text.replace("[Handoff] ", "").strip()
                result = await self.orchestrator.run_agent_message(
                    agent_key=target_key,
                    user_id=user_id,
                    message=user_prompt,
                    extra_context=[{"role": "system", "content": system_prompt}],
                )
                generated_text = (result.get("content") or "").strip()

            # Persist context for follow-up replies
            if telegram_id:
                self.user_context[telegram_id] = {
                    "agent_type": agent_key,
                    "last_topic": topic,
                    "system_prompt": system_prompt,
                    # The orchestrator stores dialog history; here we store only metadata
                    "timestamp": datetime.now().isoformat(),
                }

            # Return generated message and metadata
            return {
                "text": generated_text,
                "type": message_type,
                "agent_type": message_config["agent_type"],
                "topic": topic,
                "media_type": message_config["media_type"],
            }

        except Exception as e:
            logger.error(f"Failed to generate message: {e}")
            return {"text": "Message generation error", "error": str(e)}

    async def handle_user_response(self, telegram_id: str, user_message: str) -> str:
        """
        Handle a user's reply to an automated message using the same agent that generated it.

        Args:
            telegram_id: Telegram user ID
            user_message: User message text

        Returns:
            Agent response
        """
        # Use stored agent if available, otherwise fallback to the general agent
        if telegram_id not in self.user_context:
            agent_key = "general"
        else:
            agent_key = self.user_context[telegram_id].get("agent_type", "general")

        try:
            result = await self.orchestrator.run_agent_message(
                agent_key=agent_key,
                user_id=telegram_id,
                message=user_message,
            )
            assistant_response = (result.get("content") or "").strip()
            # Update metadata
            self.user_context[telegram_id] = {
                **self.user_context.get(telegram_id, {}),
                "agent_type": result.get("agent_key", agent_key),
                "timestamp": datetime.now().isoformat(),
            }
            return assistant_response
        except Exception as e:
            logger.error(f"Failed to process user reply: {e}")
            return "Sorry, an error occurred while processing your message. Please try again later."

    async def _handle_with_general_agent(self, user_message: str) -> str:
        """Compatibility fallback: route through the general agent via the orchestrator."""
        result = await self.orchestrator.run_agent_message(
            agent_key="general",
            user_id="broadcast:general",
            message=user_message,
        )
        return (result.get("content") or "").strip()

    def save_conversation_to_db(self, session: Session, telegram_id: str) -> None:
        """
        Persist the current in-memory conversation context to the database.

        Args:
            session: SQLAlchemy session
            telegram_id: Telegram user ID
        """
        if telegram_id not in self.user_context:
            return

        context = self.user_context[telegram_id]

        # Find user by Telegram ID
        user = session.query(TelegramUser).filter_by(telegram_id=telegram_id).first()

        if not user:
            logger.warning(
                f"User with telegram_id {telegram_id} not found in the database"
            )
            return

        # Create a record in the conversations table
        conversation = Conversation(
            user_id=user.id,
            agent_type=context["agent_type"],
            topic=context["last_topic"],
            conversation_data=json.dumps(context, ensure_ascii=False),
            created_at=datetime.now(),
        )

        session.add(conversation)
        session.commit()

    def cleanup_old_contexts(self, max_age_hours: int = 24) -> None:
        """
        Clean up old dialog contexts that have not been used for more than the specified time.

        Args:
            max_age_hours: Maximum age of a context in hours
        """
        now = datetime.now()
        keys_to_remove = []

        for telegram_id, context in self.user_context.items():
            timestamp = datetime.fromisoformat(context["timestamp"])
            age = (now - timestamp).total_seconds() / 3600

            if age > max_age_hours:
                keys_to_remove.append(telegram_id)

        for key in keys_to_remove:
            del self.user_context[key]

        if keys_to_remove:
            logger.info(f"Removed {len(keys_to_remove)} stale dialog contexts")

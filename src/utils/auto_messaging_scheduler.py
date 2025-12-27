"""Auto-messaging scheduling and delivery module."""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import settings
from src.db.models import AutoMessageSchedule, Base, TelegramUser
from src.utils.auto_messaging_generator import AutoMessagingGenerator

logger = logging.getLogger(__name__)


class AutoMessagingScheduler:
    def __init__(self):
        """Initialize the auto-messaging scheduler."""
        self.generator = AutoMessagingGenerator()

        # Configure DB connection
        self.engine = create_engine(settings.DATABASE_URL)
        # Create tables if needed
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

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

    def _get_next_run_time(self, message_config: Dict[str, Any]) -> datetime:
        """
        Compute the next scheduled time based on the message configuration.

        Args:
            message_config: Message configuration

        Returns:
            Next scheduled run datetime
        """
        now = datetime.now()
        schedule_type = message_config["schedule"]
        time_str = message_config["time"]
        hour, minute = map(int, time_str.split(":"))

        if schedule_type == "daily":
            # If today's time has passed, schedule for tomorrow
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target

        elif schedule_type == "weekly":
            # Map weekday (0 = Monday, 6 = Sunday)
            day_of_week = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }
            target_day = day_of_week.get(message_config.get("day", "monday").lower(), 0)

            # Current weekday (0 = Monday, 6 = Sunday)
            current_day = now.weekday()

            # Compute how many days ahead we need to schedule
            days_ahead = target_day - current_day
            if days_ahead < 0 or (
                days_ahead == 0 and now.replace(hour=hour, minute=minute) <= now
            ):
                # Target day has passed this week, or it's today but time has passed
                days_ahead += 7

            target = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            ) + timedelta(days=days_ahead)
            return target

        else:
            # Default: schedule for tomorrow
            return now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            ) + timedelta(days=1)

    def schedule_auto_messages(self) -> None:
        """
        Schedule auto-messages and save schedules to the database.
        """
        with self.Session() as session:
            # Fetch all active users
            users = session.query(TelegramUser).filter_by(is_active=True).all()

            if not users:
                logger.warning("No active users found for scheduling auto-messages")
                return

            for message_config in self.config["auto_messages"]:
                message_id = message_config["id"]

                # Compute next run time
                next_run_time = self._get_next_run_time(message_config)

                for user in users:
                    # Check whether we already have an unsent schedule for this user/message type
                    existing = (
                        session.query(AutoMessageSchedule)
                        .filter_by(
                            telegram_id=user.telegram_id,
                            message_type=message_id,
                            is_sent=False,
                        )
                        .first()
                    )

                    if existing:
                        # Update schedule time if it changed
                        if existing.scheduled_for != next_run_time:
                            existing.scheduled_for = next_run_time
                            logger.info(
                                f"Updated schedule time for {message_id} user {user.telegram_id}"
                            )
                    else:
                        # Create a new schedule record
                        schedule = AutoMessageSchedule(
                            telegram_id=user.telegram_id,
                            user_id=user.id,
                            message_type=message_id,
                            scheduled_for=next_run_time,
                            is_sent=False,
                        )
                        session.add(schedule)
                        logger.info(
                            f"Scheduled {message_id} for {user.telegram_id} at {next_run_time}"
                        )

            session.commit()

    async def check_and_send_auto_messages(self, bot) -> None:
        """
        Check and send scheduled auto-messages.

        Args:
            bot: Telegram bot instance used to send messages
        """
        now = datetime.now()
        logger.info(f"Checking scheduled auto-messages at {now}")

        # Use a short-lived session
        session = self.Session()
        try:
            # Fetch all unsent messages that are due
            schedules = (
                session.query(AutoMessageSchedule)
                .filter(
                    AutoMessageSchedule.is_sent == False,  # noqa: E712
                    AutoMessageSchedule.scheduled_for <= now,
                )
                .all()
            )

            if not schedules:
                logger.debug("No scheduled auto-messages to send")
                return

            for schedule in schedules:
                # Generate message using the generator
                message_data = await self.generator.generate_message(
                    message_type=schedule.message_type, telegram_id=schedule.telegram_id
                )

                if "error" in message_data:
                    logger.error(f"Message generation error: {message_data['error']}")
                    continue

                try:
                    # Send message to the user
                    await bot.send_message(
                        chat_id=int(schedule.telegram_id),
                        text=message_data["text"],
                        parse_mode="HTML",
                    )

                    # Mark as sent and store message payload
                    schedule.is_sent = True
                    schedule.sent_at = datetime.now()
                    schedule.message_data = json.dumps(message_data, ensure_ascii=False)

                    # Schedule the next message of this type
                    for msg_config in self.config["auto_messages"]:
                        if msg_config["id"] == schedule.message_type:
                            next_run_time = self._get_next_run_time(msg_config)
                            new_schedule = AutoMessageSchedule(
                                telegram_id=schedule.telegram_id,
                                user_id=schedule.user_id,
                                message_type=schedule.message_type,
                                scheduled_for=next_run_time,
                                is_sent=False,
                            )
                            session.add(new_schedule)
                            break

                    logger.info(
                        f"Sent auto-message {schedule.message_type} to user {schedule.telegram_id}"
                    )

                except Exception as e:
                    logger.error(f"Failed to send auto-message: {e}")

            session.commit()

        finally:
            session.close()

    def cleanup_old_schedules(self, days: int = 30) -> None:
        """
        Clean up old records for completed schedules.

        Args:
            days: Delete records older than this many days
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.Session() as session:
            # Delete old sent messages
            deleted = (
                session.query(AutoMessageSchedule)
                .filter(
                    AutoMessageSchedule.is_sent == True,  # noqa: E712
                    AutoMessageSchedule.sent_at <= cutoff_date,
                )
                .delete()
            )

            session.commit()

            if deleted:
                logger.info(f"Deleted {deleted} old schedule records")

    def get_scheduled_messages(self, telegram_id: str = None) -> List[Dict[str, Any]]:
        """
        Return a list of scheduled (unsent) messages.

        Args:
            telegram_id: Optional Telegram user ID

        Returns:
            List of scheduled messages
        """
        with self.Session() as session:
            query = session.query(AutoMessageSchedule).filter_by(is_sent=False)

            if telegram_id:
                query = query.filter_by(telegram_id=telegram_id)

            schedules = query.all()

            result = []
            for schedule in schedules:
                # Find corresponding message configuration
                message_config = None
                for msg in self.config["auto_messages"]:
                    if msg["id"] == schedule.message_type:
                        message_config = msg
                        break

                result.append(
                    {
                        "id": schedule.id,
                        "telegram_id": schedule.telegram_id,
                        "message_type": schedule.message_type,
                        "message_name": (
                            message_config["name"]
                            if message_config
                            else schedule.message_type
                        ),
                        "scheduled_for": schedule.scheduled_for.isoformat(),
                        "agent_type": (
                            message_config["agent_type"] if message_config else None
                        ),
                    }
                )

            return result

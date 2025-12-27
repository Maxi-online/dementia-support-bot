import logging
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from src.db.models import Reminder

# Import for content generation
from src.utils.reminder_content_generator import generate_reminder_text

logger = logging.getLogger(__name__)

# ===============================
# Six-month program themes
# ===============================

# List of tuples: week number (1-24) and the corresponding theme
WEEKLY_THEMES = [
    # Month 1
    (1, "Morning exercises"),
    (2, "Hydration routine"),
    (3, "Healthy nutrition"),
    (4, "Social activity"),
    # Month 2
    (5, "Meditation"),
    (6, "Affirmations"),
    (7, "Stress reduction"),
    (8, "Sleep routine"),
    # Month 3
    (9, "Optimism and positive mindset"),
    (10, "New hobbies"),
    (11, "Journaling"),
    (12, "Self-esteem and gratitude"),
    # Month 4
    (13, "Morning exercises (yoga/stretching)"),
    (14, "Vitamins and micronutrients"),
    (15, "Communication and creativity"),
    (16, "Evening rituals"),
    # Month 5
    (17, "Light workouts"),
    (18, "Mindful eating"),
    (19, "Developing new interests"),
    (20, "Breathing control"),
    # Month 6
    (21, "Morning exercises 2.0"),
    (22, "Social connections"),
    (23, "Optimism and gratitude"),
    (24, "Restoring energy"),
]

# Map {week_number: theme} for quick access
WEEK_THEME_MAP = {num: theme for num, theme in WEEKLY_THEMES}

# ===============================
# Daily templates
# ===============================

# Full template — main flow (9 messages per day)
DAY_TEMPLATE = [
    # (in-day order, time, generator key, default title)
    (1, "07:15", "good_morning", "Good morning"),
    (2, "07:20", "health_ritual", "Morning health ritual"),
    (3, "10:00", "education", "Clear. Simple. The Essentials"),
    (4, "10:10", "daily_task", "Task of the day"),
    (5, "12:00", "physical_activity", "Physical activity reminder"),
    (6, "15:00", "humor", "Smile"),
    (7, "16:00", "cognitive_task", "Cognitive task"),
    (8, "20:00", "anti_stress", "Sleep / anti-stress"),
    (9, "21:00", "good_night", "Good night"),
]

# Short template for the introductory month (up to 7 messages/day)
INTRO_DAY_TEMPLATE = DAY_TEMPLATE[:7]  # first 7 items are enough


def _local_time_to_datetime(
    start_date: datetime, time_str: str, tz: ZoneInfo
) -> datetime:
    """Build a datetime for a given local time."""
    hours, minutes = map(int, time_str.split(":"))
    dt = start_date.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    return dt.astimezone(tz)


def generate_initial_reminders(
    session: Session,
    telegram_id: str,
    timezone_str: str = "UTC",
    days: int = 210,
) -> List[Reminder]:
    """Create scheduled reminders for the next `days` days.

    If reminders already exist (by telegram_id) — skip generation to avoid duplicates.
    """
    existing = (
        session.query(Reminder).filter(Reminder.telegram_id == telegram_id).first()
    )
    if existing:
        logger.info(
            "Reminders already exist for user %s, skipping generation", telegram_id
        )
        return []

    user_tz = ZoneInfo(timezone_str)
    today_local = datetime.now(user_tz).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    reminders_to_add: List[Reminder] = []

    # (Optional) Initialize additional components for content generation if needed.
    # Kept for future expansion.

    for day_offset in range(days):
        day_base = today_local + timedelta(days=day_offset)

        # Week number (starting at 1). Day 1 belongs to week 1.
        current_week = (day_offset // 7) + 1

        theme = WEEK_THEME_MAP.get(current_week, "General wellbeing")

        # Choose which template to use: introductory month (first 30 days) or main
        day_template = INTRO_DAY_TEMPLATE if day_offset < 30 else DAY_TEMPLATE

        for order, time_str, key, default_title in day_template:
            scheduled_local = _local_time_to_datetime(day_base, time_str, user_tz)

            # Generate reminder text via content generator
            text = generate_reminder_text(
                theme=theme, category_key=key, default_title=default_title
            )

            reminders_to_add.append(
                Reminder(
                    telegram_id=telegram_id,
                    timezone=timezone_str,
                    scheduled_for=scheduled_local.replace(tzinfo=None),
                    title=default_title,
                    text=text,
                    user_id=None,  # can be filled later when the User is created
                )
            )

    session.add_all(reminders_to_add)
    session.commit()
    logger.info("Created %d reminders for user %s", len(reminders_to_add), telegram_id)
    return reminders_to_add

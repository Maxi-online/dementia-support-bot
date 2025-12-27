"""User data access module."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src.core.config import settings

Base = declarative_base()


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)
    preferences = Column(JSON, default={})
    conversation_history = Column(JSON, default=[])
    emergency_contacts = Column(JSON, default=[])
    medical_info = Column(JSON, default={})


class UserDataManager:
    """User data manager."""

    def __init__(self) -> None:
        """Initialize the user data manager."""
        self.engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    async def create_user(
        self, telegram_id: int, username: Optional[str] = None
    ) -> User:
        """Create a new user.

        Args:
            telegram_id: Telegram user ID
            username: Telegram username

        Returns:
            The created user object
        """
        session = self.Session()
        try:
            user = User(telegram_id=telegram_id, username=username)
            session.add(user)
            session.commit()
            return user
        finally:
            session.close()

    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Get a user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User object or None if not found
        """
        session = self.Session()
        try:
            return session.query(User).filter(User.telegram_id == telegram_id).first()
        finally:
            session.close()

    async def update_preferences(
        self, telegram_id: int, preferences: Dict[str, Any]
    ) -> Optional[User]:
        """Update user preferences.

        Args:
            telegram_id: Telegram user ID
            preferences: New user preferences

        Returns:
            Updated user object or None if not found
        """
        session = self.Session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.preferences.update(preferences)
                session.commit()
            return user
        finally:
            session.close()

    async def add_conversation_entry(
        self, telegram_id: int, message: str, response: str
    ) -> Optional[User]:
        """Append an entry to the user's conversation history.

        Args:
            telegram_id: Telegram user ID
            message: User message
            response: Bot response

        Returns:
            Updated user object or None if not found
        """
        session = self.Session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": message,
                    "response": response,
                }
                user.conversation_history.append(entry)
                if len(user.conversation_history) > settings.MAX_HISTORY_ENTRIES:
                    user.conversation_history = user.conversation_history[
                        -settings.MAX_HISTORY_ENTRIES :
                    ]
                session.commit()
            return user
        finally:
            session.close()

    async def update_emergency_contacts(
        self, telegram_id: int, contacts: List[Dict[str, str]]
    ) -> Optional[User]:
        """Update emergency contacts.

        Args:
            telegram_id: Telegram user ID
            contacts: Contact list

        Returns:
            Updated user object or None if not found
        """
        session = self.Session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.emergency_contacts = contacts[: settings.MAX_EMERGENCY_CONTACTS]
                session.commit()
            return user
        finally:
            session.close()

    async def update_medical_info(
        self, telegram_id: int, medical_info: Dict[str, Any]
    ) -> Optional[User]:
        """Update user medical information.

        Args:
            telegram_id: Telegram user ID
            medical_info: Medical information

        Returns:
            Updated user object or None if not found
        """
        session = self.Session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.medical_info.update(medical_info)
                session.commit()
            return user
        finally:
            session.close()

    async def get_conversation_history(
        self, telegram_id: int, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a user.

        Args:
            telegram_id: Telegram user ID
            limit: Maximum number of entries

        Returns:
            List of history entries
        """
        session = self.Session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                history = user.conversation_history
                if limit:
                    history = history[-limit:]
                return history
            return []
        finally:
            session.close()

    async def deactivate_user(self, telegram_id: int) -> Optional[User]:
        """Deactivate a user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Updated user object or None if not found
        """
        session = self.Session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.is_active = 0
                session.commit()
            return user
        finally:
            session.close()

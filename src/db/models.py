from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    username = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient_profile = relationship(
        "PatientProfile", back_populates="user", uselist=False
    )
    caregiver_profile = relationship(
        "CaregiverProfile", back_populates="user", uselist=False
    )
    conversations = relationship("Conversation", back_populates="user")
    crisis_events = relationship("CrisisEvent", back_populates="user")
    reminders = relationship("Reminder", back_populates="user")


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    diagnosis = Column(String)
    stage = Column(String)
    medications = Column(Text)
    emergency_contact = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="patient_profile")
    assessments = relationship("Assessment", back_populates="patient")


class CaregiverProfile(Base):
    __tablename__ = "caregiver_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    relationship_type = Column(String)  # Renamed from `relationship`
    experience_years = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="caregiver_profile")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    agent_type = Column(String)
    message = Column(Text)
    response = Column(Text)
    sentiment_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="conversations")


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_profiles.id"))
    assessment_type = Column(String)
    score = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("PatientProfile", back_populates="assessments")


class CrisisEvent(Base):
    __tablename__ = "crisis_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String)
    severity = Column(Float)
    description = Column(Text)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="crisis_events")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))  # Internal FK to users.id
    telegram_id = Column(String, index=True)  # Duplicated for quick access

    # Reminder data
    timezone = Column(
        String, default="UTC"
    )  # zoneinfo-compatible TZ, e.g. "America/New_York"
    scheduled_for = Column(DateTime, nullable=False)  # User-local scheduled datetime
    title = Column(String, nullable=False)
    text = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    video_url = Column(String, nullable=True)

    # Internal fields
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="reminders")


class TelegramUser(Base):
    """Telegram users for simplified access."""

    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_interaction = Column(DateTime, default=datetime.utcnow)


class AutoMessageSchedule(Base):
    """Scheduled auto-messages for users."""

    __tablename__ = "auto_message_schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    telegram_id = Column(String, index=True)
    message_type = Column(String, nullable=False)
    scheduled_for = Column(DateTime, nullable=False)

    # Internal fields
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    message_data = Column(Text, nullable=True)  # JSON payload of the sent message

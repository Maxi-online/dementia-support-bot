import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import aiohttp
from openai import AsyncOpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    JobQueue,
    MessageHandler,
    filters,
)

from src.core.http_client import async_client
from src.db.models import AutoMessageSchedule, Base, Reminder, TelegramUser
from src.utils.auto_messaging_generator import AutoMessagingGenerator
from src.utils.auto_messaging_scheduler import AutoMessagingScheduler
from src.utils.reminder_generator import generate_initial_reminders

from ..core.config import settings
from ..core.orchestrator import MessageOrchestrator

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class DementiaSupportBot:
    def __init__(self):
        """Initialize the Dementia Support Telegram bot."""
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.openai_base_url,
            http_client=async_client,
        )
        self.orchestrator = MessageOrchestrator()
        self.functions = [
            {
                "name": "process_message",
                "description": "Processes a user message",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message_type": {
                            "type": "string",
                            "enum": ["text", "command", "callback"],
                            "description": "Message type",
                        },
                        "content": {"type": "string", "description": "Message content"},
                        "user_id": {"type": "string", "description": "User ID"},
                        "additional_data": {
                            "type": "object",
                            "description": "Additional data",
                        },
                    },
                    "required": ["message_type", "content", "user_id"],
                },
            }
        ]
        # Directory for local dialog history (ignored by git)
        os.makedirs("dialogs", exist_ok=True)
        # Yandex SpeechKit URL
        self.YANDEX_SPEECHKIT_URL = settings.YANDEX_SPEECHKIT_URL
        # Database connection
        self.engine = create_engine(settings.DATABASE_URL)
        # Create tables if needed
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Auto-messaging components
        self.auto_messaging_generator = AutoMessagingGenerator()
        self.auto_messaging_scheduler = AutoMessagingScheduler()

    def get_system_prompt(self) -> str:
        return """You are an AI Telegram bot that supports people living with dementia and their caregivers.
Your job is to process user messages and route them to the correct specialized agent(s).

Supported message types:
1) Text messages
2) Commands
3) Callback queries

Safety:
- Always check for signs of crisis or self-harm risk and route to the crisis agent immediately.

Language:
- Respond in English."""

    def format_text_for_telegram(self, text: str) -> str:
        """
        Format text for Telegram using HTML tags.

        Supports basic Markdown-like patterns:
        **bold** -> <b>bold</b>
        __underline__ -> <u>underline</u>
        *italic* -> <i>italic</i>
        ~strikethrough~ -> <s>strikethrough</s>
        `code` -> <code>code</code>
        ```code block``` -> <pre>code block</pre>
        [link text](URL) -> <a href="URL">link text</a>
        """
        # Escape HTML to avoid injection
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Replace code blocks
        text = re.sub(r"```([\s\S]*?)```", r"<pre>\1</pre>", text)

        # Replace inline code
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

        # Replace links
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

        # Replace bold text
        text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)

        # Replace underlined text
        text = re.sub(r"__([^_]+)__", r"<u>\1</u>", text)

        # Replace italic text
        text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)

        # Replace strikethrough text
        text = re.sub(r"~([^~]+)~", r"<s>\1</s>", text)

        return text

    async def start(self, update: Update, context: CallbackContext) -> None:
        """Handle the /start command."""
        user_id = str(update.effective_user.id)
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name

        # Create or update a user in the DB
        with self.Session() as session:
            # First, check whether the user already exists
            telegram_user = (
                session.query(TelegramUser).filter_by(telegram_id=user_id).first()
            )

            if not telegram_user:
                # Create a new user
                telegram_user = TelegramUser(
                    telegram_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                    created_at=datetime.now(),
                    last_interaction=datetime.now(),
                )
                session.add(telegram_user)
                session.commit()
            else:
                # Update an existing user
                telegram_user.username = username
                telegram_user.first_name = first_name
                telegram_user.last_name = last_name
                telegram_user.is_active = True
                telegram_user.last_interaction = datetime.now()
                session.commit()

        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": "A new user started the bot. Create a welcome message in English.",
                },
            ],
            functions=[
                {
                    "name": "create_welcome_message",
                    "description": "Creates a welcome message",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "welcome_text": {
                                "type": "string",
                                "description": "Welcome text",
                            },
                            "available_commands": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Available commands",
                            },
                            "initial_instructions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Initial instructions",
                            },
                        },
                        "required": [
                            "welcome_text",
                            "available_commands",
                            "initial_instructions",
                        ],
                    },
                }
            ],
            function_call={"name": "create_welcome_message"},
        )

        raw_args = response.choices[0].message.function_call.arguments
        welcome_data = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        welcome_text = (
            f"{welcome_data['welcome_text']}\n\n"
            f"**Available commands:**\n"
            + "\n".join(f"- {cmd}" for cmd in welcome_data["available_commands"])
            + "\n\n"
            f"**Getting started:**\n"
            + "\n".join(f"- {instr}" for instr in welcome_data["initial_instructions"])
        )
        formatted_text = self.format_text_for_telegram(welcome_text)
        await update.message.reply_text(formatted_text, parse_mode=ParseMode.HTML)

        # Create a baseline 30-day set of reminders on first launch
        with self.Session() as session:
            generate_initial_reminders(session, telegram_id=user_id)

        # Schedule auto-messages for a new user
        self.auto_messaging_scheduler.schedule_auto_messages()

    async def help(self, update: Update, context: CallbackContext) -> None:
        """Handle the /help command."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {
                    "role": "user",
                    "content": "The user asked for help. Create a help message in English.",
                },
            ],
            functions=[
                {
                    "name": "create_help_message",
                    "description": "Creates a help message",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "help_text": {
                                "type": "string",
                                "description": "Main help text",
                            },
                            "features": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Features",
                            },
                            "examples": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Usage examples",
                            },
                        },
                        "required": ["help_text", "features", "examples"],
                    },
                }
            ],
            function_call={"name": "create_help_message"},
        )

        raw_args = response.choices[0].message.function_call.arguments
        help_data = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        help_text = (
            f"{help_data['help_text']}\n\n"
            f"**Available features:**\n"
            + "\n".join(f"- {feature}" for feature in help_data["features"])
            + "\n\n"
            f"**Usage examples:**\n"
            + "\n".join(f"- {example}" for example in help_data["examples"])
        )
        formatted_text = self.format_text_for_telegram(help_text)
        await update.message.reply_text(formatted_text, parse_mode=ParseMode.HTML)

    async def send_typing_action(self, chat_id, duration):
        """Send typing indicator for the given duration (seconds)."""
        end_time = datetime.now().timestamp() + duration
        while datetime.now().timestamp() < end_time:
            await self.application.bot.send_chat_action(
                chat_id=chat_id, action=ChatAction.TYPING
            )
            await asyncio.sleep(3)

    async def send_voice_action(self, chat_id, duration):
        """Send voice recording indicator for the given duration (seconds)."""
        end_time = datetime.now().timestamp() + duration
        while datetime.now().timestamp() < end_time:
            await self.application.bot.send_chat_action(
                chat_id=chat_id, action=ChatAction.RECORD_VOICE
            )
            await asyncio.sleep(3)

    async def recognize_speech(self, voice_data):
        """
        Recognize speech using Yandex SpeechKit API v3.

        Args:
            voice_data: Voice message bytes

        Returns:
            str: Recognized text
        """
        headers = {
            "Authorization": f"Api-Key {settings.YANDEX_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Create a recognition task
                create_recognition_request = {
                    "config": {
                        "specification": {
                            "languageCode": "ru-RU",
                            "audioEncoding": "OGG_OPUS",
                            "sampleRateHertz": 48000,
                            "audioChannelCount": 1,
                        }
                    }
                }

                # Add folder ID only if configured
                if hasattr(settings, "FOLDER_ID") and settings.FOLDER_ID:
                    create_recognition_request["folderId"] = settings.FOLDER_ID

                async with session.post(
                    "https://stt.api.cloud.yandex.net/speech/v3/longRunningRecognize",
                    headers=headers,
                    json=create_recognition_request,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to create recognition task: {response.status}, {error_text}"
                        )
                        return ""

                    operation_data = await response.json()
                    operation_id = operation_data.get("id")

                    if not operation_id:
                        logger.error("Recognition operation ID was not returned")
                        return ""

                # Step 2: Upload audio
                upload_url = operation_data.get("uploadUrl")
                if not upload_url:
                    logger.error("Upload URL for audio was not returned")
                    return ""

                async with session.put(
                    upload_url,
                    data=voice_data,
                    headers={"Content-Type": "application/octet-stream"},
                ) as upload_response:
                    if upload_response.status != 200:
                        error_text = await upload_response.text()
                        logger.error(
                            f"Failed to upload audio: {upload_response.status}, {error_text}"
                        )
                        return ""

                # Step 3: Wait for recognition result
                max_attempts = 30  # Number of polling attempts
                for attempt in range(max_attempts):
                    async with session.get(
                        f"https://operation.api.cloud.yandex.net/operations/{operation_id}",
                        headers=headers,
                    ) as status_response:
                        if status_response.status != 200:
                            error_text = await status_response.text()
                            logger.error(
                                f"Failed to fetch status: {status_response.status}, {error_text}"
                            )
                            return ""

                        status_data = await status_response.json()
                        if status_data.get("done"):
                            if "response" in status_data:
                                chunks = status_data["response"].get("chunks", [])
                                if chunks:
                                    return " ".join(
                                        chunk.get("alternatives", [{}])[0].get(
                                            "text", ""
                                        )
                                        for chunk in chunks
                                    )

                            logger.error("Recognition response contained an error")
                            return ""

                        # Wait before the next poll
                        await asyncio.sleep(1)

                logger.error(
                    f"Exceeded maximum polling attempts ({max_attempts}) for recognition status"
                )
                return ""

        except Exception as e:
            logger.error(f"Speech recognition failed: {e}")
            return ""

    async def synthesize_speech(self, text):
        """
        Synthesize speech using Yandex SpeechKit API v3.

        Args:
            text: Text to synthesize

        Returns:
            bytes: Audio data
        """
        headers = {
            "Authorization": f"Api-Key {settings.YANDEX_API_KEY}",
            "Content-Type": "application/json",
        }

        synthesis_request = {
            "text": text,
            "outputAudioSpec": {"containerAudio": {"containerAudioType": "OGG_OPUS"}},
            "voice": {"name": "alena"},
        }

        # Add folder ID only if configured
        if hasattr(settings, "FOLDER_ID") and settings.FOLDER_ID:
            synthesis_request["folderId"] = settings.FOLDER_ID

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Create a synthesis task
                async with session.post(
                    "https://tts.api.cloud.yandex.net/speech/v3/synthesize",
                    headers=headers,
                    json=synthesis_request,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"Synthesis failed: {response.status}, {error_text}"
                        )
                        return None

                    operation_data = await response.json()
                    operation_id = operation_data.get("id")

                    if not operation_id:
                        logger.error("Synthesis operation ID was not returned")
                        return None

                # Step 2: Wait for synthesis result and download audio
                max_attempts = 30  # Number of polling attempts
                for attempt in range(max_attempts):
                    async with session.get(
                        f"https://operation.api.cloud.yandex.net/operations/{operation_id}",
                        headers=headers,
                    ) as status_response:
                        if status_response.status != 200:
                            error_text = await status_response.text()
                            logger.error(
                                f"Failed to fetch synthesis status: {status_response.status}, {error_text}"
                            )
                            return None

                        status_data = await status_response.json()
                        if status_data.get("done"):
                            if "response" in status_data:
                                audio_url = status_data["response"].get("audioUrl")
                                if audio_url:
                                    async with session.get(audio_url) as audio_response:
                                        if audio_response.status == 200:
                                            return await audio_response.read()

                            logger.error("Synthesis response contained an error")
                            return None

                        # Wait before the next poll
                        await asyncio.sleep(1)

                logger.error(
                    f"Exceeded maximum polling attempts ({max_attempts}) for synthesis status"
                )
                return None

        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            return None

    async def save_history_to_file(self, user_id, username, message, response):
        """Save dialog history to a local file (ignored by git)."""
        file_path = os.path.join("dialogs", f"{user_id}_history.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(f"Username: {username}\n\n")

        with open(file_path, "a", encoding="utf-8") as file:
            file.write(f"{timestamp} User ({username}): {message}\n")
            file.write(f"{timestamp} Bot: {response}\n\n")

    async def handle_message(self, update: Update, context: CallbackContext) -> None:
        """Handle incoming text messages."""
        message = update.message.text
        user_id = str(update.effective_user.id)
        username = update.effective_user.first_name

        # Update user's last activity timestamp
        with self.Session() as session:
            user = session.query(TelegramUser).filter_by(telegram_id=user_id).first()
            if user:
                user.last_interaction = datetime.now()
                session.commit()

        # Check whether this is a reply to an auto-message
        is_auto_message_response = False
        response_text = ""

        # Check whether we have auto-message context for this user
        if (
            hasattr(self.auto_messaging_generator, "user_context")
            and user_id in self.auto_messaging_generator.user_context
        ):
            # Process the message using the relevant specialized agent
            is_auto_message_response = True
            typing_task = asyncio.create_task(
                self.send_typing_action(update.effective_chat.id, 15)
            )

            try:
                response_text = (
                    await self.auto_messaging_generator.handle_user_response(
                        user_id, message
                    )
                )
                typing_task.cancel()

                # Format the response for Telegram
                formatted_text = self.format_text_for_telegram(response_text)

                # Save exchange to history
                await self.save_history_to_file(
                    user_id, username, message, response_text
                )

                # Send the response
                await update.message.reply_text(
                    formatted_text, parse_mode=ParseMode.HTML
                )
                return

            except Exception as e:
                logger.error(f"Failed to process auto-message reply: {e}")
                # If an error occurs, fall back to normal processing
                is_auto_message_response = False

        # If this is not an auto-message reply (or an error occurred), process as a normal message
        # Start "typing" indicator
        typing_task = asyncio.create_task(
            self.send_typing_action(update.effective_chat.id, 30)
        )

        # Get response from the orchestrator
        raw_response = await self.orchestrator.process_message(message, user_id)

        # Stop "typing" indicator
        typing_task.cancel()

        # If a JSON string was returned, parse it into a dict
        data = (
            json.loads(raw_response) if isinstance(raw_response, str) else raw_response
        )

        # Extract response text (keys 'response' or 'content') or format a JSON dict
        if (
            isinstance(data, dict)
            and not data.get("response")
            and not data.get("content")
        ):
            # Format list key/value pairs
            lines = []
            for key, val in data.items():
                title = key.replace("_", " ").capitalize()
                lines.append(f"**{title}:**")
                if isinstance(val, list):
                    for item in val:
                        lines.append(f"- {item}")
                else:
                    lines.append(str(val))
                lines.append("")
            reply_text = "\n".join(lines).strip()
        else:
            reply_text = data.get("response") or data.get("content") or str(data)

        # Format text for Telegram
        formatted_text = self.format_text_for_telegram(reply_text)

        # Save exchange to history for summarization
        self.orchestrator.conversation_history.append(
            {"user_id": user_id, "message": message, "response": reply_text}
        )

        # Persist to a local file
        await self.save_history_to_file(user_id, username, message, reply_text)

        # For text messages, reply with text only
        await update.message.reply_text(formatted_text, parse_mode=ParseMode.HTML)

    async def handle_voice(self, update: Update, context: CallbackContext) -> None:
        """Handle incoming voice messages."""
        user_id = str(update.effective_user.id)
        username = update.effective_user.first_name

        # Handle a voice message
        voice_file = await update.message.voice.get_file()

        # Create a temp file for the voice message
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".ogg"
        ) as temp_voice_file:
            voice_path = temp_voice_file.name
            await voice_file.download_to_memory(temp_voice_file)

        # Send "recording voice" indicator
        processing_task = asyncio.create_task(
            self.send_voice_action(update.effective_chat.id, 30)
        )

        # Read file contents and send to speech recognition
        with open(voice_path, "rb") as voice_file:
            voice_data = voice_file.read()
            # Recognize speech
            recognized_text = await self.recognize_speech(voice_data)

        # Delete temp file
        os.remove(voice_path)

        if not recognized_text:
            processing_task.cancel()
            await update.message.reply_text(
                "Sorry, I couldn't recognize the voice message. Please try again."
            )
            return

        # Get response from the orchestrator
        raw_response = await self.orchestrator.process_message(recognized_text, user_id)

        # If a JSON string was returned, parse it into a dict
        data = (
            json.loads(raw_response) if isinstance(raw_response, str) else raw_response
        )

        # Extract response text
        if (
            isinstance(data, dict)
            and not data.get("response")
            and not data.get("content")
        ):
            # Format list key/value pairs
            lines = []
            for key, val in data.items():
                title = key.replace("_", " ").capitalize()
                lines.append(f"{title}:")
                if isinstance(val, list):
                    for item in val:
                        lines.append(f"- {item}")
                else:
                    lines.append(str(val))
                lines.append("")
            reply_text = "\n".join(lines).strip()
        else:
            reply_text = data.get("response") or data.get("content") or str(data)

        # Synthesize speech
        speech_data = await self.synthesize_speech(reply_text)

        # Stop processing indicator
        processing_task.cancel()

        # Save exchange to history for summarization
        self.orchestrator.conversation_history.append(
            {"user_id": user_id, "message": recognized_text, "response": reply_text}
        )

        # Persist to a local file
        await self.save_history_to_file(user_id, username, recognized_text, reply_text)

        # For voice messages, reply with voice only
        # If synthesis succeeds, send a voice reply
        if speech_data:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
                temp_file.write(speech_data)
                temp_file_path = temp_file.name

            try:
                await update.message.reply_voice(voice=open(temp_file_path, "rb"))
            finally:
                os.remove(temp_file_path)
        else:
            # If synthesis fails, send a text reply explaining the issue
            await update.message.reply_text(
                self.format_text_for_telegram(reply_text), parse_mode=ParseMode.HTML
            )

    async def check_and_send_reminders(self, context: CallbackContext) -> None:
        """Send due reminders to users.

        This runs periodically via Telegram JobQueue. Times in DB are stored as local user time
        (`scheduled_for`) with an associated timezone (`timezone`). If current UTC time is within
        60 seconds of the computed event time, the reminder will be sent and marked as delivered.
        """
        now_utc = datetime.utcnow().replace(tzinfo=dt_timezone.utc)

        # Use a short DB session to avoid holding the connection longer than necessary
        session = self.Session()
        try:
            # Fetch all unsent reminders
            reminders = (
                session.query(Reminder)
                .filter(Reminder.is_sent == False)  # noqa: E712
                .all()
            )

            for reminder in reminders:
                # Compute exact reminder time in UTC, using the configured time zone
                try:
                    user_tz = (
                        ZoneInfo(reminder.timezone)
                        if reminder.timezone
                        else dt_timezone.utc
                    )
                except Exception:
                    user_tz = dt_timezone.utc

                reminder_time_local = reminder.scheduled_for.replace(tzinfo=user_tz)
                reminder_time_utc = reminder_time_local.astimezone(dt_timezone.utc)

                # If the reminder should be sent within the next 60 seconds
                delta = abs((reminder_time_utc - now_utc).total_seconds())
                if delta <= 60:
                    await self._send_reminder(context, reminder)
                    # Mark as sent
                    reminder.is_sent = True
                    reminder.sent_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

    async def _send_reminder(
        self, context: CallbackContext, reminder: Reminder
    ) -> None:
        """Send one reminder to a specific Telegram user."""
        chat_id = int(reminder.telegram_id) if reminder.telegram_id else None
        if not chat_id:
            return

        caption_parts = []
        if reminder.title:
            caption_parts.append(f"<b>{reminder.title}</b>")
        if reminder.text:
            caption_parts.append(reminder.text)
        caption_html = self.format_text_for_telegram("\n\n".join(caption_parts))

        bot = context.bot
        # If a video is specified, prioritize video
        if reminder.video_url:
            try:
                await bot.send_video(
                    chat_id=chat_id,
                    video=reminder.video_url,
                    caption=caption_html,
                    parse_mode=ParseMode.HTML,
                )
                return
            except Exception as exc:
                logger.error(f"Failed to send video reminder: {exc}")
        # If an image is specified
        if reminder.image_url:
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=reminder.image_url,
                    caption=caption_html,
                    parse_mode=ParseMode.HTML,
                )
                return
            except Exception as exc:
                logger.error(f"Failed to send photo reminder: {exc}")

        # Otherwise, send text
        try:
            await bot.send_message(
                chat_id=chat_id, text=caption_html, parse_mode=ParseMode.HTML
            )
        except Exception as exc:
            logger.error(f"Failed to send text reminder: {exc}")

    async def auto_messages(self, update: Update, context: CallbackContext) -> None:
        """Show scheduled automated messages for the user."""
        user_id = str(update.effective_user.id)

        # Get a list of scheduled auto-messages for the user
        scheduled_messages = self.auto_messaging_scheduler.get_scheduled_messages(
            user_id
        )

        if not scheduled_messages:
            await update.message.reply_text(
                "You don't have any scheduled auto-messages yet.",
                parse_mode=ParseMode.HTML,
            )
            return

        # Build a message with scheduled auto-messages
        message_parts = ["**Scheduled auto-messages:**\n"]

        for msg in scheduled_messages:
            scheduled_time = datetime.fromisoformat(msg["scheduled_for"]).strftime(
                "%d.%m.%Y %H:%M"
            )
            message_parts.append(
                f"- {msg['message_name']} (agent: {msg['agent_type']})\n"
                f"  Scheduled for: {scheduled_time}"
            )

        # Add a short explanation of how auto-messaging works
        message_parts.append("\n**About auto-messaging:**")
        message_parts.append(
            "Each message is generated by a specialized GPT agent focused on a specific topic. "
            "If you reply to a message, the same agent will continue the conversation with you."
        )

        formatted_text = self.format_text_for_telegram("\n".join(message_parts))
        await update.message.reply_text(formatted_text, parse_mode=ParseMode.HTML)

    async def check_auto_messages(self, context: CallbackContext) -> None:
        """Check and send scheduled automated messages."""
        logger.info("Checking and sending scheduled auto-messages...")
        await self.auto_messaging_scheduler.check_and_send_auto_messages(context.bot)

        # Periodically clean up old message contexts
        self.auto_messaging_generator.cleanup_old_contexts()

    def run(self) -> None:
        """Run the bot (polling mode)."""
        from telegram.ext import JobQueue

        job_queue = JobQueue()
        self.application = (
            Application.builder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .job_queue(job_queue)
            .build()
        )

        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(
            CommandHandler("auto_messages", self.auto_messages)
        )
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))

        # Start periodic reminder checks every 60 seconds
        self.application.job_queue.run_repeating(
            self.check_and_send_reminders, interval=60, first=0
        )

        # Start periodic auto-messaging checks every 60 seconds
        self.application.job_queue.run_repeating(
            self.check_auto_messages, interval=60, first=10
        )

        # Start the bot
        self.application.run_polling()

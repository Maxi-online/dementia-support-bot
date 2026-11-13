"""Application configuration module with `settings.json` support."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _resolve_settings_env(value):
    """Resolve required environment references in already parsed configuration."""
    import os
    import re
    if isinstance(value, dict):
        return {key: _resolve_settings_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_settings_env(item) for item in value]
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"\$\{([A-Z_][A-Z0-9_]*)(?::(int|float|bool))?\}", value)
    if match is None:
        return value
    name, kind = match.groups()
    content = os.environ.get(name)
    if content is None or not content.strip():
        raise RuntimeError(f"Required configuration variable is missing: {name}")
    if kind == "int":
        return int(content)
    if kind == "float":
        return float(content)
    if kind == "bool":
        if content.lower() not in {"true", "false", "1", "0"}:
            raise ValueError(f"Expected a boolean configuration variable: {name}")
        return content.lower() in {"true", "1"}
    return content



logger = logging.getLogger(__name__)


class Settings:
    """Settings manager that loads configuration from `settings.json`."""

    def __init__(self, settings_file: str = None):
        """
        Initialize settings.

        Args:
            settings_file: Path to a settings file. If not provided, tries to find `settings.json`.
        """
        self._settings = {}
        self._load_settings(settings_file)

    def _load_settings(self, settings_file: str = None):
        """Load settings from file."""
        # Resolve settings file path
        if settings_file:
            settings_path = Path(settings_file)
        else:
            # Search for `settings.json` in common locations
            possible_paths = [
                Path("settings.json"),
                Path("src/core/settings.json"),
                Path("/app/settings.json"),
                Path("/app/src/core/settings.json"),
            ]

            settings_path = None
            for path in possible_paths:
                if path.exists():
                    settings_path = path
                    break

            if not settings_path:
                # If `settings.json` is missing, copy it from the example.
                example_path = Path("src/core/settings.json.example")
                if example_path.exists():
                    settings_path = Path("settings.json")
                    logger.warning(
                        f"`settings.json` not found. Copying from {example_path}"
                    )
                    import shutil

                    shutil.copy(example_path, settings_path)
                else:
                    logger.error(
                        "Neither `settings.json` nor `settings.json.example` was found."
                    )
                    raise FileNotFoundError("Configuration file not found")

        # Load JSON
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                self._settings = _resolve_settings_env(json.load(f))
            logger.info(f"Settings loaded from {settings_path}")
        except Exception as e:
            logger.error(f"Failed to load settings from {settings_path}: {e}")
            raise

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a value by a dotted path key (e.g. `database.host`).

        Args:
            key_path: Dotted key path
            default: Default value if key is missing

        Returns:
            Setting value
        """
        keys = key_path.split(".")
        value = self._settings

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any):
        """
        Set a value by a dotted path key.

        Args:
            key_path: Dotted key path
            value: New value
        """
        keys = key_path.split(".")
        current = self._settings

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    # Core application settings
    @property
    def PROJECT_NAME(self) -> str:
        return self.get("application.project_name", "Dementia Support Bot")

    @property
    def VERSION(self) -> str:
        return self.get("application.version", "1.0.0")

    @property
    def DEBUG(self) -> bool:
        return self.get("application.debug", False)

    @property
    def LOG_LEVEL(self) -> str:
        return self.get("logging.level", "INFO")

    # Telegram
    @property
    def telegram_bot_token(self) -> str:
        return self.get("telegram.bot_token", "")

    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        return self.telegram_bot_token

    # OpenAI
    @property
    def openai_api_key(self) -> str:
        return self.get("openai.api_key", "")

    @property
    def OPENAI_API_KEY(self) -> str:
        return self.openai_api_key

    @property
    def openai_model(self) -> str:
        return self.get("openai.model", "gpt-5-nano")

    @property
    def OPENAI_MODEL(self) -> str:
        return self.openai_model

    @property
    def openai_base_url(self) -> str:
        return self.get("openai.base_url", "https://api.openai.com/v1")

    # Yandex SpeechKit (optional)
    @property
    def YANDEX_API_KEY(self) -> str:
        return self.get("yandex.api_key", "")

    @property
    def YANDEX_SPEECHKIT_URL(self) -> str:
        return self.get("yandex.speechkit_url", "https://stt.api.cloud.yandex.net")

    @property
    def FOLDER_ID(self) -> str:
        return self.get("yandex.folder_id", "")

    # Database
    @property
    def database_url(self) -> str:
        return self.get(
            "database.url",
            "",
        )

    @property
    def DATABASE_URL(self) -> str:
        return self.database_url


# Create a global settings instance
try:
    settings = Settings()
except Exception as e:
    logger.error(f"Failed to initialize settings: {e}")
    # Fallback defaults to avoid a hard crash during import
    settings = Settings.__new__(Settings)
    settings._settings = {
        "database": {"url": os.environ["URL"]},
        "telegram": {"bot_token": ""},
        "openai": {"api_key": "", "model": "gpt-5-nano"},
        "application": {"debug": True},
    }

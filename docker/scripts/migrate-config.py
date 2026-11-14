#!/usr/bin/env python3
"""
Utility to migrate settings from a .env file to settings.json.
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote


def load_env_file(env_file_path):
    """Load variables from a .env file."""
    env_vars = {}

    if not os.path.exists(env_file_path):
        print(f"⚠️  File {env_file_path} not found")
        return env_vars

    with open(env_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip().strip("\"'")

    return env_vars


def create_settings_from_env(env_vars):
    """Create a settings.json structure from environment variables."""
    password = env_vars.get("POSTGRES_PASSWORD", "")
    if not password:
        raise ValueError("POSTGRES_PASSWORD must be supplied explicitly")
    encoded_password = quote(password, safe="")
    settings = {
        "database": {
            "url": f"postgresql://dementia_user:{encoded_password}@postgres:5432/dementia_db",
            "host": "postgres",
            "port": 5432,
            "name": "dementia_db",
            "username": "dementia_user",
            "password": password,
        },
        "redis": {"url": "redis://redis:6379", "host": "redis", "port": 6379, "db": 0},
        "telegram": {
            "bot_token": env_vars.get("TELEGRAM_BOT_TOKEN", ""),
            "webhook_url": env_vars.get("WEBHOOK_URL", ""),
            "webhook_secret": env_vars.get("WEBHOOK_SECRET", ""),
        },
        "openai": {
            "api_key": env_vars.get("OPENAI_API_KEY", ""),
            "base_url": env_vars.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "model": env_vars.get("OPENAI_MODEL", "gpt-4o-mini"),
            "max_tokens": int(env_vars.get("OPENAI_MAX_TOKENS", "2000")),
            "temperature": float(env_vars.get("OPENAI_TEMPERATURE", "0.7")),
            "timeout": int(env_vars.get("OPENAI_TIMEOUT", "60")),
        },
        "services": {
            "telegram_bot_url": env_vars.get(
                "TELEGRAM_BOT_SERVICE_URL", "http://telegram-bot:8001"
            ),
            "messaging_service_url": env_vars.get(
                "MESSAGING_SERVICE_URL", "http://messaging-service:8002"
            ),
            "agent_service_url": env_vars.get(
                "AGENT_SERVICE_URL", "http://agent-service:8003"
            ),
            "api_service_url": env_vars.get(
                "API_SERVICE_URL", "http://api-service:8004"
            ),
        },
        "security": {
            "api_key": env_vars.get("API_KEY", ""),
            "jwt_secret": env_vars.get("JWT_SECRET", "your-jwt-secret"),
            "allowed_hosts": ["*"],
        },
        "logging": {
            "level": env_vars.get("LOG_LEVEL", "INFO"),
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file_path": "/app/logs",
            "max_file_size": "10MB",
            "backup_count": 5,
        },
        "application": {
            "debug": env_vars.get("DEBUG", "false").lower() in ("true", "1", "t"),
            "timezone": "Your/City",
            "language": "en",
            "environment": "production",
            "project_name": "Dementia Support Bot",
            "version": "1.0.0",
        },
        "features": {
            "auto_messaging_enabled": True,
            "webhook_mode": True,
            "health_checks_enabled": True,
            "metrics_enabled": True,
        },
        "limits": {
            "max_users_per_day": 1000,
            "max_messages_per_user_per_hour": 50,
            "max_agent_requests_per_minute": 30,
        },
        "pinecone": {
            "api_key": env_vars.get("PINECONE_API_KEY", ""),
            "host": env_vars.get("PINECONE_HOST", ""),
            "index_name": env_vars.get("PINECONE_INDEX_NAME", "dementia"),
        },
        "yandex": {
            "api_key": env_vars.get("YANDEX_API_KEY", ""),
            "speechkit_url": env_vars.get(
                "YANDEX_SPEECHKIT_URL", "https://stt.api.cloud.yandex.net"
            ),
            "folder_id": env_vars.get("FOLDER_ID", ""),
        },
    }

    return settings


def main():
    """Main migration routine."""
    print("Migrating settings from .env to settings.json")
    print("=" * 50)

    # Find .env file
    env_paths = [".env", "../.env", "docker/.env"]

    env_file = None
    for path in env_paths:
        if os.path.exists(path):
            env_file = path
            break

    if not env_file:
        print(".env file not found.")
        print("Checked paths:")
        for path in env_paths:
            print(f"   - {path}")
        sys.exit(1)

    print(f"Found .env file: {env_file}")

    # Load variables from .env
    env_vars = load_env_file(env_file)
    print(f"Loaded {len(env_vars)} variables from .env")

    # Create settings.json structure
    settings = create_settings_from_env(env_vars)

    # Output path for settings.json
    settings_path = "settings.json"

    # Check existing settings.json
    if os.path.exists(settings_path):
        response = input(f"⚠️  File {settings_path} already exists. Overwrite? (y/n): ")
        if response.lower() != "y":
            print("Migration cancelled.")
            sys.exit(1)

    # Save settings.json
    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

        print(f"Settings saved to {settings_path}")
        print()
        print("Please review and configure:")
        print("   - telegram.bot_token")
        print("   - openai.api_key")
        print("   - database.password")
        print()
        print("Open settings.json and review all settings.")

    except Exception as e:
        print(f"Failed to save settings.json: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

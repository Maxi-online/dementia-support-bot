# Dementia Support Telegram Bot

A multi-agent Telegram bot that provides supportive conversations and guidance for people living with dementia and their caregivers.

This repository is prepared for public GitHub hosting: **no secrets are committed**, and runtime artifacts (DB files, logs, chat history, caches, virtual environments) are excluded via `.gitignore`.

## Key features

- Routing via an orchestrator to specialized agents (memory support, crisis intervention, medical knowledge, family support, etc.)
- Scheduled reminders and automated messaging
- Optional voice: speech-to-text and text-to-speech via Yandex SpeechKit (if configured)

## Requirements

- Python 3.11+
- (Optional) PostgreSQL + Redis (recommended for production / Docker deployment)

## Configuration (no `.env` for app secrets)

All application secrets and credentials must be stored in **`settings.json`** (ignored by git).

1. Copy the example config:

```bash
copy src\core\settings.json.example settings.json
```

1. Edit `settings.json` and fill:

- `telegram.bot_token`
- `openai.api_key`
- (Optional) `yandex.*` for voice features

## Local run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

## Docker deployment

See `docker/README.md`.

## Security & privacy notes

- **Do not commit** `settings.json`, DB files, chat history (`dialogs/`) or any user data.
- This project can write dialog history to local files for debugging; for public deployment you should keep `dialogs/` disabled/ignored and use secure storage if needed.

## License

MIT (see `LICENSE`).

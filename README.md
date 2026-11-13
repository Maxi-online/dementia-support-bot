# Dementia Support Telegram Bot

**A multi-agent conversational-assistant prototype for caregiver-support workflows.**

The project explores how an orchestrator can route a Telegram conversation to
specialized agents while retaining context, scheduling reminders and optionally
supporting voice. The implemented work is conversational software infrastructure;
clinical effectiveness has not been evaluated.

## Implemented components

- An orchestrator for agent selection, conversation context and response handling.
- Specialized agent modules for memory prompts, routines, family support,
  wellbeing, general enquiries and related conversation topics.
- Conversation summarization and history access.
- Reminder and automated-message components.
- Optional speech-to-text/text-to-speech through Yandex SpeechKit.
- Local application and Docker service layouts for bot, agent, API and messaging roles.

The agent names describe routing roles. They do not establish medical expertise,
diagnostic accuracy or a validated emergency-response service.

## Architecture

```mermaid
flowchart LR
    A[Telegram text / optional voice] --> B[Message orchestrator]
    B --> C[Conversation context]
    B --> D[Specialized agents]
    D --> E[Response / handoff]
    F[Reminder and messaging components] --> A
    E --> A
```

Key source entry points:

- [Application startup](src/main.py)
- [Orchestrator](src/core/orchestrator.py)
- [Agent modules](src/agents)
- [Configuration loader](src/core/config.py)
- [Automatic messaging](README_auto_messaging.md)

## Local setup

Use Python 3.11+ and create a project environment:

```bash
git clone https://github.com/Maxi-online/dementia-support-bot.git
cd dementia-support-bot
python -m venv .venv
```

On Windows PowerShell:

```powershell
& .venv/Scripts/python.exe -m pip install -r requirements.txt
if (!(Test-Path -LiteralPath settings.json)) { Copy-Item -LiteralPath src/core/settings.json.example -Destination settings.json }
```

On Linux/macOS:

```bash
.venv/bin/python -m pip install -r requirements.txt
test -e settings.json || cp src/core/settings.json.example settings.json
```

For a fresh setup, edit `settings.json` with `telegram.bot_token` and
`openai.api_key`. Voice features additionally require the configured Yandex
settings. Keep existing credentials when adapting an established deployment;
the copy commands above initialize a fresh configuration.

Start the configured application with the environment's Python:

```powershell
& .venv/Scripts/python.exe -m src.main
```

The equivalent POSIX command is `.venv/bin/python -m src.main`.
[Docker deployment instructions](docker/README.md) describe the separate service
layout; a Compose layout alone is not evidence of a verified production deployment.

## Data and validation boundaries

Conversation history and reminder data can contain personal information. Keep
runtime configuration, databases, logs and dialog history outside published
examples. Use synthetic conversations for demonstrations.

The repository demonstrates routing, scheduling and messenger/provider
integration. Agent quality, difficult handoffs, reminder delivery and behaviour
during provider failures require separate end-to-end evaluation. No clinical
outcomes or medical-quality scores are claimed here.

## License

[MIT](LICENSE). Third-party APIs and libraries retain their own terms.

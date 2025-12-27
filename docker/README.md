# Docker deployment

This folder contains a Docker Compose setup for running the project as a set of small services.

## Services

- **nginx**: gateway
- **telegram-bot**: Telegram updates handling
- **messaging-service**: scheduler / automated messaging
- **agent-service**: LLM agents service
- **api-service**: REST API
- **postgres**: PostgreSQL database
- **redis**: cache / jobs

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+

## Configuration

### 1) Application config (`settings.json`)

All application secrets and credentials are stored in `settings.json` (this file must NOT be committed).

From repository root:

```bash
cp src/core/settings.json.example settings.json
```

Edit `settings.json` and set at least:

- `telegram.bot_token`
- `openai.api_key`
- `openai.model` (default in the example is `gpt-5-nano`)
- (optional) `yandex.*` — required for voice features

### 2) Docker-only variables (`.env`)

Docker Compose can use a `.env` file for container variables (not application secrets). The minimal requirement:

```bash
cp docker/env.example .env
```

Then edit `.env` and set:

- `POSTGRES_PASSWORD`

## Start

From repository root:

```bash
cd docker
docker-compose up -d --build
```

## Logs

```bash
cd docker
docker-compose logs -f
```

Or for a single service:

```bash
docker-compose logs -f telegram-bot
```

## Stop

```bash
cd docker
docker-compose down
```

## Troubleshooting

- **Telegram bot does not start**: verify `telegram.bot_token` in `settings.json`
- **OpenAI errors**: verify `openai.api_key` and network access to the configured `openai.base_url`
- **Database connection issues**: verify `database.url` in `settings.json` and `POSTGRES_PASSWORD` in `.env`


#!/bin/bash

# Logs viewer script

# Move to docker-compose directory
cd "$(dirname "$0")/.."

# If an argument is provided, show logs for that service
if [ $# -eq 1 ]; then
    echo "📋 Logs for service $1:"
    docker-compose logs -f --tail=100 "$1"
else
    echo "📋 Logs for all services:"
    echo "Available services: telegram-bot, messaging-service, agent-service, api-service, postgres, redis, nginx"
    echo "To view logs for a specific service: $0 <service-name>"
    echo ""
    docker-compose logs -f --tail=50
fi

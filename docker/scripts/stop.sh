#!/bin/bash

# Service stop script

echo "🛑 Stopping Dementia Support Bot services..."

# Move to docker-compose directory
cd "$(dirname "$0")/.."

# Stop and remove containers
docker-compose down

echo "✅ Services stopped!"

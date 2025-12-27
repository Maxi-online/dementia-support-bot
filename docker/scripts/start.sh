#!/bin/bash

# Service start script

echo "🚀 Starting Dementia Support Bot services..."

# Move to docker-compose directory
cd "$(dirname "$0")/.."

# Check configuration
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Copy env.example to .env and configure variables"
    exit 1
fi

# Create network if it doesn't exist
docker network create dementia_network 2>/dev/null || true

# Start services
echo "📦 Starting containers..."
docker-compose up -d

# Wait for startup
echo "⏳ Waiting for services to start..."
sleep 30

# Status check
echo "📊 Service status:"
docker-compose ps

echo "✅ Services started!"
echo "🌐 Available endpoints:"
echo "   • Health check: http://localhost/health"
echo "   • API: http://localhost:8004/docs"

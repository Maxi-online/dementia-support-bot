#!/bin/bash

# Deployment script for the Dementia Support Bot project on a Linux server

set -e  # Exit on error

echo "🚀 Starting deployment of the Dementia Support Bot project..."

# Check Docker and Docker Compose
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed. Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
        echo "✅ Docker installed"
    else
        echo "✅ Docker is already installed"
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose is not installed. Installing..."
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        echo "✅ Docker Compose installed"
    else
        echo "✅ Docker Compose is already installed"
    fi
}

# Check configuration
check_config() {
    echo "🔍 Checking configuration..."
    
    # Check .env file for Docker
    if [ ! -f ".env" ]; then
        if [ -f "docker/env.example" ]; then
            echo "📋 Copying Docker .env example..."
            cp docker/env.example .env
            echo "⚠️  IMPORTANT: Edit the Docker .env file!"
            echo "   You must set POSTGRES_PASSWORD"
        else
            echo "❌ docker/env.example not found!"
            exit 1
        fi
    else
        echo "✅ .env file found"
    fi
    
    # Check settings.json for the application
    if [ ! -f "settings.json" ]; then
        if [ -f "src/core/settings.json.example" ]; then
            echo "📋 Copying settings.json example..."
            cp src/core/settings.json.example settings.json
            echo "⚠️  IMPORTANT: Edit settings.json with your settings!"
            echo "   Key settings:"
            echo "   - telegram.bot_token - Telegram bot token"
            echo "   - openai.api_key - OpenAI API key"
            echo "   - database.password - database password"
            echo ""
            echo "🔧 Open settings.json in an editor and configure it"
            read -p "Press Enter after editing settings.json..."
        else
            echo "❌ src/core/settings.json.example not found!"
            exit 1
        fi
    else
        echo "✅ settings.json found"
    fi
}

# Create required directories
create_directories() {
    echo "📁 Creating required directories..."
    
    mkdir -p logs
    mkdir -p ssl
    mkdir -p backup
    
    # Set permissions
    chmod 755 logs
    chmod 700 ssl
    chmod 755 backup
    
    echo "✅ Directories created"
}

# SSL setup (optional)
setup_ssl() {
    echo "🔒 Configuring SSL..."
    
    if [ ! -f "ssl/cert.pem" ] || [ ! -f "ssl/private.key" ]; then
        echo "⚠️  SSL certificates not found"
        read -p "Create a self-signed certificate for testing? (y/n): " create_ssl
        
        if [ "$create_ssl" = "y" ]; then
            echo "🔧 Creating self-signed certificate..."
            openssl req -x509 -newkey rsa:4096 -keyout ssl/private.key -out ssl/cert.pem -days 365 -nodes \
                -subj "/C=US/ST=State/L=City/O=DementiaSupport/CN=localhost"
            chmod 600 ssl/private.key
            chmod 644 ssl/cert.pem
            echo "✅ Self-signed certificate created"
        else
            echo "ℹ️  Copy your SSL certificates into the ssl/ folder:"
            echo "   cert.pem - certificate"
            echo "   private.key - private key"
        fi
    else
        echo "✅ SSL certificates found"
    fi
}

# Build images
build_images() {
    echo "🏗️  Building Docker images..."
    
    # Stop existing containers
    docker-compose down 2>/dev/null || true
    
    # Build images
    docker-compose build --no-cache
    
    echo "✅ Images built"
}

# Start services
start_services() {
    echo "🚀 Starting services..."
    
    # Start in background
    docker-compose up -d
    
    echo "⏳ Waiting for services to start..."
    sleep 30
    
    # Status check
    docker-compose ps
    
    echo "✅ Services started"
}

# Health checks
health_check() {
    echo "🔍 Checking service health..."
    
    services=("nginx:80" "telegram-bot:8001" "messaging-service:8002" "agent-service:8003" "api-service:8004")
    
    for service in "${services[@]}"; do
        IFS=':' read -r name port <<< "$service"
        if curl -f -s http://localhost:$port/health > /dev/null; then
            echo "✅ $name is healthy"
        else
            echo "❌ $name is not responding"
        fi
    done
}

# Backup (if data already exists)
backup_data() {
    if docker volume ls | grep -q dementia_postgres_data; then
        echo "💾 Creating database backup..."
        timestamp=$(date +%Y%m%d_%H%M%S)
        docker-compose exec -T postgres pg_dump -U dementia_user dementia_db > backup/db_backup_$timestamp.sql
        echo "✅ Backup created: backup/db_backup_$timestamp.sql"
    fi
}

# systemd autostart (optional)
setup_systemd() {
    read -p "Enable autostart on boot via systemd? (y/n): " setup_autostart
    
    if [ "$setup_autostart" = "y" ]; then
        echo "🔧 Configuring autostart..."
        
        current_dir=$(pwd)
        
        sudo tee /etc/systemd/system/dementia-support.service > /dev/null <<EOF
[Unit]
Description=Dementia Support Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$current_dir
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable dementia-support.service
        
        echo "✅ Autostart configured"
        echo "   Manage it with:"
        echo "   sudo systemctl start dementia-support"
        echo "   sudo systemctl stop dementia-support"
        echo "   sudo systemctl status dementia-support"
    fi
}

# Show deployment info
show_info() {
    echo ""
    echo "🎉 Deployment completed!"
    echo ""
    echo "📋 Services:"
    echo "   • Nginx Gateway: http://localhost:80"
    echo "   • API Service: http://localhost:8004"
    echo "   • Health checks: http://localhost/health"
    echo ""
    echo "🔧 Useful commands:"
    echo "   • Logs: docker-compose logs -f [service_name]"
    echo "   • Status: docker-compose ps"
    echo "   • Stop: docker-compose down"
    echo "   • Restart: docker-compose restart"
    echo ""
    echo "📁 Important folders:"
    echo "   • logs/ - service logs"
    echo "   • backup/ - backups"
    echo "   • ssl/ - SSL certificates"
    echo ""
    echo "⚠️  Don't forget:"
    echo "   1. Configure the Telegram webhook (if using webhook mode)"
    echo "   2. Check firewall settings"
    echo "   3. Set up monitoring and backups"
}

# Main
main() {
    echo "🤖 Deploying the Dementia Support Bot project"
    echo "=========================================="
    
    # Root check for some operations
    if [ "$EUID" -eq 0 ]; then
        echo "⚠️  Running as root is not recommended. Use a normal user account."
        read -p "Continue anyway? (y/n): " continue_root
        [ "$continue_root" != "y" ] && exit 1
    fi
    
    check_docker
    check_config
    create_directories
    setup_ssl
    backup_data
    build_images
    start_services
    health_check
    setup_systemd
    show_info
}

# Run
main "$@"

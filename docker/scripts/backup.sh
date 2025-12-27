#!/bin/bash

# Backup creation script

echo "💾 Creating a backup..."

# Move to docker-compose directory
cd "$(dirname "$0")/.."

# Create backup directory
mkdir -p backup

# Generate timestamped file prefix
timestamp=$(date +%Y%m%d_%H%M%S)
backup_file="backup/dementia_backup_$timestamp"

# Database backup
echo "📊 Database backup..."
docker-compose exec -T postgres pg_dump -U dementia_user -h localhost dementia_db > "${backup_file}.sql"

# Logs archive
echo "📋 Archiving logs..."
tar -czf "${backup_file}_logs.tar.gz" logs/ 2>/dev/null || true

# Configuration archive
echo "⚙️ Archiving configuration..."
tar -czf "${backup_file}_config.tar.gz" .env docker-compose.yml nginx/ 2>/dev/null || true

echo "✅ Backup created:"
echo "   • Database: ${backup_file}.sql"
echo "   • Logs: ${backup_file}_logs.tar.gz"
echo "   • Config: ${backup_file}_config.tar.gz"

# Cleanup old backups (older than 7 days)
find backup/ -name "dementia_backup_*" -mtime +7 -delete 2>/dev/null || true

echo "🧹 Old backups cleaned up"

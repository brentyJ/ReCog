# ReCog Self-Hosting Guide

Complete guide to deploying ReCog on your own infrastructure.

**Version**: 0.9
**Last Updated**: January 2026

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Docker)](#quick-start-docker)
3. [Docker Deployment](#docker-deployment)
4. [Manual Deployment](#manual-deployment)
5. [Environment Configuration](#environment-configuration)
6. [Database Setup](#database-setup)
7. [Production Considerations](#production-considerations)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 2 GB | 4+ GB |
| Storage | 1 GB | 10+ GB (depends on document volume) |
| OS | Linux, macOS, Windows | Linux (Ubuntu 22.04+) |

### Required Software

**For Docker deployment:**
- Docker 24.0+ ([Install Docker](https://docs.docker.com/get-docker/))
- Docker Compose 2.20+ (included with Docker Desktop)

**For manual deployment:**
- Python 3.11+ ([Download Python](https://www.python.org/downloads/))
- Node.js 18+ ([Download Node.js](https://nodejs.org/))
- npm 9+ (included with Node.js)
- Git ([Download Git](https://git-scm.com/downloads))

### API Keys (Optional but Recommended)

ReCog's Tier 0 signal extraction works without any API keys. For LLM-powered features (Tier 1-3), you need at least one:

| Provider | Get API Key | Models |
|----------|-------------|--------|
| OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) | gpt-4o-mini (default), gpt-4o |
| Anthropic | [console.anthropic.com](https://console.anthropic.com/settings/keys) | claude-sonnet-4 |

---

## Quick Start (Docker)

The fastest way to get ReCog running:

```bash
# 1. Clone the repository
git clone https://github.com/brentyJ/recog.git
cd recog

# 2. Create environment file
cp _scripts/.env.example _scripts/.env

# 3. Edit .env with your API keys (optional for Tier 0)
# Use your preferred editor:
# nano _scripts/.env
# notepad _scripts/.env  (Windows)

# 4. Start services
docker compose up -d

# 5. Verify it's running
curl http://localhost:5100/api/health
```

**Access points:**
- **API**: http://localhost:5100
- **API Docs**: http://localhost:5100/docs (Swagger UI)
- **Health Check**: http://localhost:5100/api/health

The UI is not included in Docker by default. See [Manual Deployment](#manual-deployment) for UI setup.

---

## Docker Deployment

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    docker-compose.yml                        │
├─────────────────────────┬───────────────────────────────────┤
│      recog (API)        │         worker (Background)       │
│  Flask + Gunicorn       │    Queue processor                │
│  Port 5100              │    Depends on recog health        │
├─────────────────────────┴───────────────────────────────────┤
│                    recog_data (Volume)                       │
│  Persistent storage: SQLite DB, uploaded files               │
└─────────────────────────────────────────────────────────────┘
```

### Single Container (API Only)

For simple deployments without background processing:

```bash
# Build the image
docker build -t recog .

# Run with environment variables
docker run -d \
  --name recog \
  -p 5100:5100 \
  -v recog_data:/app/_data \
  -e RECOG_OPENAI_API_KEY=sk-your-key \
  -e RECOG_DATA_DIR=/app/_data \
  recog

# Verify
docker logs recog
curl http://localhost:5100/api/health
```

### Docker Compose (Recommended)

Full setup with API server and background worker:

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Check status
docker compose ps

# Stop services
docker compose down

# Stop and remove data (WARNING: deletes database!)
docker compose down -v
```

### Custom docker-compose.yml

Create a `docker-compose.override.yml` for local customizations:

```yaml
# docker-compose.override.yml
services:
  recog:
    ports:
      - "8080:5100"  # Custom port
    environment:
      - RECOG_DEBUG=true
      - RECOG_LOG_LEVEL=DEBUG
```

### Using Environment File

The default setup mounts `_scripts/.env` into the container:

```yaml
volumes:
  - ./_scripts/.env:/app/.env:ro  # Read-only mount
```

Alternatively, use `env_file` directive:

```yaml
services:
  recog:
    env_file:
      - ./_scripts/.env
```

### Persistent Data

Data is stored in a Docker volume named `recog_data`:

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect recog_recog_data

# Backup data (while container is stopped)
docker run --rm -v recog_recog_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/recog-backup-$(date +%Y%m%d).tar.gz -C /data .

# Restore data
docker run --rm -v recog_recog_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/recog-backup-20260115.tar.gz -C /data
```

---

## Manual Deployment

### Backend Setup

```bash
# 1. Clone repository
git clone https://github.com/brentyJ/recog.git
cd recog

# 2. Create Python virtual environment
cd _scripts
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create environment file
cp .env.example .env
# Edit .env with your settings

# 5. Initialize database
python recog_cli.py db init

# 6. Verify database
python recog_cli.py db check
```

### Running the Backend

**Development mode:**

```bash
# From _scripts/ directory with venv activated
python server.py
```

**Production mode (with Gunicorn):**

```bash
# From _scripts/ directory
gunicorn --bind 0.0.0.0:5100 --workers 2 --timeout 120 server:app
```

**With systemd (Linux):**

Create `/etc/systemd/system/recog.service`:

```ini
[Unit]
Description=ReCog API Server
After=network.target

[Service]
Type=simple
User=recog
WorkingDirectory=/opt/recog/_scripts
Environment=PATH=/opt/recog/_scripts/venv/bin
ExecStart=/opt/recog/_scripts/venv/bin/gunicorn --bind 0.0.0.0:5100 --workers 2 --timeout 120 server:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable recog
sudo systemctl start recog

# Check status
sudo systemctl status recog
```

### Background Worker

The worker processes queued extraction jobs:

```bash
# Run worker (separate terminal)
python worker.py
```

**As systemd service:**

Create `/etc/systemd/system/recog-worker.service`:

```ini
[Unit]
Description=ReCog Background Worker
After=recog.service
Requires=recog.service

[Service]
Type=simple
User=recog
WorkingDirectory=/opt/recog/_scripts
Environment=PATH=/opt/recog/_scripts/venv/bin
ExecStart=/opt/recog/_scripts/venv/bin/python worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Frontend Setup (Optional)

The React UI is optional - you can use the API directly or via Swagger UI.

```bash
# From project root
cd _ui

# Install dependencies
npm install

# Development server (http://localhost:3100)
npm run dev

# Production build
npm run build
```

**Serving the built frontend:**

After `npm run build`, the static files are in `_ui/dist/`. Serve with any web server:

```bash
# With Python
cd _ui/dist
python -m http.server 3100

# With Node.js (install serve globally)
npm install -g serve
serve -s dist -l 3100

# With nginx (see Production Considerations)
```

---

## Environment Configuration

### Complete Variable Reference

Create `_scripts/.env` with these variables:

```bash
# =============================================================================
# LLM PROVIDERS
# =============================================================================

# Default provider: "openai" or "anthropic"
# If both keys are set, this determines which is used by default
RECOG_LLM_PROVIDER=openai

# OpenAI Configuration
RECOG_OPENAI_API_KEY=sk-your-openai-key-here
RECOG_OPENAI_MODEL=gpt-4o-mini

# Anthropic Configuration
RECOG_ANTHROPIC_API_KEY=sk-ant-api03-your-anthropic-key-here
RECOG_ANTHROPIC_MODEL=claude-sonnet-4-20250514

# =============================================================================
# COST CONTROLS
# =============================================================================

# Maximum spend per session (in cents) - prevents runaway costs
RECOG_COST_LIMIT_CENTS=100

# Maximum tokens per extraction call
RECOG_MAX_TOKENS=2000

# =============================================================================
# SERVER
# =============================================================================

# Server port (default: 5100)
RECOG_PORT=5100

# Debug mode - enables detailed logging (default: false)
RECOG_DEBUG=false

# Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
RECOG_LOG_LEVEL=INFO

# Data directory for database and uploads (default: ./_data)
RECOG_DATA_DIR=./_data

# =============================================================================
# RATE LIMITING
# =============================================================================

# Enable rate limiting (default: true)
RECOG_RATE_LIMIT_ENABLED=true

# Rate limits (requests per minute)
# - General endpoints: 60/min
# - LLM operations: 10/min
# - File uploads: 20/min
# - Health checks: 120/min

# =============================================================================
# CACHING
# =============================================================================

# Enable response caching (default: true)
RECOG_CACHE_ENABLED=true

# Cache TTL in hours (default: 24)
RECOG_CACHE_TTL_HOURS=24

# =============================================================================
# FILE UPLOADS
# =============================================================================

# Maximum file size in MB (default: 10)
RECOG_MAX_FILE_SIZE_MB=10
```

### Provider Priority

When both API keys are configured:

1. `RECOG_LLM_PROVIDER` determines the default
2. Per-request `provider` parameter overrides the default

```bash
# Example: Default to OpenAI, but allow Anthropic override
RECOG_LLM_PROVIDER=openai
RECOG_OPENAI_API_KEY=sk-...
RECOG_ANTHROPIC_API_KEY=sk-ant-...
```

```bash
# Override per-request
curl -X POST http://localhost:5100/api/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "...", "provider": "anthropic"}'
```

### Validate Configuration

```bash
# Check configuration is valid
python recog_cli.py config

# Expected output:
# Configuration valid
# - Provider: openai
# - Model: gpt-4o-mini
# - Data dir: ./_data
# - Cost limit: 100 cents
```

---

## Database Setup

### Initialization

ReCog uses SQLite - no external database required.

```bash
# Initialize database (creates tables)
python recog_cli.py db init

# Check database status
python recog_cli.py db check
```

Expected output:
```
Database: _data/recog.db
Tables: 27
Status: healthy
```

### Database Location

By default: `_scripts/_data/recog.db`

Override with `RECOG_DATA_DIR`:

```bash
RECOG_DATA_DIR=/var/lib/recog
# Database will be at: /var/lib/recog/recog.db
```

### Backup Strategy

**Manual backup:**

```bash
# Stop services first for consistency
systemctl stop recog recog-worker

# Copy database
cp _data/recog.db _data/recog.db.backup-$(date +%Y%m%d)

# Or use SQLite backup command
sqlite3 _data/recog.db ".backup '_data/recog-backup-$(date +%Y%m%d).db'"

# Restart services
systemctl start recog recog-worker
```

**Automated backup script:**

Create `/opt/recog/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/recog"
DB_PATH="/opt/recog/_scripts/_data/recog.db"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/recog-$DATE.db'"

# Keep only last 7 days
find "$BACKUP_DIR" -name "recog-*.db" -mtime +7 -delete

echo "Backup complete: recog-$DATE.db"
```

Add to crontab:
```bash
# Daily backup at 2 AM
0 2 * * * /opt/recog/backup.sh >> /var/log/recog-backup.log 2>&1
```

### Migration

Database migrations are applied automatically on startup. For manual migration:

```bash
# Check current schema version
sqlite3 _data/recog.db "SELECT * FROM schema_version;"

# Apply specific migration
sqlite3 _data/recog.db < migrations/migration_v0_5_cases.sql
```

---

## Production Considerations

### HTTPS with Nginx

Create `/etc/nginx/sites-available/recog`:

```nginx
server {
    listen 80;
    server_name recog.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name recog.yourdomain.com;

    # SSL certificates (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/recog.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/recog.yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:5100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long-running extraction
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
    }

    # Swagger UI
    location /docs {
        proxy_pass http://127.0.0.1:5100;
        proxy_set_header Host $host;
    }

    location /apispec.json {
        proxy_pass http://127.0.0.1:5100;
        proxy_set_header Host $host;
    }

    # Frontend (if serving static build)
    location / {
        root /opt/recog/_ui/dist;
        try_files $uri $uri/ /index.html;
    }

    # File upload size
    client_max_body_size 50M;
}
```

Enable and test:

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/recog /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### Let's Encrypt SSL

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d recog.yourdomain.com

# Auto-renewal (added automatically)
sudo systemctl status certbot.timer
```

### Gunicorn Optimization

For higher traffic, adjust Gunicorn workers:

```bash
# Formula: (2 x CPU cores) + 1
# For 4-core server: 9 workers

gunicorn --bind 0.0.0.0:5100 \
  --workers 9 \
  --worker-class sync \
  --timeout 120 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --access-logfile /var/log/recog/access.log \
  --error-logfile /var/log/recog/error.log \
  server:app
```

### Health Monitoring

ReCog includes a built-in health check endpoint:

```bash
# Basic health check
curl http://localhost:5100/api/health

# Response includes:
# - Database connectivity
# - Table count
# - Available LLM providers
# - Rate limit status
```

**Monitoring with external tools:**

```bash
# Uptime Kuma / Healthchecks.io
curl -fsS http://localhost:5100/api/health > /dev/null && curl -fsS https://hc-ping.com/your-uuid

# Prometheus metrics (if needed, add prometheus_flask_exporter)
```

### Log Management

Configure centralized logging:

```bash
# Create log directory
sudo mkdir -p /var/log/recog
sudo chown recog:recog /var/log/recog

# Update systemd service
Environment=RECOG_LOG_LEVEL=INFO
StandardOutput=append:/var/log/recog/server.log
StandardError=append:/var/log/recog/error.log
```

Log rotation (`/etc/logrotate.d/recog`):

```
/var/log/recog/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 recog recog
    sharedscripts
    postrotate
        systemctl reload recog >/dev/null 2>&1 || true
    endscript
}
```

### Security Checklist

- [ ] API keys stored in environment variables, not code
- [ ] `.env` file has restricted permissions (`chmod 600`)
- [ ] Database file has restricted permissions
- [ ] HTTPS enabled with valid certificate
- [ ] Rate limiting enabled
- [ ] Firewall configured (only expose needed ports)
- [ ] Regular backups configured
- [ ] Log monitoring set up

---

## Troubleshooting

### Common Issues

#### "Connection refused" on port 5100

```bash
# Check if server is running
ps aux | grep -E "(gunicorn|server.py)"

# Check if port is in use
lsof -i :5100  # Linux/macOS
netstat -ano | findstr :5100  # Windows

# Check logs
tail -50 /var/log/recog/error.log
# or
docker compose logs recog
```

#### "LLM not configured" error

```bash
# Verify environment variables are set
echo $RECOG_OPENAI_API_KEY

# Check .env file exists and is readable
cat _scripts/.env | grep API_KEY

# Test API key directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $RECOG_OPENAI_API_KEY"
```

#### Database errors

```bash
# Check database exists
ls -la _data/recog.db

# Verify permissions
# Should be readable/writable by server user

# Reinitialize (WARNING: loses data!)
rm _data/recog.db
python recog_cli.py db init
```

#### Docker container won't start

```bash
# Check container logs
docker compose logs recog

# Common issues:
# - Port already in use: change port in docker-compose.yml
# - Volume mount error: ensure .env file exists
# - Memory limit: increase Docker memory allocation

# Rebuild from scratch
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

#### Rate limit errors (429)

```bash
# Check rate limit status
curl http://localhost:5100/api/rate-limit/status

# Disable rate limiting temporarily (development only)
RECOG_RATE_LIMIT_ENABLED=false

# Wait for rate limit window to reset (usually 60 seconds)
```

#### File upload fails

```bash
# Check file size limit
echo $RECOG_MAX_FILE_SIZE_MB

# Increase limit if needed
RECOG_MAX_FILE_SIZE_MB=50

# For nginx, also set:
# client_max_body_size 50M;
```

### Getting Help

1. **Check the logs first** - most issues are logged
2. **API Documentation** - http://localhost:5100/docs
3. **Health endpoint** - http://localhost:5100/api/health
4. **GitHub Issues** - [github.com/brentyJ/recog/issues](https://github.com/brentyJ/recog/issues)

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Environment variable
RECOG_DEBUG=true
RECOG_LOG_LEVEL=DEBUG

# Or run server directly with debug
python server.py  # Flask debug mode
```

---

## Quick Reference

### Ports

| Service | Default Port |
|---------|--------------|
| API Server | 5100 |
| Frontend Dev | 3100 |
| Swagger UI | 5100/docs |

### Key Paths

| Path | Description |
|------|-------------|
| `_scripts/` | Backend Python code |
| `_scripts/_data/` | Database and uploads |
| `_scripts/.env` | Environment configuration |
| `_ui/` | Frontend React code |
| `_ui/dist/` | Built frontend assets |

### Useful Commands

```bash
# Health check
curl http://localhost:5100/api/health

# Tier 0 test (no API key needed)
curl -X POST http://localhost:5100/api/tier0 \
  -H "Content-Type: application/json" \
  -d '{"text": "John met Sarah yesterday"}'

# Database status
python recog_cli.py db check

# Clear rate limit cache
curl -X POST http://localhost:5100/api/cache/clear

# Docker status
docker compose ps
docker compose logs -f recog
```

---

*Need help? Open an issue at [github.com/brentyJ/recog/issues](https://github.com/brentyJ/recog/issues)*

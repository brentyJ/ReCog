# ReCog Configuration Reference

Complete reference for all environment variables used by ReCog.

**Location**: `_scripts/.env` (copy from `.env.example`)

---

## Quick Start

```bash
# Minimal configuration (Tier 0 only - no LLM)
RECOG_DATA_DIR=./_data
RECOG_PORT=5100

# Add LLM support (pick one or both)
RECOG_OPENAI_API_KEY=sk-...
RECOG_ANTHROPIC_API_KEY=sk-ant-...
```

---

## LLM Providers

### RECOG_LLM_PROVIDER

Default LLM provider when multiple are configured.

| | |
|---|---|
| **Type** | string |
| **Default** | `openai` |
| **Options** | `openai`, `anthropic` |

```bash
RECOG_LLM_PROVIDER=anthropic
```

### RECOG_OPENAI_API_KEY

OpenAI API key for GPT models.

| | |
|---|---|
| **Type** | string |
| **Default** | (none) |
| **Required** | For OpenAI provider |

```bash
RECOG_OPENAI_API_KEY=sk-proj-...
```

Get your key: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### RECOG_OPENAI_MODEL

OpenAI model to use for extraction and synthesis.

| | |
|---|---|
| **Type** | string |
| **Default** | `gpt-4o-mini` |
| **Options** | `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo` |

```bash
RECOG_OPENAI_MODEL=gpt-4o
```

### RECOG_ANTHROPIC_API_KEY

Anthropic API key for Claude models.

| | |
|---|---|
| **Type** | string |
| **Default** | (none) |
| **Required** | For Anthropic provider |

```bash
RECOG_ANTHROPIC_API_KEY=sk-ant-api03-...
```

Get your key: [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)

### RECOG_ANTHROPIC_MODEL

Anthropic model to use.

| | |
|---|---|
| **Type** | string |
| **Default** | `claude-sonnet-4-20250514` |
| **Options** | `claude-sonnet-4-20250514`, `claude-3-5-sonnet-20241022` |

```bash
RECOG_ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

---

## Server

### RECOG_PORT

HTTP port for the API server.

| | |
|---|---|
| **Type** | integer |
| **Default** | `5100` |

```bash
RECOG_PORT=8080
```

### RECOG_DEBUG

Enable Flask debug mode (auto-reload, detailed errors).

| | |
|---|---|
| **Type** | boolean |
| **Default** | `false` |

```bash
RECOG_DEBUG=true
```

**Warning**: Never enable in production - exposes sensitive information.

### RECOG_DATA_DIR

Directory for database, uploads, cache, and logs.

| | |
|---|---|
| **Type** | path |
| **Default** | `./_data` |

```bash
RECOG_DATA_DIR=/var/lib/recog
```

Creates subdirectories:
- `recog.db` - SQLite database
- `uploads/` - Uploaded files
- `cache/` - Response cache
- `logs/` - Log files

### RECOG_SKIP_VALIDATION

Skip configuration validation on startup.

| | |
|---|---|
| **Type** | boolean |
| **Default** | `false` |

```bash
RECOG_SKIP_VALIDATION=true
```

Use during development when API keys aren't needed.

---

## File Uploads

### RECOG_MAX_FILE_SIZE_MB

Maximum upload file size in megabytes.

| | |
|---|---|
| **Type** | float |
| **Default** | `10` |

```bash
RECOG_MAX_FILE_SIZE_MB=50
```

**Note**: Also configure nginx `client_max_body_size` if using reverse proxy.

---

## Cost Controls

### RECOG_COST_LIMIT_CENTS

Maximum LLM spend per worker session (in cents).

| | |
|---|---|
| **Type** | integer |
| **Default** | `100` |

```bash
RECOG_COST_LIMIT_CENTS=500
```

Worker stops processing when limit is reached. Reset by restarting worker.

---

## Logging

### RECOG_LOG_LEVEL

Logging verbosity level.

| | |
|---|---|
| **Type** | string |
| **Default** | `INFO` |
| **Options** | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

```bash
RECOG_LOG_LEVEL=DEBUG
```

### RECOG_LOG_FILE

Path to log file.

| | |
|---|---|
| **Type** | path |
| **Default** | `{DATA_DIR}/logs/recog.log` |

```bash
RECOG_LOG_FILE=/var/log/recog/server.log
```

### RECOG_LOG_JSON

Output logs in JSON format (for log aggregators).

| | |
|---|---|
| **Type** | boolean |
| **Default** | `false` |

```bash
RECOG_LOG_JSON=true
```

---

## Response Cache

### RECOG_CACHE_ENABLED

Enable caching of LLM responses.

| | |
|---|---|
| **Type** | boolean |
| **Default** | `true` |

```bash
RECOG_CACHE_ENABLED=false
```

Caching prevents duplicate LLM calls for identical text, reducing costs.

### RECOG_CACHE_TTL_HOURS

Cache entry time-to-live in hours.

| | |
|---|---|
| **Type** | integer |
| **Default** | `24` |

```bash
RECOG_CACHE_TTL_HOURS=168  # 1 week
```

---

## Rate Limiting

### RECOG_RATE_LIMIT_ENABLED

Enable API rate limiting.

| | |
|---|---|
| **Type** | boolean |
| **Default** | `true` |

```bash
RECOG_RATE_LIMIT_ENABLED=false
```

### RECOG_RATE_LIMIT_STORAGE

Rate limit storage backend.

| | |
|---|---|
| **Type** | string |
| **Default** | `memory://` |
| **Options** | `memory://`, `redis://host:port` |

```bash
RECOG_RATE_LIMIT_STORAGE=redis://localhost:6379
```

Use Redis for multi-instance deployments.

### RECOG_RATE_LIMIT_DEFAULT

Default rate limit for general endpoints.

| | |
|---|---|
| **Type** | string |
| **Default** | `60 per minute` |

```bash
RECOG_RATE_LIMIT_DEFAULT=120 per minute
```

### RECOG_RATE_LIMIT_EXPENSIVE

Rate limit for LLM-powered endpoints (extract, synth, critique).

| | |
|---|---|
| **Type** | string |
| **Default** | `10 per minute` |

```bash
RECOG_RATE_LIMIT_EXPENSIVE=20 per minute
```

### RECOG_RATE_LIMIT_UPLOAD

Rate limit for file upload endpoints.

| | |
|---|---|
| **Type** | string |
| **Default** | `20 per minute` |

```bash
RECOG_RATE_LIMIT_UPLOAD=50 per minute
```

---

## Background Worker

### RECOG_WORKER_POLL

Worker polling interval in seconds.

| | |
|---|---|
| **Type** | integer |
| **Default** | `5` |

```bash
RECOG_WORKER_POLL=10
```

### RECOG_WORKER_BATCH

Maximum items to process per batch.

| | |
|---|---|
| **Type** | integer |
| **Default** | `10` |

```bash
RECOG_WORKER_BATCH=25
```

---

## Auto-Progress

### RECOG_AUTO_PROGRESS_INTERVAL

Interval (seconds) for automatic workflow state advancement.

| | |
|---|---|
| **Type** | integer |
| **Default** | `10` |

```bash
RECOG_AUTO_PROGRESS_INTERVAL=30
```

---

## Entity Validation

### RECOG_VALIDATE_ENTITIES_LLM

Automatically validate entities with LLM during extraction.

| | |
|---|---|
| **Type** | boolean |
| **Default** | `false` |

```bash
RECOG_VALIDATE_ENTITIES_LLM=true
```

Increases accuracy but adds LLM cost per extraction.

---

## Legacy Variables

These are deprecated but still supported for backwards compatibility:

| Variable | Replacement |
|----------|-------------|
| `RECOG_LLM_API_KEY` | `RECOG_OPENAI_API_KEY` |
| `RECOG_LLM_MODEL` | `RECOG_OPENAI_MODEL` |

---

## Example Configurations

### Development (Tier 0 only)

```bash
RECOG_DATA_DIR=./_data
RECOG_PORT=5100
RECOG_DEBUG=true
RECOG_LOG_LEVEL=DEBUG
RECOG_SKIP_VALIDATION=true
RECOG_RATE_LIMIT_ENABLED=false
```

### Development (with LLM)

```bash
RECOG_DATA_DIR=./_data
RECOG_PORT=5100
RECOG_DEBUG=true
RECOG_LOG_LEVEL=DEBUG

RECOG_OPENAI_API_KEY=sk-...
RECOG_COST_LIMIT_CENTS=50
```

### Production

```bash
RECOG_DATA_DIR=/var/lib/recog
RECOG_PORT=5100
RECOG_DEBUG=false
RECOG_LOG_LEVEL=INFO
RECOG_LOG_JSON=true
RECOG_LOG_FILE=/var/log/recog/server.log

RECOG_OPENAI_API_KEY=sk-...
RECOG_ANTHROPIC_API_KEY=sk-ant-...
RECOG_LLM_PROVIDER=openai

RECOG_COST_LIMIT_CENTS=1000
RECOG_MAX_FILE_SIZE_MB=50

RECOG_CACHE_ENABLED=true
RECOG_CACHE_TTL_HOURS=48

RECOG_RATE_LIMIT_ENABLED=true
RECOG_RATE_LIMIT_STORAGE=redis://localhost:6379
```

---

## Validation

Check your configuration:

```bash
cd _scripts
python recog_cli.py config
```

Or via API:

```bash
curl http://localhost:5100/api/health
```

The health endpoint shows which providers are configured and available.

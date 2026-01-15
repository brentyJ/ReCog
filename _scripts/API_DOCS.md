# ReCog API Documentation

REST API for document intelligence and insight extraction.

**Base URL:** `http://localhost:5100`

**Interactive Docs:** [http://localhost:5100/docs](http://localhost:5100/docs) (Swagger UI)

**OpenAPI Spec:** [http://localhost:5100/apispec.json](http://localhost:5100/apispec.json)

## Quick Start

```bash
# Check server health
curl http://localhost:5100/api/health

# Upload a file
curl -X POST http://localhost:5100/api/upload \
  -F "file=@document.pdf"

# Run Tier 0 signal extraction (free, no LLM)
curl -X POST http://localhost:5100/api/tier0 \
  -H "Content-Type: application/json" \
  -d '{"text": "I am really frustrated with the delays. John promised delivery by Friday."}'

# Extract insights (requires LLM API key)
curl -X POST http://localhost:5100/api/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "Meeting notes from project review...", "source_type": "document"}'
```

---

## Core Endpoints

### Health & Info

#### GET /api/health
Check server health status.

```bash
curl http://localhost:5100/api/health
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "database": {"tables": 27, "path": "_data/recog.db"},
    "llm_configured": true,
    "available_providers": ["anthropic", "openai"]
  }
}
```

#### GET /api/info
List all available endpoints.

```bash
curl http://localhost:5100/api/info
```

---

### File Upload

#### POST /api/upload
Upload a single file for analysis.

```bash
curl -X POST http://localhost:5100/api/upload \
  -F "file=@document.pdf" \
  -F "case_id=optional-case-uuid"
```

**Supported formats:** `.txt`, `.md`, `.pdf`, `.json`, `.csv`, `.xlsx`, `.docx`, `.eml`

**Response:**
```json
{
  "success": true,
  "data": {
    "preflight_id": "pf_abc123",
    "case_id": "case_xyz789",
    "filename": "document.pdf",
    "size_bytes": 102400,
    "mime_type": "application/pdf"
  }
}
```

#### POST /api/upload/batch
Upload multiple files at once.

```bash
curl -X POST http://localhost:5100/api/upload/batch \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.txt" \
  -F "case_id=optional-case-uuid"
```

---

### Tier 0: Signal Extraction (Free)

No LLM required. Extracts emotions, entities, temporal references, and structural patterns.

#### POST /api/tier0
Run signal extraction on text.

```bash
curl -X POST http://localhost:5100/api/tier0 \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I am extremely disappointed with the service. Sarah called me yesterday about the refund.",
    "include_raw": false
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "emotions": {
      "frustration": {"count": 1, "intensity": "high"},
      "disappointment": {"count": 1, "intensity": "high"}
    },
    "entities": {
      "people": ["Sarah"],
      "organizations": [],
      "locations": []
    },
    "temporal": ["yesterday"],
    "flags": {
      "high_emotion": true,
      "contains_questions": false,
      "formal_tone": false
    },
    "summary": "High emotional content with frustration/disappointment signals..."
  }
}
```

---

### Tier 1: Insight Extraction (LLM Required)

#### POST /api/extract
Extract insights from text using LLM.

```bash
curl -X POST http://localhost:5100/api/extract \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Meeting with client revealed budget concerns...",
    "source_type": "document",
    "case_id": "optional-case-uuid",
    "provider": "anthropic"
  }'
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| text | string | Yes | Text to analyze |
| source_type | string | No | "document", "chat", "email" (default: "document") |
| case_id | string | No | Link to existing case for context |
| provider | string | No | "anthropic" or "openai" |
| save | boolean | No | Save insights to DB (default: true) |

**Response:**
```json
{
  "success": true,
  "data": {
    "insights": [
      {
        "id": "ins_abc123",
        "content": "Client expressed budget concerns during Q3 review",
        "category": "financial",
        "confidence": 0.85,
        "entities": ["client"],
        "source_span": "budget concerns"
      }
    ],
    "tier0": {
      "emotions": {"concern": {"count": 1}},
      "flags": {"high_emotion": false}
    },
    "tokens_used": 1250,
    "cached": false
  }
}
```

---

### Entities

#### GET /api/entities
List all entities.

```bash
curl "http://localhost:5100/api/entities?type=person&confirmed=true&limit=50"
```

**Query parameters:**
- `type`: Filter by type (person, organization, location)
- `confirmed`: Filter by confirmation status (true/false)
- `limit`: Max results (default: 100)
- `offset`: Pagination offset

#### GET /api/entities/{id}
Get entity details.

```bash
curl http://localhost:5100/api/entities/ent_abc123
```

#### PATCH /api/entities/{id}
Update entity (confirm, merge, add details).

```bash
curl -X PATCH http://localhost:5100/api/entities/ent_abc123 \
  -H "Content-Type: application/json" \
  -d '{"confirmed": true, "notes": "CEO of Acme Corp"}'
```

#### POST /api/entities/{id}/reject
Reject false positive entity (adds to blacklist).

```bash
curl -X POST http://localhost:5100/api/entities/ent_abc123/reject
```

#### POST /api/entities/validate
Validate entities using LLM (identify false positives).

```bash
curl -X POST http://localhost:5100/api/entities/validate \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 50}'
```

---

### Insights

#### GET /api/insights
List insights with filtering.

```bash
curl "http://localhost:5100/api/insights?category=financial&min_confidence=0.7"
```

#### GET /api/insights/{id}
Get insight details.

```bash
curl http://localhost:5100/api/insights/ins_abc123
```

#### PATCH /api/insights/{id}
Update insight status or metadata.

```bash
curl -X PATCH http://localhost:5100/api/insights/ins_abc123 \
  -H "Content-Type: application/json" \
  -d '{"status": "verified", "notes": "Confirmed by client"}'
```

---

### Synthesis (LLM Required)

#### POST /api/synth/run
Run pattern synthesis across insights.

```bash
curl -X POST http://localhost:5100/api/synth/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "auto",
    "min_cluster_size": 3,
    "max_clusters": 10
  }'
```

**Strategy options:** `auto`, `thematic`, `temporal`, `entity`

#### GET /api/synth/patterns
List synthesized patterns.

```bash
curl http://localhost:5100/api/synth/patterns
```

---

### Cases

#### GET /api/cases
List all cases.

```bash
curl http://localhost:5100/api/cases
```

#### POST /api/cases
Create a new case.

```bash
curl -X POST http://localhost:5100/api/cases \
  -H "Content-Type: application/json" \
  -d '{"name": "Project Alpha Review", "description": "Q3 document analysis"}'
```

#### GET /api/cases/{id}
Get case details.

```bash
curl http://localhost:5100/api/cases/case_abc123
```

#### GET /api/cases/{id}/documents
List documents in a case.

```bash
curl http://localhost:5100/api/cases/case_abc123/documents
```

#### GET /api/cases/{id}/findings
Get case findings.

```bash
curl http://localhost:5100/api/cases/case_abc123/findings
```

---

### Cache Management

#### GET /api/cache/stats
Get cache statistics.

```bash
curl http://localhost:5100/api/cache/stats
```

#### POST /api/cache/clear
Clear all cached responses.

```bash
curl -X POST http://localhost:5100/api/cache/clear
```

#### POST /api/cache/cleanup
Remove expired cache entries.

```bash
curl -X POST http://localhost:5100/api/cache/cleanup
```

---

### Rate Limiting

#### GET /api/rate-limit/status
Get current rate limit status.

```bash
curl http://localhost:5100/api/rate-limit/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "enabled": true,
    "key": "127.0.0.1",
    "limits": {
      "default": "60 per minute",
      "expensive": "10 per minute",
      "upload": "20 per minute"
    }
  }
}
```

---

## Common Errors

### 400 Bad Request
Invalid input or missing required fields.

```json
{
  "success": false,
  "error": "Missing required field: text",
  "data": {"error_type": "ValidationError"}
}
```

**Fix:** Check request body has all required fields.

### 413 File Too Large
Uploaded file exceeds size limit (default: 10MB).

```json
{
  "success": false,
  "error": "This file is too large (15.3MB). Maximum size is 10MB.",
  "data": {"error_type": "FileTooLargeError"}
}
```

**Fix:** Compress or split the file.

### 415 Unsupported File Type
File format not supported.

```json
{
  "success": false,
  "error": "This file type (video/mp4) is not supported.",
  "data": {"error_type": "UnsupportedFileTypeError"}
}
```

**Fix:** Convert to supported format (.txt, .pdf, .docx, etc.)

### 429 Too Many Requests
Rate limit exceeded.

```json
{
  "success": false,
  "error": "Too many requests. Please wait 45 seconds and try again.",
  "data": {"error_type": "RateLimitError", "retry_after_seconds": 45}
}
```

**Fix:** Wait for `Retry-After` header duration.

### 503 Service Unavailable
LLM provider unavailable or not configured.

```json
{
  "success": false,
  "error": "LLM not configured. Set RECOG_OPENAI_API_KEY or RECOG_ANTHROPIC_API_KEY.",
  "data": {"error_type": "LLMNotConfiguredError"}
}
```

**Fix:** Set API key environment variables.

---

## Response Format

All responses follow this structure:

```json
{
  "success": true|false,
  "data": { ... },
  "error": "Error message (only if success=false)",
  "timestamp": "2025-01-14T10:30:00.000000Z"
}
```

## Rate Limits

| Endpoint Type | Limit |
|--------------|-------|
| General | 60/minute |
| LLM Operations (extract, synth, critique) | 10/minute |
| File Upload | 20/minute |
| Health Check | 120/minute |

## Headers

**Request headers:**
- `Content-Type: application/json` for JSON bodies
- `X-Request-ID: <id>` optional request tracking

**Response headers:**
- `X-Request-ID` echoed back for tracking
- `X-RateLimit-Limit` rate limit ceiling
- `X-RateLimit-Remaining` remaining requests
- `X-RateLimit-Reset` reset timestamp
- `Retry-After` seconds until retry (on 429)

---

## Configuration

Set via environment variables:

```bash
# LLM Providers (at least one required for extraction)
RECOG_OPENAI_API_KEY=sk-...
RECOG_ANTHROPIC_API_KEY=sk-ant-...

# Server
RECOG_PORT=5100
RECOG_DATA_DIR=./_data
RECOG_MAX_FILE_SIZE_MB=10

# Logging
RECOG_LOG_LEVEL=INFO

# Caching
RECOG_CACHE_ENABLED=true
RECOG_CACHE_TTL_HOURS=24

# Rate Limiting
RECOG_RATE_LIMIT_ENABLED=true
```

Validate configuration: `python recog_cli.py config`

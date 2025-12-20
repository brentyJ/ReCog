# EhkoForge → ReCog Pipeline Audit

## Executive Summary

ReCog extraction from EhkoForge is **functionally complete** through Phase 3.

---

## PHASE STATUS

| Phase | Description | Status |
|-------|-------------|--------|
| 1.0 | Repository setup, batch migration | ✅ Complete |
| 2.0 | Universal file detection, ingestion | ✅ Complete |
| 2.5 | Tier 0 + Extraction logic | ✅ Complete |
| 2.6 | Entity registry + Preflight | ✅ Complete |
| 3.0 | Flask server + Frontend | ✅ Complete |
| 4.0 | Database insight storage | 🔲 Pending |

---

## DELIVERABLES

### Core Engine (`recog_engine/`)
- `tier0.py` - Zero-cost signal extraction
- `extraction.py` - LLM insight extraction with similarity
- `entity_registry.py` - Contact tracking with anonymisation
- `preflight.py` - Batch import workflow
- `core/` - Types, config, LLM interface, processors
- `adapters/` - Base, Memory, SQLite adapters

### Ingestion (`ingestion/`)
- Universal file detection
- Parsers: PDF, Markdown, Plaintext, Messages, JSON export

### Server (`server.py`)
- Flask REST API (15+ endpoints)
- File upload with preflight
- Entity management
- LLM extraction integration

### Frontend (`static/index.html`)
- Terminal aesthetic UI
- Drop zone file upload
- Tier 0 text analysis
- Server status display

### Database (`migrations/schema_v0_1.sql`)
- 12 tables covering full workflow

### CLI (`recog_cli.py`)
- detect, ingest, formats
- tier0 with --text and --json
- db init/check
- preflight create/scan/status

---

## API ENDPOINTS

```
GET  /api/health                    - Server health
GET  /api/info                      - API info
POST /api/detect                    - Detect file format
POST /api/upload                    - Upload + preflight
POST /api/tier0                     - Tier 0 analysis

GET  /api/preflight/<id>            - Session summary
GET  /api/preflight/<id>/items      - Session items
POST /api/preflight/<id>/filter     - Apply filters
POST /api/preflight/<id>/exclude/<item> - Exclude item
POST /api/preflight/<id>/include/<item> - Re-include
POST /api/preflight/<id>/confirm    - Confirm processing

GET  /api/entities                  - List entities
GET  /api/entities/unknown          - Unknown entities
GET  /api/entities/<id>             - Get entity
PATCH /api/entities/<id>            - Update entity
GET  /api/entities/stats            - Registry stats

POST /api/extract                   - LLM extraction
GET  /api/insights                  - List insights (pending)
```

---

## RUNNING

```bash
cd ReCog/_scripts
pip install -r requirements.txt
python recog_cli.py db init
python server.py
```

Open http://localhost:5000

---

## REMAINING (Phase 4)

1. **Insight persistence**: Store extracted insights in database
2. **Pattern detection**: Correlate insights across documents
3. **Processing queue**: Background worker for LLM tasks
4. **Export**: Markdown, JSON export of insights

---

*Last updated: Phase 3 completion*

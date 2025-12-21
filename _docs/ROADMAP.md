# ReCog Development Roadmap

## Completed Phases

### Phase 1-3 ✅
- Core engine architecture
- Tier 0 signal extraction (emotions, entities, temporal, intensity)
- Flask REST API (15+ endpoints)
- Terminal-aesthetic web UI
- File upload with preflight sessions
- Entity registry with normalisation
- Database schema (12 tables)

---

## Phase 4: LLM Integration & Insight Storage

**Goal**: Connect LLM extraction and persist insights to database

### 4.1 LLM Provider System ✅
```
Files created:
- recog_engine/core/providers/__init__.py
- recog_engine/core/providers/openai_provider.py
- recog_engine/core/providers/anthropic_provider.py  
- recog_engine/core/providers/factory.py
- .env.example
- .env (gitignored)
```

Completed:
- [x] LLMProvider abstract interface (llm.py)
- [x] OpenAI provider with gpt-4o-mini support
- [x] Anthropic provider with Claude Sonnet support
- [x] Provider factory with auto-detection from env vars
- [x] JSON generation methods on both providers
- [x] Token/usage tracking per response
- [x] Environment-based configuration (.env support)
- [x] server.py updated to use provider system
- [x] Health endpoint shows available providers

### 4.2 LLM Extraction Integration
```
Files modified:
- server.py: /api/extract uses provider factory
```

Completed:
- [x] Test extraction with real OpenAI API key
- [x] Token/cost tracking per extraction call
- [x] Provider selection via request body

Pending:
- [ ] Store ExtractedInsight objects in `insights` table
- [ ] Store source links in `insight_sources` table
- [ ] Track extraction history in `insight_history` table

### 4.2 Insight Database Layer
```
New file: recog_engine/insight_store.py
```

Tasks:
- [ ] InsightStore class with CRUD operations
- [ ] `save_insight(insight)` - insert or update
- [ ] `get_insight(id)` - retrieve by ID
- [ ] `list_insights(filters)` - with status, significance, date filters
- [ ] `search_insights(query)` - full-text search
- [ ] Similarity check before insert (merge duplicates)

### 4.3 Processing Queue Worker
```
New file: worker.py
```

Tasks:
- [ ] Background worker that processes queue
- [ ] Pull items from `processing_queue` table
- [ ] Run LLM extraction on each
- [ ] Update status (pending → processing → complete/failed)
- [ ] Rate limiting / cost caps

### 4.4 API Endpoints
```
Modify: server.py
```

New endpoints:
- [ ] `GET /api/insights` - list with filters
- [ ] `GET /api/insights/<id>` - get single insight
- [ ] `PATCH /api/insights/<id>` - update status/significance
- [ ] `DELETE /api/insights/<id>` - soft delete
- [ ] `GET /api/queue` - view processing queue
- [ ] `POST /api/queue/<id>/retry` - retry failed item

### 4.5 Environment Setup
```
.env.example file
```

```env
RECOG_LLM_API_KEY=sk-...
RECOG_LLM_MODEL=gpt-4o-mini
RECOG_LLM_MAX_TOKENS=2000
RECOG_COST_LIMIT_CENTS=100
```

**Deliverable**: Working LLM extraction with database persistence

---

## Phase 5: Preflight UI & Entity Management

**Goal**: Full workflow UI for reviewing imports and managing entities

### 5.1 Preflight Review Page
```
New file: static/preflight.html (or add to index.html)
```

UI Components:
- [ ] Session summary header (words, items, cost estimate)
- [ ] Item list with checkboxes (include/exclude)
- [ ] Filter controls (min words, date range, keywords)
- [ ] Per-item preview (title, word count, flags, entities)
- [ ] "Confirm & Process" button with cost warning
- [ ] Progress indicator during processing

### 5.2 Entity Management Page
```
New file: static/entities.html (or add to index.html)
```

UI Components:
- [ ] Unknown entities queue (needs identification)
- [ ] Entity card: raw value, occurrence count, sources
- [ ] Quick actions: "This is [name]", "Skip", "Anonymise"
- [ ] Relationship dropdown (family, work, medical, etc.)
- [ ] Bulk confirm/skip buttons
- [ ] Search/filter existing entities

### 5.3 Entity API Enhancements
```
Modify: server.py
```

- [ ] `POST /api/entities/bulk` - update multiple at once
- [ ] `GET /api/entities/<id>/occurrences` - where entity appears
- [ ] `POST /api/entities/merge` - combine duplicates

### 5.4 Navigation & Layout
```
Modify: static/index.html
```

- [ ] Tab navigation: Upload | Preflight | Entities | Insights
- [ ] Session state persistence (localStorage)
- [ ] Mobile-responsive layout
- [ ] Keyboard shortcuts (Ctrl+Enter to analyse)

**Deliverable**: Complete preflight workflow from upload to processing

---

## Phase 6: Parser Improvements & Production Polish

**Goal**: Handle real-world data formats, harden for production

### 6.1 New Parsers
```
New files in ingestion/parsers/
```

- [ ] `xml_sms.py` - Android/iOS SMS backup XML
- [ ] `chatgpt.py` - ChatGPT conversations.json export
- [ ] `whatsapp.py` - WhatsApp chat export (.txt)
- [ ] `email_mbox.py` - MBOX email archives
- [ ] `xlsx.py` - Excel spreadsheets (openpyxl)

### 6.2 Entity Extraction Improvements
```
Modify: recog_engine/tier0.py
```

- [ ] Full name extraction ("Dr. Smith" not just "Dr")
- [ ] Organisation detection
- [ ] Location/address detection
- [ ] Date/time normalisation
- [ ] Currency/amount detection

### 6.3 Error Handling & Logging
```
Modify: server.py, all engine files
```

- [ ] Structured logging with levels
- [ ] Request ID tracking
- [ ] Graceful error responses
- [ ] File upload validation (size, type, malware scan?)
- [ ] Rate limiting per IP

### 6.4 Testing
```
New directory: tests/
```

- [ ] `test_tier0.py` - signal extraction unit tests
- [ ] `test_extraction.py` - LLM prompt/parse tests
- [ ] `test_parsers.py` - each parser with sample files
- [ ] `test_api.py` - endpoint integration tests
- [ ] Sample test files in `tests/fixtures/`

### 6.5 Documentation
```
Update: README.md, new files in _docs/
```

- [ ] API documentation (OpenAPI/Swagger?)
- [ ] Self-hosting guide
- [ ] Parser development guide
- [ ] Configuration reference

### 6.6 Deployment Prep
```
New files in project root
```

- [ ] `Dockerfile` - containerised deployment
- [ ] `docker-compose.yml` - with volume mounts
- [ ] `fly.toml` or `railway.json` - cloud deploy config
- [ ] Production WSGI setup (gunicorn)
- [ ] HTTPS/SSL configuration notes

**Deliverable**: Production-ready ReCog for ehkoforge.ai launch

---

## Quick Reference

| Phase | Focus | Key Deliverable |
|-------|-------|-----------------|
| 4 | LLM + Database | Insights stored and queryable |
| 5 | UI Workflow | Full upload → review → process flow |
| 6 | Polish | Production-ready with real parsers |

## Estimated Effort

- **Phase 4**: 1-2 sessions (LLM integration, database layer)
- **Phase 5**: 2-3 sessions (UI heavy)
- **Phase 6**: 2-4 sessions (many small tasks)

Total: ~6-9 sessions to production-ready MVP

---

*Last updated: Phase 4.1 LLM Provider System complete - 21 Dec 2025*

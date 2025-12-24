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

## Phase 4: LLM Integration & Insight Storage ✅

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

### 4.2 LLM Extraction Integration ✅
```
Files modified:
- server.py: /api/extract uses provider factory
```

Completed:
- [x] Test extraction with real OpenAI API key
- [x] Token/cost tracking per extraction call
- [x] Provider selection via request body
- [x] Store ExtractedInsight objects in `insights` table
- [x] Store source links in `insight_sources` table
- [x] Track extraction history in `insight_history` table

### 4.3 Insight Database Layer ✅
```
New file: recog_engine/insight_store.py
```

Completed:
- [x] InsightStore class with CRUD operations
- [x] `save_insight(insight)` - insert or update with similarity check
- [x] `save_insights_batch(insights)` - batch save with dedup
- [x] `get_insight(id)` - retrieve by ID with sources/history
- [x] `list_insights(filters)` - with status, significance, type filters
- [x] `update_insight()` - update status/significance/themes
- [x] `delete_insight()` - soft delete (sets rejected)
- [x] `get_sources()` / `get_history()` - audit trail
- [x] `get_stats()` - insight statistics
- [x] Similarity check before insert (merge duplicates)

### 4.4 Processing Queue Worker ✅
```
New file: worker.py
```

Completed:
- [x] Background worker that polls queue
- [x] Pull items from `processing_queue` table
- [x] Run LLM extraction on each
- [x] Update status (pending → processing → complete/failed)
- [x] Rate limiting / cost caps
- [x] Graceful shutdown on SIGINT/SIGTERM

### 4.5 API Endpoints ✅
```
Modify: server.py
```

Completed:
- [x] `GET /api/insights` - list with filters (status, significance, type, pagination)
- [x] `GET /api/insights/<id>` - get single insight with sources/history
- [x] `PATCH /api/insights/<id>` - update status/significance/themes/patterns
- [x] `DELETE /api/insights/<id>` - soft delete (?hard=true for permanent)
- [x] `GET /api/insights/stats` - insight statistics
- [x] `GET /api/queue` - list queue items with filters
- [x] `GET /api/queue/stats` - queue statistics
- [x] `GET /api/queue/<id>` - get single queue item
- [x] `POST /api/queue/<id>/retry` - retry failed item
- [x] `DELETE /api/queue/<id>` - remove from queue
- [x] `POST /api/queue/clear` - clear failed/complete items

### 4.6 Environment Setup
```
.env.example file
```

```env
RECOG_LLM_API_KEY=sk-...
RECOG_LLM_MODEL=gpt-4o-mini
RECOG_LLM_MAX_TOKENS=2000
RECOG_COST_LIMIT_CENTS=100
```

**Deliverable**: Working LLM extraction with database persistence ✅ COMPLETE

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

## Phase 6: Synth Engine (Pattern Synthesis) ✅

**Goal**: Transform isolated insights into higher-order patterns through recursive synthesis

### 6.1 Core Synth Engine ✅
```
New file: recog_engine/synth.py
```

Completed:
- [x] ClusterStrategy enum (thematic, temporal, entity, emotional, auto)
- [x] InsightCluster dataclass with metadata
- [x] SynthesizedPattern dataclass with scoring
- [x] `cluster_by_theme()` - group by shared themes
- [x] `cluster_by_time()` - group by time periods (month/quarter)
- [x] `cluster_by_entity()` - group by mentioned people
- [x] `auto_cluster()` - multi-strategy with deduplication
- [x] SynthEngine class with full workflow

### 6.2 Pattern Synthesis ✅
```
Files: recog_engine/synth.py
```

Completed:
- [x] SYNTH_SYSTEM_PROMPT - pattern analyst persona
- [x] SYNTH_CLUSTER_PROMPT - structured JSON output
- [x] `build_synth_prompt()` - inject cluster context
- [x] `parse_synth_response()` - JSON to SynthesizedPattern
- [x] `synthesize_cluster()` - single cluster synthesis
- [x] `run_synthesis()` - full cycle (cluster → synth → store)

### 6.3 Database Schema ✅
```
New file: migrations/migration_v0_2_synth.sql
```

Tables added:
- [x] `insight_clusters` - groups awaiting synthesis
- [x] `pattern_details` - extended pattern metadata

### 6.4 API Endpoints ✅
```
Modify: server.py (v0.4.0)
```

Completed:
- [x] `POST /api/synth/clusters` - create clusters from insights
- [x] `GET /api/synth/clusters` - list pending clusters
- [x] `POST /api/synth/run` - run full synthesis cycle
- [x] `GET /api/synth/patterns` - list patterns with filters
- [x] `GET /api/synth/patterns/<id>` - get single pattern
- [x] `PATCH /api/synth/patterns/<id>` - update status
- [x] `GET /api/synth/stats` - synth statistics

### 6.5 Worker Integration ✅
```
Modify: worker.py
```

Completed:
- [x] `process_synthesize_job()` - handle 'synthesize' operations
- [x] Support for auto clustering and specific cluster synthesis
- [x] SynthEngine initialization in worker

**Deliverable**: REDUCE layer - insights → patterns ✅ COMPLETE

---

## Phase 7: Entity Graph Evolution

**Goal**: Transform flat entity registry into relationship graph

### 7.1 Entity Relationships
```
Modify: entity_registry.py → entity_graph.py
```

- [ ] Relationship types (manages, works_with, mentioned_with)
- [ ] Sentiment tracking per entity
- [ ] Co-occurrence detection
- [ ] Entity timeline (first/last seen, frequency)

### 7.2 Graph Queries
```
New endpoints in server.py
```

- [ ] `GET /api/entities/<id>/network` - related entities
- [ ] `GET /api/entities/<id>/timeline` - occurrence over time
- [ ] `GET /api/entities/graph` - full network visualization data

### 7.3 Integration with Synth
```
Modify: synth.py
```

- [ ] Use entity graph for smarter clustering
- [ ] Relational pattern detection ("X always appears with Y")
- [ ] Entity-centric pattern views

**Deliverable**: Rich entity relationships enabling deeper pattern detection

---

## Phase 8: Critique & Validation Layer

**Goal**: Self-correction mechanism to prevent error propagation

### 8.1 Critique Engine
```
New file: recog_engine/critique.py
```

- [ ] Citation validation (does excerpt support claim?)
- [ ] Confidence calibration (is significance justified?)
- [ ] Contradiction detection (conflicts with existing patterns?)
- [ ] Hallucination filter (grounded vs fabricated?)

### 8.2 Reflexion Loop
```
Modify: extraction.py, synth.py
```

- [ ] Extract → Critique → (pass/fail) → Refine → Store
- [ ] Track critique history for improvement
- [ ] Configurable strictness levels

**Deliverable**: Quality assurance preventing recursive error amplification

---

## Phase 9: Parser Improvements & Production Polish

**Goal**: Handle real-world data formats, harden for production

### 9.1 New Parsers
```
New files in ingestion/parsers/
```

- [ ] `xml_sms.py` - Android/iOS SMS backup XML
- [ ] `chatgpt.py` - ChatGPT conversations.json export
- [ ] `whatsapp.py` - WhatsApp chat export (.txt)
- [ ] `email_mbox.py` - MBOX email archives
- [ ] `xlsx.py` - Excel spreadsheets (openpyxl)

### 9.2 Entity Extraction Improvements
```
Modify: recog_engine/tier0.py
```

- [x] Fix false positives ("The", "This", common verbs) - v0.2
- [ ] Full name extraction ("Dr. Smith" not just "Dr")
- [ ] Organisation detection
- [ ] Location/address detection
- [ ] Date/time normalisation
- [ ] Currency/amount detection

### 9.3 Error Handling & Logging
```
Modify: server.py, all engine files
```

- [ ] Structured logging with levels
- [ ] Request ID tracking
- [ ] Graceful error responses
- [ ] File upload validation (size, type, malware scan?)
- [ ] Rate limiting per IP

### 9.4 Testing
```
New directory: tests/
```

- [x] `test_tier0.py` - signal extraction, entity false positive regression
- [ ] `test_extraction.py` - LLM prompt/parse tests
- [ ] `test_synth.py` - clustering and synthesis tests
- [ ] `test_parsers.py` - each parser with sample files
- [ ] `test_api.py` - endpoint integration tests
- [ ] Sample test files in `tests/fixtures/`

### 9.5 Documentation
```
Update: README.md, new files in _docs/
```

- [ ] API documentation (OpenAPI/Swagger?)
- [ ] Self-hosting guide
- [ ] Parser development guide
- [ ] Configuration reference

### 9.6 Deployment Prep
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
| 4 ✅ | LLM + Database | Insights stored and queryable |
| 5 | UI Workflow | Full upload → review → process flow |
| 6 ✅ | Synth Engine | Patterns from insight clusters |
| 7 | Entity Graph | Relationship-aware analysis |
| 8 | Critique Layer | Self-correcting quality assurance |
| 9 | Polish | Production-ready with real parsers |

## Architecture (Post-Phase 6)

```
┌─────────────────────────────────────────────────────────────────┐
│                        LAYER 0: DATA                            │
│  Ingestion → Adaptive Chunking → Tier 0 Signals → Entity Extract│
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 1: MAP (Extraction) ✅                 │
│  Per-chunk LLM analysis → Structured InsightJSON                │
│  (extraction.py + worker.py) ← GPT-4o-mini                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 LAYER 2: REDUCE (Synthesis) ✅                  │
│  Cluster insights → Cross-reference → Patterns                  │
│  (synth.py) ← Claude Sonnet                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                LAYER 3: CRITIQUE (Validation)                   │
│  Validate claims → Confidence calibration → Reflexion loop      │
│  (critique.py) ← Phase 8                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 4: META (Higher-Order)                       │
│  Patterns → Life themes → Ehko witness output                   │
│  (meta_analysis.py) ← Future                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Estimated Effort

- **Phase 4**: 1-2 sessions (LLM integration, database layer) ✅
- **Phase 5**: 2-3 sessions (UI heavy)
- **Phase 6**: 1 session (Synth Engine) ✅
- **Phase 7**: 1-2 sessions (Entity graph)
- **Phase 8**: 1-2 sessions (Critique layer)
- **Phase 9**: 2-4 sessions (many small tasks)

Total: ~8-14 sessions to production-ready MVP

---

*Last updated: Phase 6 Synth Engine complete - 24 Dec 2025*

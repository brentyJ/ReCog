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

## Phase 5: Preflight UI & Entity Management ✅

**Goal**: Full workflow UI for reviewing imports and managing entities

### 5.1 Preflight Review Page ✅
```
Modified: static/index.html
```

Completed:
- [x] Session summary header (words, items, cost estimate)
- [x] Item list with checkboxes (include/exclude)
- [x] Per-item preview (title, word count, flags, entities)
- [x] "Confirm & Process" button with cost warning
- [x] Unknown entity warning before processing
- [x] Session persistence in localStorage

### 5.2 Entity Management Page ✅
```
Modified: static/index.html
```

Completed:
- [x] Unknown entities queue (needs identification)
- [x] Entity card: raw value, occurrence count, type
- [x] Quick actions modal: Identify, Skip
- [x] Relationship dropdown (family, work, medical, etc.)
- [x] Anonymise option with placeholder name
- [x] Entity registry list (confirmed entities)
- [x] Entity statistics display

### 5.3 Insights Browser ✅
```
Modified: static/index.html
```

Completed:
- [x] Insight list with significance scores
- [x] Filter by status (raw, refined, surfaced)
- [x] Filter by minimum significance
- [x] Filter by insight type
- [x] Excerpt preview with themes
- [x] Insight statistics display

### 5.4 Patterns Browser ✅
```
Modified: static/index.html
```

Completed:
- [x] Pattern list with strength bars
- [x] Run synthesis controls (strategy, cluster size)
- [x] Pattern type and status display
- [x] Entities involved display
- [x] Synthesis statistics

### 5.5 Navigation & Layout ✅
```
Modified: static/index.html
```

Completed:
- [x] Tab navigation: Analyse | Upload | Preflight | Entities | Insights | Patterns
- [x] Session state persistence (localStorage)
- [x] Badge counts on nav items
- [x] Keyboard shortcuts (Ctrl+Enter to analyse, Escape to close modal)
- [x] Modal system for entity editing
- [x] Loading states and error handling
- [x] Version updated to v0.6.0

**Deliverable**: Complete preflight workflow from upload to processing ✅ COMPLETE

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

## Phase 7: Entity Graph Evolution ✅

**Goal**: Transform flat entity registry into relationship graph

### 7.1 Entity Graph Core ✅
```
New file: recog_engine/entity_graph.py
```

Completed:
- [x] EntityGraph class extending EntityRegistry
- [x] RelationshipType enum (manages, works_with, family_of, etc.)
- [x] EntityRelationship dataclass with strength scoring
- [x] EntitySentiment dataclass for tracking over time
- [x] CoOccurrence dataclass for entity pairs
- [x] EntityNetwork dataclass for graph queries

### 7.2 Relationship Management ✅
```
Methods in EntityGraph
```

Completed:
- [x] `add_relationship()` - create/update relationship with strength
- [x] `get_relationships()` - query by direction, type, min_strength
- [x] `remove_relationship()` - delete relationship
- [x] Bidirectional relationship support
- [x] Relationship strengthening on repeated observations

### 7.3 Sentiment Tracking ✅
```
Methods in EntityGraph
```

Completed:
- [x] `record_sentiment()` - store sentiment from source
- [x] `get_sentiment_history()` - timeline of sentiment records
- [x] `get_sentiment_summary()` - aggregated stats (avg, trend)
- [x] Automatic label inference (positive/negative/neutral/mixed)

### 7.4 Co-occurrence Detection ✅
```
Methods in EntityGraph
```

Completed:
- [x] `record_co_occurrence()` - track entities appearing together
- [x] `get_co_occurrences()` - find frequently co-occurring entities
- [x] Pairwise tracking with source references

### 7.5 Graph Queries ✅
```
Methods in EntityGraph
```

Completed:
- [x] `get_network()` - relationship network around entity (configurable depth)
- [x] `get_timeline()` - chronological entity events
- [x] `find_path()` - BFS shortest path between entities
- [x] `get_graph_stats()` - comprehensive statistics
- [x] `process_insight_entities()` - auto-register from insights

### 7.6 Database Schema ✅
```
New file: migrations/migration_v0_3_entity_graph.sql
```

Tables added:
- [x] `entity_relationships` - links between entities
- [x] `entity_sentiment` - sentiment tracking over time
- [x] `entity_co_occurrences` - co-occurrence pairs
- [x] `entity_insight_links` - entity → insight references

### 7.7 API Endpoints ✅
```
Modify: server.py (v0.5.0)
```

Completed:
- [x] `GET /api/entities/<id>/relationships` - entity relationships
- [x] `POST /api/entities/<id>/relationships` - add relationship
- [x] `GET /api/entities/<id>/network` - relationship network
- [x] `GET /api/entities/<id>/timeline` - entity events timeline
- [x] `GET /api/entities/<id>/sentiment` - sentiment summary + history
- [x] `POST /api/entities/<id>/sentiment` - record sentiment
- [x] `GET /api/entities/<a>/path/<b>` - find shortest path
- [x] `GET /api/entities/graph/stats` - graph statistics
- [x] `GET /api/relationships` - list all relationships
- [x] `DELETE /api/relationships/<id>` - remove relationship
- [x] `GET /api/relationships/types` - list relationship types

### 7.8 Synth Integration ✅
```
Modify: server.py, synth.py
```

Completed:
- [x] SynthEngine now uses EntityGraph instead of EntityRegistry
- [x] `cluster_by_entity()` leverages graph for smarter grouping

**Deliverable**: Rich entity relationships enabling deeper pattern detection ✅ COMPLETE

---

## Phase 8: Critique & Validation Layer ✅

**Goal**: Self-correction mechanism to prevent error propagation

### 8.1 Critique Engine Core ✅
```
New file: recog_engine/critique.py
```

Completed:
- [x] CritiqueEngine class with configurable strictness
- [x] CritiqueResult enum (pass, fail, warn, refine)
- [x] CritiqueType enum (citation, confidence, contradiction, grounding, coherence)
- [x] StrictnessLevel enum (lenient, standard, strict)
- [x] CritiqueCheck dataclass for individual check results
- [x] CritiqueReport dataclass with overall verdict

### 8.2 Validation Checks ✅
```
Methods in CritiqueEngine
```

Completed:
- [x] Citation validation (does excerpt support claim?)
- [x] Confidence calibration (is significance justified?)
- [x] Coherence check (internal consistency, themes match content)
- [x] Grounding verification (evidence-based vs fabricated)
- [x] Synthesis check for patterns (genuine vs forced connection)
- [x] Contradiction check for patterns

### 8.3 Reflexion Loop ✅
```
Methods in CritiqueEngine
```

Completed:
- [x] `critique_with_refinement()` - automatic refinement loop
- [x] `_llm_refine_insight()` - LLM-powered insight improvement
- [x] Configurable max refinement iterations
- [x] Refinement history tracking in database

### 8.4 Prompts & Response Parsing ✅
```
Constants and methods in critique.py
```

Completed:
- [x] CRITIQUE_SYSTEM_PROMPT - fact-checker persona
- [x] INSIGHT_CRITIQUE_PROMPT - structured validation checks
- [x] PATTERN_CRITIQUE_PROMPT - pattern-specific validation
- [x] REFINEMENT_PROMPT - guided improvement
- [x] `parse_critique_response()` - JSON to CritiqueReport

### 8.5 Database Schema ✅
```
New file: migrations/migration_v0_4_critique.sql
```

Tables added:
- [x] `critique_reports` - validation results with checks
- [x] `refinement_history` - track refinement iterations

### 8.6 API Endpoints ✅
```
Modify: server.py (v0.6.0)
```

Completed:
- [x] `POST /api/critique/insight` - validate an insight
- [x] `POST /api/critique/pattern` - validate a pattern
- [x] `POST /api/critique/refine` - critique with auto-refinement loop
- [x] `GET /api/critique/<id>` - get critique report
- [x] `GET /api/critique/for/<type>/<id>` - critiques for target
- [x] `GET /api/critique` - list critiques with filters
- [x] `GET /api/critique/stats` - critique statistics
- [x] `GET /api/critique/strictness` - current strictness level
- [x] `POST /api/critique/strictness` - set strictness level

### 8.7 Module Integration ✅
```
Modify: recog_engine/__init__.py
```

Exports added:
- [x] CritiqueResult, CritiqueType, StrictnessLevel enums
- [x] CritiqueCheck, CritiqueReport dataclasses
- [x] CritiqueEngine class
- [x] init_critique_engine, get_critique_engine module functions

**Deliverable**: Quality gate preventing hallucination propagation ✅ COMPLETE

---

## Phase 9: Parser Improvements & Production Polish (In Progress)

**Goal**: Handle real-world data formats, harden for production

### 9.1 New Parsers ✅
```
Files in ingestion/parsers/
```

- [x] `messages.py` - WhatsApp, SMS XML, generic chat (unified)
- [x] `json_export.py` - ChatGPT conversations.json export
- [x] `excel.py` - Excel spreadsheets (.xlsx, .xls, .xlsm via openpyxl)
- [ ] `email_mbox.py` - MBOX email archives (future)

### 9.2 Entity Context Injection ✅
```
Modify: server.py /api/extract endpoint
```

Completed:
- [x] Resolve Tier 0 entities against registry during extraction
- [x] Inject resolved entity context into LLM prompts (display names, relationships)
- [x] Return entity_resolution in API response (resolved vs unknown counts)
- [x] Support anonymization (use placeholder_name if anonymise_in_prompts=True)
- [x] Updated endpoint docstring documenting entity_resolution field

### 9.3 Entity Extraction Improvements
```
Modify: recog_engine/tier0.py
```

- [x] Fix false positives ("The", "This", common verbs) - v0.2
- [ ] Full name extraction ("Dr. Smith" not just "Dr")
- [ ] Organisation detection
- [ ] Location/address detection
- [ ] Date/time normalisation
- [ ] Currency/amount detection

### 9.4 Error Handling & Logging ✅
```
New file: recog_engine/logging_utils.py
```

- [x] Structured logging with levels (JSON + text output)
- [x] Request ID tracking (context vars)
- [x] Timer context manager for performance
- [x] log_request decorator for endpoints
- [ ] Rate limiting per IP (future)

### 9.5 Testing ✅
```
Directory: tests/
```

- [x] `test_tier0.py` - signal extraction, entity false positive regression
- [x] `test_extraction.py` - LLM prompt/parse tests
- [x] `test_synth.py` - clustering and synthesis tests
- [x] `test_parsers.py` - each parser with sample files
- [x] `test_api.py` - endpoint integration tests (pytest)
- [ ] Sample test files in `tests/fixtures/`

### 9.6 Documentation
```
Update: README.md, new files in _docs/
```

- [ ] API documentation (OpenAPI/Swagger?)
- [ ] Self-hosting guide
- [ ] Parser development guide
- [ ] Configuration reference

### 9.7 Deployment Prep ✅
```
New files in project root
```

- [x] `Dockerfile` - multi-stage build, gunicorn
- [x] `docker-compose.yml` - with volume mounts, worker service
- [x] `requirements.txt` - updated with gunicorn, pytest, openpyxl
- [ ] `fly.toml` or `railway.json` - cloud deploy config
- [ ] HTTPS/SSL configuration notes

**Deliverable**: Production-ready ReCog for ehkoforge.ai launch

---

## Quick Reference

| Phase | Focus | Key Deliverable |
|-------|-------|-----------------|
| 4 ✅ | LLM + Database | Insights stored and queryable |
| 5 ✅ | UI Workflow | Full upload → review → process flow |
| 6 ✅ | Synth Engine | Patterns from insight clusters |
| 7 ✅ | Entity Graph | Relationship-aware analysis |
| 8 ✅ | Critique Layer | Self-correcting quality assurance |
| 9 ⏳ | Polish | Production-ready with real parsers |

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
│              LAYER 3: CRITIQUE (Validation) ✅                  │
│  Validate claims → Confidence calibration → Reflexion loop      │
│  (critique.py) ← GPT-4o-mini / Claude                           │
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
- **Phase 5**: 1 session (UI workflow) ✅
- **Phase 6**: 1 session (Synth Engine) ✅
- **Phase 7**: 1-2 sessions (Entity graph)
- **Phase 8**: 1-2 sessions (Critique layer)
- **Phase 9**: 2-4 sessions (many small tasks)

Total: ~8-14 sessions to production-ready MVP

---

*Last updated: Phase 9.2 Entity Context Injection complete - 25 Dec 2025*

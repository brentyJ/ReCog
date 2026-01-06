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

## Phase 10: React UI Modernization ✅

**Goal**: Professional React + shadcn/ui interface with consistent design system

### 10.1 React Foundation ✅
```
Location: C:\EhkoDev\recog-ui
```

Completed:
- [x] React 18 + Vite setup
- [x] shadcn/ui component library integration
- [x] Tailwind CSS with holographic theme
- [x] Sidebar navigation with all 6 pages
- [x] Logo and branding preserved
- [x] Server health check integration
- [x] Port 3101 with API proxy to :5100

### 10.2 Page Implementation ✅
```
New components in src/components/pages/
```

Completed:
- [x] Signal Extraction page - Tier 0 analysis form with emotion/entity/temporal extraction
- [x] Upload page - drag/drop file handler with format detection, case selection
- [x] Preflight page - review workflow with item selection, case context banner
- [x] Entities page - entity management with identification modal and anonymization
- [x] Insights page - browse insights with filters, findings promotion
- [x] Patterns page - synthesis view with pattern cards and cluster controls
- [x] Cases page - case dashboard, case detail, findings management, timeline

### 10.3 Component Library ✅
```
Components in src/components/ui/
```

Completed:
- [x] Button (variants: default, secondary, destructive, outline, ghost)
- [x] Card (with header, content, footer)
- [x] Input (text input)
- [x] Textarea (monospace)
- [x] Label (form labels)
- [x] Dialog (modals)
- [x] Select/Dropdown (for filters) - Radix UI primitive
- [x] Badge (for status indicators)
- [x] Tabs (for multi-section pages) - Radix UI primitive

To add (Phase 10.4):
- [ ] Table (for data grids)
- [ ] Toast (notifications)
- [ ] Progress (for processing status)

### 10.4 API Integration ✅
```
Utility functions in src/lib/api.js
```

Completed:
- [x] Complete API client with all 40+ endpoints
- [x] Error handling with custom APIError class
- [x] Loading states in all page components
- [x] Type-safe request/response handling

### 10.5 Theme Customization ✅
```
Modify: tailwind.config.js, src/index.css
```

Completed:
- [x] Holographic color palette (deep void + blue/orange)
- [x] Custom scrollbar styling
- [x] Glow effects utilities
- [x] Design token CSS variables
- [x] Consistent component theming

**Deliverable**: Modern, maintainable UI with consistent design system ✅ COMPLETE

---

## Phase 10.5: Case Architecture Backend ✅

**Goal**: Transform ReCog from analysis tool → document intelligence platform with case-centric workflows

### 10.5.1 Database Schema ✅
```
New file: migrations/migration_v0_5_cases.sql
```

Tables added:
- [x] `cases` - case containers with title, context, focus_areas, status
- [x] `case_documents` - links documents to cases
- [x] `findings` - validated insights promoted from raw insights
- [x] `case_timeline` - auto-generated case evolution log
- [x] FK columns: `insights.case_id`, `patterns.case_id`, `preflight_sessions.case_id`

### 10.5.2 Store Classes ✅
```
New files in recog_engine/
```

Completed:
- [x] `case_store.py` - CaseStore class with full CRUD
- [x] `findings_store.py` - FindingsStore for insight promotion
- [x] `timeline_store.py` - TimelineStore for event logging
- [x] CaseContext, CaseDocument, Finding, TimelineEvent dataclasses
- [x] Auto-promotion logic for high-confidence insights
- [x] Statistics and summary methods

### 10.5.3 Context Injection ✅
```
Modify: recog_engine/extraction.py, server.py
```

Completed:
- [x] CASE_CONTEXT_TEMPLATE for prompt injection
- [x] `build_extraction_prompt()` accepts `case_context` parameter
- [x] `/api/extract` accepts `case_id` parameter
- [x] Case context fetched and injected into LLM prompts
- [x] Timeline event logged when insights extracted
- [x] `insight_store.save_insights_batch()` accepts `case_id`

### 10.5.4 API Endpoints ✅
```
Modify: server.py (v0.7.0)
```

Case Management:
- [x] `POST /api/cases` - create new case
- [x] `GET /api/cases` - list cases with filters
- [x] `GET /api/cases/<id>` - get case details
- [x] `PATCH /api/cases/<id>` - update case
- [x] `DELETE /api/cases/<id>` - delete with cascade
- [x] `GET /api/cases/<id>/documents` - list case documents
- [x] `POST /api/cases/<id>/documents` - add document to case
- [x] `DELETE /api/cases/<id>/documents/<doc_id>` - remove document
- [x] `GET /api/cases/<id>/stats` - case statistics
- [x] `GET /api/cases/<id>/context` - get prompt injection context

Findings Management:
- [x] `POST /api/findings` - promote insight to finding
- [x] `GET /api/cases/<id>/findings` - list case findings
- [x] `GET /api/findings/<id>` - get finding details
- [x] `PATCH /api/findings/<id>` - update status/tags
- [x] `POST /api/findings/<id>/note` - add annotation
- [x] `DELETE /api/findings/<id>` - demote finding
- [x] `POST /api/cases/<id>/findings/auto-promote` - batch promotion
- [x] `GET /api/cases/<id>/findings/stats` - findings statistics

Timeline Management:
- [x] `GET /api/cases/<id>/timeline` - timeline with filters
- [x] `POST /api/cases/<id>/timeline` - add human annotation
- [x] `POST /api/timeline/<id>/annotate` - annotate existing event
- [x] `GET /api/cases/<id>/timeline/summary` - timeline stats
- [x] `GET /api/cases/<id>/timeline/daily` - daily event counts
- [x] `GET /api/cases/<id>/activity` - recent activity

**Deliverable**: Complete case-centric backend for document intelligence ✅ COMPLETE

---

## Phase 10.6: Code Quality & Developer Experience ✅

**Goal**: Improve test coverage, code organization, and developer tooling

**Session Date**: 2026-01-06 (Claude Code CLI)

### 10.6.1 Test Coverage ✅
```
New file: _scripts/tests/test_cases.py
```

Completed:
- [x] TestCaseStore - 21 tests for case CRUD operations
- [x] TestFindingsStore - 14 tests for findings management
- [x] TestTimelineStore - 14 tests for timeline events
- [x] TestCaseIntegration - 4 integration tests
- [x] Standalone runner for environments without pytest
- [x] Total: 53 new tests covering Case architecture

### 10.6.2 Database Indexes ✅
```
New file: migrations/migration_v0_7_missing_indexes.sql
```

Indexes added:
- [x] FK indexes: `merged_into_id`, `critique_id`, `source_cluster_id`
- [x] Timestamp indexes: `created_at`, `queued_at`, `ingested_at`, `last_seen_at`
- [x] Total: 10 new indexes for query performance

### 10.6.3 UI Component Refactoring ✅
```
New files in _ui/src/components/ui/
```

Shared components extracted:
- [x] `loading-state.jsx` - Spinner with message, 3 size variants
- [x] `empty-state.jsx` - Icon, title, description, optional action
- [x] `status-badge.jsx` - 15+ predefined status color schemes
- [x] `stat-card.jsx` - StatCard + StatGrid for metrics display

Pages updated:
- [x] InsightsPage, PatternsPage, EntitiesPage - StatGrid, LoadingState, EmptyState
- [x] PreflightPage - LoadingState, EmptyState
- [x] CasesPage - LoadingState, EmptyState, StatusBadge
- [x] Net reduction: 62 lines (-166, +104)

### 10.6.4 API Consistency Review ✅
```
Review: server.py
```

Completed:
- [x] Verified all 70+ endpoints use `api_response()` wrapper
- [x] Confirmed consistent format: `{success, data, error, timestamp}`
- [x] No fixes needed - architecture already enforces consistency

### 10.6.5 Code Comment Audit ✅
```
Search: TODO, FIXME, HACK comments
```

Completed:
- [x] Found 2 valid TODOs (synthesis cost tracking, correlation feature)
- [x] Both are legitimate future work items, not outdated
- [x] Codebase is clean - no stale comments to remove

**Deliverable**: Improved test coverage, query performance, and code organization ✅ COMPLETE

---

## Phase 10.7: UI Navigation & State Persistence ✅

**Goal**: Improve UI navigation, state persistence, and batch operations

**Session Date**: 2026-01-06 (Claude Code CLI)

### 10.7.1 Hash-Based Routing ✅
```
Modify: _ui/src/App.jsx
```

Completed:
- [x] Hash routing for all pages (#upload, #preflight/123, etc.)
- [x] Listen for hashchange events for browser back/forward
- [x] Default to analyse page when hash empty or invalid
- [x] Sidebar navigation updates URL hash

### 10.7.2 Upload Page Improvements ✅
```
Modify: _ui/src/components/pages/UploadPage.jsx
```

Completed:
- [x] Checkboxes to select uploaded files
- [x] Select All / Deselect All buttons
- [x] "Review Selected" button for batch preflight review
- [x] Clear button to remove upload history
- [x] Persist uploads to localStorage (survives navigation)
- [x] Visual highlighting for selected files

### 10.7.3 Preflight Page Improvements ✅
```
Modify: _ui/src/components/pages/PreflightPage.jsx
```

Completed:
- [x] Select All / Deselect All buttons for items
- [x] Listen for hash changes to support session switching
- [x] Fall back to localStorage if no session ID in URL
- [x] Proper state reset when session changes

### 10.7.4 Vite Configuration ✅
```
Modify: _ui/vite.config.js
```

Completed:
- [x] strictPort: true - fail if port 3100 in use (no silent fallback)
- [x] Prevents port drift (3100 → 3101 → 3102)

### 10.7.5 Backend Fixes ✅
```
Modify: _scripts/server.py
```

Completed:
- [x] Fix datetime.utcnow() deprecation warning
- [x] Use timezone-aware datetime.now(timezone.utc)

**Deliverable**: Improved UX with persistent state and batch operations ✅ COMPLETE

---

## Phase 10.8: Entity Extraction Quality ✅

**Goal**: Improve entity detection accuracy and add user feedback loop

**Session Date**: 2026-01-06 (Claude Code CLI)

### 10.8.1 False Positive Filtering ✅
```
Modify: _scripts/recog_engine/tier0.py
```

Expanded NON_NAME_CAPITALS (~300 entries):
- [x] US cities: Seattle, Chicago, Boston, Denver, Portland, etc.
- [x] International cities: Toronto, Vancouver, Dublin, Edinburgh, etc.
- [x] Business terms: Project, Meeting, Date, Deadline, Schedule, etc.
- [x] Research terms: Interviewer, Cohort, Site, Hypothesis, Protocol, etc.
- [x] Compass/project names: Meridian, Horizon, Summit, Aurora, etc.
- [x] Building/room terms: Conference, Room, Floor, Hall, etc.

### 10.8.2 Title Detection Fix ✅
```
Modify: _scripts/recog_engine/tier0.py
```

Completed:
- [x] Abbreviation protection pattern prevents sentence splitting on "Dr.", "Mr.", etc.
- [x] "Dr. Sarah" now correctly detected as HIGH confidence (was LOW)
- [x] Added Prof, Rev, Sir, Dame, Lord, Lady to PEOPLE_TITLES
- [x] Honorifics (Mr, Mrs, Dr, etc.) skipped when followed by actual name

### 10.8.3 Entity Confirmation Fix ✅
```
Modify: _ui/src/components/pages/EntitiesPage.jsx
```

Completed:
- [x] handleIdentify() now sends `confirmed: true` with entity update
- [x] Entities move from "Unknown" to "Confirmed" list after identification

### 10.8.4 Entity Rejection (Blacklist) UI ✅
```
Modify: _ui/src/components/pages/EntitiesPage.jsx, _ui/src/lib/api.js
```

Completed:
- [x] Added `rejectEntity()` API function
- [x] Added "Not a Name" button with Ban icon next to "Identify"
- [x] Clicking rejects entity and adds to blacklist database
- [x] Blacklisted values skipped in future extractions
- [x] Blacklist persists across server restarts

**Deliverable**: Higher quality entity extraction with user feedback loop ✅ COMPLETE

---

## Phase 11: EhkoLabs Website Modernization 📋

**Goal**: Convert marketing website to React + shadcn/ui with consistent branding

### 11.1 Planning
- [ ] Audit current website pages and components
- [ ] Define reusable component architecture
- [ ] SEO strategy (Next.js vs static export)
- [ ] Hosting plan (Vercel, Netlify, CloudFlare Pages)

### 11.2 Component Migration
- [ ] Homepage hero with CTAs
- [ ] Product showcase pages (ReCog, EhkoForge)
- [ ] About/team page
- [ ] Contact forms
- [ ] Blog/resources section
- [ ] Pricing tables
- [ ] Testimonials

### 11.3 Interactive Features
- [ ] Live ReCog demo widget
- [ ] Pricing calculator
- [ ] Feature comparison tables
- [ ] Newsletter signup
- [ ] Demo request forms

### 11.4 Shared Design System
- [ ] Component library shared across website + products
- [ ] Consistent color palette
- [ ] Typography system
- [ ] Icon library
- [ ] Animation patterns

**Deliverable**: Professional marketing site matching product quality

**Priority**: High (Q1 2026 target)

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
| 10 ✅ | React UI | Modern interface with shadcn/ui |
| 10.5 ✅ | Case Architecture | Case-centric document intelligence |
| 10.6 ✅ | Code Quality | Tests, indexes, shared components |
| 10.7 ✅ | UI Navigation | Hash routing, state persistence, batch ops |
| 10.8 ✅ | Entity Quality | False positive filtering, blacklist UI |
| 11 📋 | Website | Marketing site modernization |

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

*Last updated: Phase 10.8 Entity Extraction Quality COMPLETE - 06 Jan 2026*

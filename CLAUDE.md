# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ReCog is a text analysis engine that extracts, correlates, and synthesises insights from unstructured text. It uses tiered processing (Tier 0-3) from free signal extraction to LLM-powered synthesis, with a built-in critique layer for validation.

**Privacy:** This processes private/personal data. All processing is local.

## Commands

### Backend (Python Flask)

```bash
# From _scripts/ directory:
cd _scripts

# Install dependencies
pip install -r requirements.txt

# Initialize database
python recog_cli.py db init

# Start API server (http://localhost:5100)
python server.py

# Run background worker for queue processing
python worker.py

# Run tests
pytest tests/

# Run single test file
pytest tests/test_tier0.py -v

# Test with coverage
pytest tests/ --cov=recog_engine
```

### Frontend (React/Vite)

```bash
# From _ui/ directory:
cd _ui

npm install
npm run dev      # Dev server at http://localhost:3100 (strictPort enabled)
npm run build    # Production build to dist/
```

Note: The UI uses hash-based routing (e.g., `#upload`, `#preflight/123`). State persists to localStorage.

### CLI Operations

```bash
# File analysis
python recog_cli.py detect <file>       # Detect format
python recog_cli.py ingest <file>       # Parse and store
python recog_cli.py tier0 <file>        # Run Tier 0 analysis
python recog_cli.py tier0 --text "..."  # Analyze text directly

# Database
python recog_cli.py db init             # Initialize
python recog_cli.py db check            # Check status

# Preflight workflow
python recog_cli.py preflight create <folder>
python recog_cli.py preflight scan <id>
```

## Architecture

### Processing Tiers

| Tier | Cost | Purpose |
|------|------|---------|
| 0 | FREE | Signal extraction: emotions (14 categories), entities, temporal refs |
| 1 | LLM | Insight extraction from individual documents |
| 2 | LLM | Pattern correlation across documents |
| 3 | LLM | Synthesis: reports, recommendations |

### Backend Structure (`_scripts/`)

- `server.py` - Flask API server (all REST endpoints)
- `worker.py` - Background queue processor
- `recog_cli.py` - CLI interface
- `db.py` - SQLite database utilities

**recog_engine/** - Core processing:
- `tier0.py` - Free signal extraction (emotions, entities, temporal) with blacklist support
- `extraction.py` - LLM insight extraction with entity context
- `synth.py` - Pattern synthesis and clustering
- `critique.py` - Validation layer with reflexion loop
- `entity_registry.py` - Entity management/normalization, LLM-powered validation
- `entity_graph.py` - Relationship graph between entities
- `insight_store.py` - Insight persistence with source tracking
- `preflight.py` - Upload session management
- `case_store.py` - Case management
- `findings_store.py` - Findings storage
- `timeline_store.py` - Timeline events
- `state_machine.py` - Case state machine (v0.8: uploading→scanning→clarifying→processing→complete)
- `cost_estimator.py` - Token/cost estimation for LLM operations (v0.8)
- `auto_progress.py` - Background worker for automatic state advancement (v0.8)

**recog_engine/cypher/** - Conversational interface:
- `intent_classifier.py` - Hybrid regex + LLM intent classification
- `action_router.py` - Routes intents to backend operations
- `response_formatter.py` - Ensures consistent Cypher voice
- `prompts.py` - System prompts and response templates

**recog_engine/core/** - Lower-level components:
- `providers/` - LLM adapters (OpenAI, Anthropic)
- `routing.py` - LLM provider selection
- `extractor.py` - Extraction logic
- `correlator.py` - Correlation logic
- `synthesizer.py` - Synthesis logic
- `signal.py` - Signal processing
- `types.py` - Type definitions

**ingestion/** - File parsing:
- `universal.py` - Unified parser interface
- `parsers/` - Format-specific parsers (PDF, Excel, messages, etc.)
- `chunker.py` - Text chunking for large documents

### Frontend Structure (`_ui/`)

React 18 + Vite + shadcn/ui + Tailwind CSS

- `src/App.jsx` - Main app with tabbed navigation
- `src/lib/api.js` - API client for backend
- `src/components/pages/` - Page components:
  - `SignalExtraction.jsx` - Tier 0 analysis
  - `UploadPage.jsx` - File upload with drag & drop
  - `PreflightPage.jsx` - Review before processing
  - `CasesPage.jsx` - Case management
  - `EntitiesPage.jsx` - Entity registry
  - `InsightsPage.jsx` - Browse/manage insights
  - `PatternsPage.jsx` - Synthesized patterns
- `src/components/ui/` - shadcn components
- `src/components/cypher/` - Conversational interface:
  - `Cypher.jsx` - Slide-in panel with message history, assistant mode toggle (v0.8)
  - `CypherMessage.jsx` - User/assistant message bubbles
  - `CypherSuggestions.jsx` - Action buttons from responses
  - `CypherTyping.jsx` - Animated typing indicator
- `src/components/case/` - Case workflow components (v0.8):
  - `CaseTerminal.jsx` - Real-time analysis monitor with progress bar, top insights, log stream
  - `CostWarningDialog.jsx` - Cost confirmation dialog before LLM processing
- `src/contexts/CypherContext.jsx` - State management for Cypher, assistant mode (v0.8)
- `src/hooks/useCypherActions.js` - Navigation and action execution

### Data Flow

```
Files → Ingestion (parse) → Tier 0 (signals) → Tier 1 (insights) → Tier 2 (patterns) → Tier 3 (synthesis)
                                ↓                    ↓                   ↓
                          Entity Registry ←→ Critique Layer (validation)
```

## Key API Endpoints

- `POST /api/upload` - Upload file, create preflight session
- `POST /api/tier0` - Run Tier 0 signal extraction
- `POST /api/extract` - Run LLM extraction
- `GET/POST /api/preflight/<id>/*` - Preflight workflow
- `GET/PATCH /api/entities/*` - Entity management
- `POST /api/entities/<id>/reject` - Blacklist false positive entity
- `POST /api/entities/validate` - LLM-powered entity validation (batch)
- `GET/PATCH /api/insights/*` - Insight management
- `POST /api/synth/run` - Run synthesis
- `POST /api/critique/insight` - Validate insight
- `POST /api/cypher/message` - Send message to Cypher conversational interface
- `GET /api/extraction/status/<case_id>` - Poll extraction progress
- `GET /api/cases/<id>/progress` - Get real-time case processing progress (v0.8)
- `GET /api/cases/<id>/estimate` - Get cost estimate for LLM processing (v0.8)
- `POST /api/cases/<id>/start-processing` - Start LLM extraction with cost confirmation (v0.8)

## Cypher Intents

The conversational interface (Cypher) supports these intent categories:

| Intent | Example Phrases | Action |
|--------|-----------------|--------|
| `entity_correction` | "Webb isn't a person", "Remove Foundation" | Remove entity, add to blacklist |
| `entity_validation` | "validate entities", "AI validate", "check entities" | Run LLM validation, suggest false positives |
| `entity_validation_confirm` | "yes remove them", "keep Webb", "no keep all" | Confirm/reject/modify validation suggestions |
| `navigation` | "show entities", "go to insights" | Navigate to view |
| `filter_request` | "focus on Seattle", "filter by date" | Apply filter to current view |

### Entity Validation Flow

1. User triggers validation via "AI Validate" button or Cypher command
2. LLM analyzes unconfirmed person entities for false positives (e.g., "Foundation", "Protocol")
3. Cypher presents suggestions: "Found 5 likely false positives: Foundation, Research..."
4. User can:
   - Confirm: "yes remove them" → removes all suggested
   - Keep specific: "keep Webb" → removes from suggestion list
   - Cancel: "no keep all" → aborts validation

## Environment Variables

Required in `_scripts/.env`:
```bash
RECOG_OPENAI_API_KEY=sk-...        # For LLM features
RECOG_ANTHROPIC_API_KEY=sk-ant-... # Alternative provider
RECOG_DATA_DIR=./_data             # Data directory
RECOG_PORT=5100                    # Server port
```

## Database

SQLite at `_scripts/_data/recog.db` with tables:
- `entities`, `entity_relationships`, `entity_sentiment`, `entity_co_occurrences`, `entity_blacklist`
- `insights`, `insight_sources`, `insight_history`
- `patterns`, `insight_clusters`
- `critique_reports`
- `preflight_sessions`, `preflight_items`
- `processing_queue`
- `cases`, `findings`, `timeline_events`
- `case_progress` - Real-time processing progress tracking (v0.8)

## Supported File Formats

Text: `.txt`, `.md`, `.json`
Documents: `.pdf`
Data: `.csv`, `.xlsx`, `.xls`, `.xlsm`
Email: `.eml`, `.msg`
Chat: WhatsApp exports, SMS XML, ChatGPT `conversations.json`

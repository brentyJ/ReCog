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
npm run dev      # Dev server at http://localhost:3101
npm run build    # Production build to dist/
```

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
- `tier0.py` - Free signal extraction (emotions, entities, temporal)
- `extraction.py` - LLM insight extraction with entity context
- `synth.py` - Pattern synthesis and clustering
- `critique.py` - Validation layer with reflexion loop
- `entity_registry.py` - Entity management/normalization
- `entity_graph.py` - Relationship graph between entities
- `insight_store.py` - Insight persistence
- `preflight.py` - Upload session management
- `case_store.py` - Case management
- `findings_store.py` - Findings storage
- `timeline_store.py` - Timeline events

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
- `GET/PATCH /api/insights/*` - Insight management
- `POST /api/synth/run` - Run synthesis
- `POST /api/critique/insight` - Validate insight

## Environment Variables

Required in `_scripts/.env`:
```bash
RECOG_OPENAI_API_KEY=sk-...        # For LLM features
RECOG_ANTHROPIC_API_KEY=sk-ant-... # Alternative provider
RECOG_DATA_DIR=./_data             # Data directory
RECOG_PORT=5100                    # Server port
```

## Database

SQLite at `_scripts/recog.db` with tables:
- `entities`, `entity_relationships`, `entity_sentiment`, `entity_co_occurrences`
- `insights`, `insight_sources`, `insight_history`
- `patterns`, `insight_clusters`
- `critique_reports`
- `preflight_sessions`, `preflight_items`
- `processing_queue`
- `cases`, `findings`, `timeline_events`

## Supported File Formats

Text: `.txt`, `.md`, `.json`
Documents: `.pdf`
Data: `.csv`, `.xlsx`, `.xls`, `.xlsm`
Email: `.eml`, `.msg`
Chat: WhatsApp exports, SMS XML, ChatGPT `conversations.json`

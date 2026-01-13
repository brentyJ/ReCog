# ReCog - Recursive Cognition Engine

![CI](https://github.com/brentyJ/ReCog/actions/workflows/test.yml/badge.svg)

**v0.7.0** | Text analysis engine that extracts, correlates, and synthesises insights from unstructured text.

ReCog processes documents through tiered analysis—from free signal extraction to LLM-powered insight synthesis—while maintaining quality through a built-in critique layer. Features a conversational assistant (Cypher) for natural language interaction. Designed for enterprise document intelligence with applications in legal, research, operations, and compliance.

## Features

- **Cypher Assistant** — Conversational AI interface for natural language queries and commands
- **Case-Centric Workflow** — Organize documents into cases with context injection for focused analysis
- **Tiered Processing** — Start free with signal extraction, escalate to LLM when needed
- **Entity Intelligence** — Registry with relationship graphs, sentiment tracking, LLM-powered validation
- **Pattern Synthesis** — Cluster insights and synthesise higher-order patterns
- **Critique Layer** — Self-correcting validation prevents hallucination propagation
- **Findings Validation** — Promote insights to verified findings with status tracking
- **Multi-Provider LLM** — OpenAI and Anthropic support with automatic fallback
- **Preflight Workflow** — Review and filter before processing, with cost estimates
- **Modern React UI** — Responsive interface with real-time extraction progress
- **Export-First** — SQLite database, human-readable formats, no lock-in

## Quick Start

```bash
# Clone and install backend
git clone https://github.com/brentyJ/recog.git
cd recog/_scripts
pip install -r requirements.txt

# Configure (copy and edit with your API keys)
cp .env.example .env

# Initialize database
python recog_cli.py db init

# Start backend server
python server.py
```

```bash
# Install and start frontend (in another terminal)
cd recog/_ui
npm install
npm run dev
```

- **Backend API**: http://localhost:5100
- **Frontend UI**: http://localhost:3100

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 0: DATA INGESTION                      │
│  File Detection → Adaptive Parsing → Tier 0 Signals → Entities │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  LAYER 1: MAP (Extraction)                      │
│  Per-document LLM analysis → Structured InsightJSON             │
│  Entity context injection from registry                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                LAYER 2: REDUCE (Synthesis)                      │
│  Cluster insights → Cross-reference → Pattern detection         │
│  Thematic, temporal, entity-based clustering strategies         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│               LAYER 3: CRITIQUE (Validation)                    │
│  Citation check → Confidence calibration → Reflexion loop       │
│  Automatic refinement for failed validations                    │
└─────────────────────────────────────────────────────────────────┘
```

### Processing Tiers

| Tier | Cost | Purpose |
|------|------|---------|
| **Tier 0** | FREE | Signal extraction: emotions (14 categories), entities, temporal refs, structure |
| **Tier 1** | LLM | Insight extraction: discrete observations from individual documents |
| **Tier 2** | LLM | Pattern correlation: themes, contradictions, evolution across documents |
| **Tier 3** | LLM | Synthesis: reports, recommendations, actionable intelligence |

## Supported File Formats

- **Text**: `.txt`, `.md`, `.json`
- **Documents**: `.pdf` (text extraction)
- **Data**: `.csv`, `.xlsx`, `.xls`, `.xlsm`
- **Email**: `.eml`, `.msg`
- **Chat Exports**: WhatsApp, SMS XML, ChatGPT `conversations.json`

## Cases: Document Intelligence Workflow

ReCog uses **Cases** to organize document analysis around specific questions or investigations. Cases provide:

- **Context Injection** — Case context (title, focus areas) is injected into LLM prompts for more relevant extraction
- **Findings Workflow** — Promote high-confidence insights to verified findings
- **Timeline Tracking** — Auto-generated chronicle of case evolution
- **Document Organization** — Group related documents for cross-reference analysis

### Case Workflow

```
1. Create Case
   └── Define title, context, and focus areas (e.g., "Q3 Sales Analysis")

2. Upload Documents
   └── Select case during upload → context stored with preflight session

3. Preflight Review
   └── Case context banner shows → confirms context will be injected

4. Process Documents
   └── LLM extraction uses case context → insights tagged with case_id

5. Review Findings
   └── Verify/reject findings → add annotations → track validation status

6. Timeline
   └── Auto-generated events: doc_added, insights_extracted, finding_verified
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Case** | Organizational container with title, context, focus areas |
| **Findings** | Validated insights promoted from raw insights |
| **Timeline** | Auto-generated chronicle of case activities |
| **Context Injection** | Case context injected into LLM prompts |

## Cypher: Conversational Interface

Cypher is ReCog's AI assistant that provides natural language interaction with the system. Access it via the slide-in panel in the UI or the `/api/cypher/message` endpoint.

### Capabilities

| Intent | Example Commands | Action |
|--------|------------------|--------|
| **Entity Correction** | "Webb isn't a person", "Remove Foundation" | Remove entity, add to blacklist |
| **Entity Validation** | "validate entities", "AI validate" | LLM suggests false positives for review |
| **Navigation** | "show entities", "go to insights" | Navigate to views |
| **Filtering** | "focus on Seattle", "filter by date" | Apply search filters |
| **Status** | "what's processing?", "extraction status" | Show current progress |

### Interactive Validation Flow

```
User: "validate entities"
Cypher: "Found 5 likely false positives: Foundation, Research, Protocol,
         Institute, Committee. Remove them?"
         [Yes, remove them] [No, keep all] [Let me review]

User: "keep Foundation"
Cypher: "Kept 'Foundation'. Still 4 to remove: Research, Protocol,
         Institute, Committee. Continue?"
         [Yes, remove rest] [No, keep all]

User: "yes"
Cypher: "Removed 4 false positives. View entities?"
```

## API Reference

### Health & Info

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check with database stats |
| `/api/info` | GET | Server version and available endpoints |

### File Processing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/detect` | POST | Detect file format (multipart upload) |
| `/api/upload` | POST | Upload file, create preflight session |
| `/api/tier0` | POST | Run Tier 0 signal extraction |
| `/api/extract` | POST | Run LLM extraction with entity context |

### Preflight Workflow

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/preflight/<id>` | GET | Get session summary |
| `/api/preflight/<id>/items` | GET | List items in session |
| `/api/preflight/<id>/filter` | POST | Apply filters (min_words, date range, keywords) |
| `/api/preflight/<id>/exclude/<item_id>` | POST | Exclude item |
| `/api/preflight/<id>/include/<item_id>` | POST | Re-include item |
| `/api/preflight/<id>/confirm` | POST | Confirm and queue for processing |

### Entity Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/entities` | GET | List entities (filter by type, confirmed status) |
| `/api/entities/unknown` | GET | Entities needing identification |
| `/api/entities/<id>` | GET | Get entity details |
| `/api/entities/<id>` | PATCH | Update entity (display_name, relationship, anonymise) |
| `/api/entities/<id>/reject` | POST | Blacklist entity as false positive |
| `/api/entities/validate` | POST | LLM-powered batch validation |
| `/api/entities/stats` | GET | Entity registry statistics |

### Entity Graph

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/entities/<id>/relationships` | GET | Entity relationships |
| `/api/entities/<id>/relationships` | POST | Add relationship |
| `/api/entities/<id>/network` | GET | Relationship network (configurable depth) |
| `/api/entities/<id>/timeline` | GET | Entity events timeline |
| `/api/entities/<id>/sentiment` | GET | Sentiment summary + history |
| `/api/entities/<id>/sentiment` | POST | Record sentiment |
| `/api/entities/<a>/path/<b>` | GET | Shortest path between entities |
| `/api/entities/graph/stats` | GET | Graph statistics |
| `/api/relationships` | GET | List all relationships |
| `/api/relationships/<id>` | DELETE | Remove relationship |
| `/api/relationships/types` | GET | Available relationship types |

### Insights

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/insights` | GET | List insights (filter by status, significance, type) |
| `/api/insights/<id>` | GET | Get insight with sources and history |
| `/api/insights/<id>` | PATCH | Update status/significance/themes |
| `/api/insights/<id>` | DELETE | Soft delete (or `?hard=true` for permanent) |
| `/api/insights/stats` | GET | Insight statistics |

### Synthesis Engine

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/synth/clusters` | POST | Create insight clusters |
| `/api/synth/clusters` | GET | List pending clusters |
| `/api/synth/run` | POST | Run full synthesis cycle |
| `/api/synth/patterns` | GET | List patterns |
| `/api/synth/patterns/<id>` | GET | Get pattern details |
| `/api/synth/patterns/<id>` | PATCH | Update pattern status |
| `/api/synth/stats` | GET | Synthesis statistics |

### Critique Engine

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/critique/insight` | POST | Validate an insight |
| `/api/critique/pattern` | POST | Validate a pattern |
| `/api/critique/refine` | POST | Critique with auto-refinement loop |
| `/api/critique/<id>` | GET | Get critique report |
| `/api/critique/for/<type>/<id>` | GET | Critiques for target |
| `/api/critique` | GET | List critique reports |
| `/api/critique/stats` | GET | Critique statistics |
| `/api/critique/strictness` | GET | Current strictness level |
| `/api/critique/strictness` | POST | Set strictness (lenient/standard/strict) |

### Processing Queue

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/queue` | GET | List queue items |
| `/api/queue/stats` | GET | Queue statistics |
| `/api/queue/<id>` | GET | Get queue item |
| `/api/queue/<id>/retry` | POST | Retry failed item |
| `/api/queue/<id>` | DELETE | Remove from queue |
| `/api/queue/clear` | POST | Clear failed/complete items |

### Cypher (Conversational Interface)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cypher/message` | POST | Send message to Cypher assistant |
| `/api/extraction/status/<case_id>` | GET | Poll extraction progress |
| `/api/extraction/status/global` | GET | Global extraction status |

### Cases

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cases` | POST | Create new case |
| `/api/cases` | GET | List cases (filter by status) |
| `/api/cases/<id>` | GET | Get case details |
| `/api/cases/<id>` | PATCH | Update case (title, context, status) |
| `/api/cases/<id>` | DELETE | Delete case with cascade |
| `/api/cases/<id>/documents` | GET | List documents in case |
| `/api/cases/<id>/documents` | POST | Add document to case |
| `/api/cases/<id>/stats` | GET | Case statistics |
| `/api/cases/<id>/context` | GET | Get context for prompt injection |

### Findings

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/findings` | POST | Promote insight to finding |
| `/api/cases/<id>/findings` | GET | List case findings |
| `/api/findings/<id>` | GET | Get finding details |
| `/api/findings/<id>` | PATCH | Update status (verified/rejected) |
| `/api/findings/<id>/note` | POST | Add annotation |
| `/api/findings/<id>` | DELETE | Demote finding |
| `/api/cases/<id>/findings/auto-promote` | POST | Batch auto-promotion |

### Timeline

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cases/<id>/timeline` | GET | Get timeline events |
| `/api/cases/<id>/timeline` | POST | Add human annotation |
| `/api/timeline/<id>/annotate` | POST | Annotate existing event |
| `/api/cases/<id>/activity` | GET | Recent case activity |

## CLI Commands

```bash
# File operations
python recog_cli.py detect <file>      # Detect format
python recog_cli.py ingest <file>      # Parse and store
python recog_cli.py formats            # List supported formats

# Tier 0 analysis
python recog_cli.py tier0 <file>       # Analyse file
python recog_cli.py tier0 --text "..." # Analyse text directly

# Database
python recog_cli.py db init            # Initialize database
python recog_cli.py db check           # Check database status

# Preflight workflow
python recog_cli.py preflight create <folder>  # Create session
python recog_cli.py preflight scan <id>        # Scan session
python recog_cli.py preflight status <id>      # Get status
```

## Configuration

### Environment Variables

```bash
# Required for LLM features
RECOG_OPENAI_API_KEY=sk-...           # OpenAI API key
RECOG_ANTHROPIC_API_KEY=sk-ant-...    # Anthropic API key (optional)

# Server configuration
RECOG_DATA_DIR=./_data                # Data directory (default: ./_data)
RECOG_PORT=5100                       # Server port (default: 5100)
RECOG_DEBUG=false                     # Debug mode

# LLM configuration
RECOG_LLM_MODEL=gpt-4o-mini           # Default model
RECOG_LLM_MAX_TOKENS=2000             # Max tokens per request
RECOG_COST_LIMIT_CENTS=100            # Cost limit for batch processing
```

### Provider Selection

ReCog auto-detects available providers from environment variables. You can override per-request:

```json
POST /api/extract
{
  "text": "...",
  "provider": "anthropic"
}
```

## Docker Deployment

```bash
# Build and run
docker-compose up -d

# Or build manually
docker build -t recog .
docker run -p 5100:5100 -v ./data:/app/_data recog
```

The Docker setup includes:
- Multi-stage build for smaller images
- Gunicorn for production serving
- Volume mounts for persistent data
- Worker service for background processing

## Database Schema

ReCog uses SQLite with 19+ tables:

**Core Tables:**
- `entities` — Entity registry with normalisation
- `entity_relationships` — Graph edges between entities
- `entity_sentiment` — Sentiment tracking over time
- `entity_co_occurrences` — Co-occurrence pairs
- `insights` — Extracted insights (with `case_id` FK)
- `insight_sources` — Source links for insights
- `insight_history` — Audit trail
- `patterns` — Synthesised patterns (with `case_id` FK)
- `insight_clusters` — Clustering for synthesis
- `critique_reports` — Validation results
- `preflight_sessions` — Upload sessions (with `case_id` FK)
- `preflight_items` — Items pending review
- `processing_queue` — Background job queue (with `case_id` FK)

**Case Tables:**
- `cases` — Case containers with title, context, focus_areas
- `case_documents` — Links documents to cases
- `findings` — Validated insights promoted from raw insights
- `case_timeline` — Auto-generated case evolution log

## Development

```bash
# Run tests
pytest tests/

# Run with debug logging
RECOG_DEBUG=true python server.py
```

### Project Structure

```
ReCog/
├── _scripts/                  # Backend (Python/Flask)
│   ├── server.py              # Flask API server (localhost:5100)
│   ├── worker.py              # Background queue processor
│   ├── recog_cli.py           # Command-line interface
│   ├── db.py                  # Database utilities
│   ├── recog_engine/          # Core processing modules
│   │   ├── tier0.py           # Signal extraction (emotions, entities, temporal)
│   │   ├── extraction.py      # LLM insight extraction
│   │   ├── synth.py           # Pattern synthesis
│   │   ├── critique.py        # Validation layer
│   │   ├── entity_registry.py # Entity management + LLM validation
│   │   ├── entity_graph.py    # Relationship graph
│   │   ├── insight_store.py   # Insight persistence
│   │   ├── cypher/            # Conversational interface
│   │   │   ├── intent_classifier.py  # Hybrid regex + LLM classification
│   │   │   ├── action_router.py      # Routes intents to operations
│   │   │   └── response_formatter.py # Consistent Cypher voice
│   │   └── core/providers/    # LLM adapters (OpenAI, Anthropic)
│   └── ingestion/             # File parsers (PDF, Excel, chat exports)
│
├── _ui/                       # Frontend (React/Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── pages/         # Dashboard, Upload, Preflight, Entities, Insights
│   │   │   ├── cypher/        # Conversational UI components
│   │   │   └── ui/            # shadcn/ui components
│   │   ├── contexts/          # React context (CypherContext)
│   │   ├── hooks/             # Custom hooks (useCypherActions)
│   │   └── lib/api.js         # API client
│   └── package.json           # React 18 + Vite (localhost:3100)
│
├── _data/                     # Database and uploads
├── _docs/                     # Documentation
├── _archive/                  # Deprecated versions
├── CLAUDE.md                  # AI assistant instructions
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## License

**AGPL-3.0** — See [LICENSE](LICENSE)

Commercial licenses available for enterprise deployments, custom adapters, and private modifications.

Contact: **brent@ehkolabs.io**

---

*Built by [EhkoLabs](https://ehkolabs.io) — Recursive cognition for enterprise intelligence*

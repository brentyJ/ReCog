# ReCog - Recursive Cognition Engine

Text analysis engine that extracts, correlates, and synthesises insights from unstructured text.

## Quick Start

```bash
# Install dependencies
cd _scripts
pip install -r requirements.txt

# Initialize database
python recog_cli.py db init

# Start server
python server.py
```

Server runs at http://localhost:5000

## Architecture

```
Processing Tiers:
├── Tier 0: Signal Extraction (FREE - no LLM)
│   ├── Emotions (14 categories)
│   ├── Entities (phones, emails, people)
│   ├── Temporal references
│   └── Structural analysis
├── Tier 1: Insight Extraction (LLM)
│   ├── Speaker attribution
│   ├── Similarity detection
│   └── Surfacing logic
├── Tier 2: Pattern Correlation (LLM)
└── Tier 3: Synthesis (LLM)
```

## CLI Commands

```bash
# File operations
python recog_cli.py detect <file>
python recog_cli.py ingest <file>
python recog_cli.py formats

# Tier 0 analysis
python recog_cli.py tier0 <file>
python recog_cli.py tier0 --text "your text"

# Database
python recog_cli.py db init
python recog_cli.py db check

# Preflight workflow
python recog_cli.py preflight create <folder>
python recog_cli.py preflight scan <id>
python recog_cli.py preflight status <id>
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/upload` | POST | Upload file, create preflight |
| `/api/tier0` | POST | Run Tier 0 on text |
| `/api/preflight/<id>` | GET | Get preflight summary |
| `/api/preflight/<id>/filter` | POST | Apply filters |
| `/api/preflight/<id>/confirm` | POST | Confirm for processing |
| `/api/entities` | GET | List entities |
| `/api/entities/unknown` | GET | Get unknown entities |
| `/api/entities/<id>` | PATCH | Update entity |
| `/api/extract` | POST | Run LLM extraction |

## Environment Variables

```bash
RECOG_DATA_DIR=./_data      # Data directory
RECOG_PORT=5000             # Server port
RECOG_DEBUG=false           # Debug mode
RECOG_LLM_API_KEY=sk-...    # OpenAI API key (for extraction)
RECOG_LLM_MODEL=gpt-4o-mini # LLM model
```

## License

AGPLv3 - See LICENSE

Commercial licenses: brent@ehkolabs.io

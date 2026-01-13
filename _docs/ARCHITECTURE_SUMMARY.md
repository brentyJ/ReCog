# ReCog Architecture Summary

*Generated: 2026-01-13 11:47*

## Overview

ReCog is a text analysis engine that extracts, correlates, and synthesizes insights from unstructured text. It processes documents through a tiered pipeline, from free signal extraction to LLM-powered synthesis.

## System Components

### Frontend Layer
- **React UI** (Port 3100): Main user interface built with Vite and shadcn/ui
- **Cypher**: Conversational interface for natural language interaction
- **Case Management**: Workflow UI for document intelligence investigations

### API Layer
- **Flask Server** (Port 5100): REST API serving all backend operations
- **Background Worker**: Async job processing for long-running tasks

### Document Ingestion
- **File Upload**: Handles multiple formats (PDF, CSV, Excel, email, chat exports)
- **Universal Parser**: Format detection and content extraction
- **Text Chunker**: Splits large documents for processing

### Processing Pipeline

| Tier | Cost | Purpose |
|------|------|---------|
| **Tier 0** | FREE | Signal extraction: emotions (14 categories), entities, temporal refs |
| **Tier 1** | LLM | Insight extraction from individual documents |
| **Tier 2** | LLM | Pattern correlation across documents |
| **Tier 3** | LLM | Synthesis: reports, recommendations |

### Case Architecture
- **Case Store**: Container for related document analysis
- **Findings Store**: Validated insights with verification status
- **Timeline Store**: Auto-logged events tracking case evolution
- **State Machine**: Workflow states (uploading → scanning → clarifying → processing → complete)

### Entity Management
- **Entity Registry**: Central store for extracted entities
- **Entity Graph**: Relationship mapping between entities
- **Blacklist**: False positive management
- **LLM Validation**: AI-powered entity verification

### LLM Integration
- **Provider Router**: Selects between available LLM providers
- **OpenAI**: GPT models for extraction and synthesis
- **Anthropic Claude**: Alternative LLM provider

### Quality & Validation
- **Critique Engine**: Validates extracted insights
- **Cost Estimator**: Predicts LLM token usage and costs

### Data Layer
- **SQLite Database**: Persistent storage for all entities, insights, cases
- **Uploads Directory**: File storage for uploaded documents

## Data Flow

```
Documents → Ingestion → Tier 0 (free signals) → Entity Registry
                ↓
            Tier 1 (LLM insights) → Critique validation
                ↓
            Tier 2 (pattern correlation)
                ↓
            Tier 3 (synthesis) → Reports/Findings
```

## Key Design Decisions

1. **Tiered Processing**: Start cheap (Tier 0), escalate as needed
2. **Case-Centric**: All analysis organized around investigation cases
3. **Privacy-First**: All processing local, no external data sharing
4. **Critique Layer**: Every LLM output validated before storage
5. **Provider Agnostic**: Works with OpenAI or Claude

## Port Configuration

| Service | Port |
|---------|------|
| React Frontend (dev) | 3100 |
| Flask API | 5100 |

## File Structure

```
ReCog/
├── _scripts/           # Backend Python code
│   ├── server.py       # Flask API
│   ├── worker.py       # Background processor
│   ├── recog_engine/   # Core processing modules
│   ├── ingestion/      # File parsers
│   └── migrations/     # Database schemas
├── _ui/                # React frontend
│   └── src/
│       ├── components/ # UI components
│       └── lib/        # API client
├── _data/              # Runtime data (gitignored)
└── _docs/              # Documentation
```

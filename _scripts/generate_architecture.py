#!/usr/bin/env python3
"""
ReCog Architecture Generator - Creates Mermaid diagrams of system architecture

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Generates:
- Mermaid diagram (ARCHITECTURE.mmd)
- Text summary (ARCHITECTURE_SUMMARY.md)

Usage:
    python generate_architecture.py [--output-dir DIR]
"""

import sys
from pathlib import Path
from datetime import datetime


# =============================================================================
# CONFIGURATION
# =============================================================================

def get_repo_root() -> Path:
    """Get the repository root directory."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent


DEFAULT_OUTPUT_DIR = get_repo_root() / "_docs"


# =============================================================================
# MERMAID DIAGRAM
# =============================================================================

MERMAID_DIAGRAM = '''%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e1e5eb', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#4a4a6a', 'lineColor': '#6b7280', 'secondaryColor': '#f0f4f8', 'tertiaryColor': '#fff' }}}%%

graph TB
    subgraph Frontend["Frontend (React + Vite)"]
        UI[React UI<br/>Port 3100]
        Cypher[Cypher<br/>Conversational Interface]
        CaseUI[Case Management<br/>Workflow UI]
    end

    subgraph API["Flask API Server (Port 5100)"]
        Server[server.py<br/>REST Endpoints]
        Worker[worker.py<br/>Background Jobs]
    end

    subgraph Ingestion["Document Ingestion"]
        Upload[File Upload]
        Parser[Universal Parser]
        Chunker[Text Chunker]
        Detect[Format Detection]
    end

    subgraph Processing["Processing Pipeline"]
        subgraph Tier0["Tier 0 (FREE)"]
            Signals[Signal Extraction]
            Emotions[Emotion Detection]
            Entities[Entity Detection]
            Temporal[Temporal Refs]
        end

        subgraph Tier1["Tier 1 (LLM)"]
            Extract[Insight Extraction]
        end

        subgraph Tier2["Tier 2 (LLM)"]
            Correlate[Pattern Correlation]
        end

        subgraph Tier3["Tier 3 (LLM)"]
            Synth[Synthesis & Reports]
        end
    end

    subgraph CaseSystem["Case Architecture"]
        CaseStore[Case Store]
        Findings[Findings Store]
        Timeline[Timeline Events]
        StateMachine[State Machine<br/>uploading→scanning→<br/>clarifying→processing→complete]
    end

    subgraph EntitySystem["Entity Management"]
        Registry[Entity Registry]
        Graph[Entity Graph]
        Blacklist[Blacklist]
        Validation[LLM Validation]
    end

    subgraph Storage["Data Layer"]
        SQLite[(SQLite DB<br/>recog.db)]
        Uploads[(Uploads<br/>_data/uploads/)]
    end

    subgraph LLMRouting["LLM Providers"]
        Router[Provider Router]
        OpenAI[OpenAI API]
        Claude[Anthropic Claude]
    end

    subgraph Quality["Quality & Validation"]
        Critique[Critique Engine]
        CostEst[Cost Estimator]
    end

    %% Frontend connections
    UI --> Server
    Cypher --> Server
    CaseUI --> Server

    %% Upload flow
    UI -->|Upload| Upload
    Upload --> Detect
    Detect --> Parser
    Parser --> Chunker
    Chunker --> Signals

    %% Processing flow
    Signals --> Emotions
    Signals --> Entities
    Signals --> Temporal

    Entities --> Registry
    Registry --> Graph
    Registry --> Blacklist

    Tier0 -->|Promote| Tier1
    Tier1 -->|Correlate| Tier2
    Tier2 -->|Synthesize| Tier3

    %% LLM connections
    Extract --> Router
    Correlate --> Router
    Synth --> Router
    Validation --> Router

    Router --> OpenAI
    Router --> Claude

    %% Case flow
    Server --> CaseStore
    CaseStore --> Findings
    CaseStore --> Timeline
    CaseStore --> StateMachine
    StateMachine --> Worker

    %% Quality
    Extract --> Critique
    CostEst --> Tier1
    CostEst --> Tier2
    CostEst --> Tier3

    %% Storage
    Server --> SQLite
    Registry --> SQLite
    CaseStore --> SQLite
    Parser --> Uploads
    Upload --> Uploads

    %% Styling
    classDef frontend fill:#dbeafe,stroke:#3b82f6,stroke-width:2px
    classDef api fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
    classDef tier0 fill:#d1fae5,stroke:#10b981,stroke-width:2px
    classDef llm fill:#fce7f3,stroke:#ec4899,stroke-width:2px
    classDef storage fill:#e5e7eb,stroke:#6b7280,stroke-width:2px
    classDef case fill:#e0e7ff,stroke:#6366f1,stroke-width:2px

    class UI,Cypher,CaseUI frontend
    class Server,Worker api
    class Signals,Emotions,Entities,Temporal tier0
    class Extract,Correlate,Synth,Router,OpenAI,Claude llm
    class SQLite,Uploads storage
    class CaseStore,Findings,Timeline,StateMachine case
'''


# =============================================================================
# SUMMARY DOCUMENT
# =============================================================================

ARCHITECTURE_SUMMARY = '''# ReCog Architecture Summary

*Generated: {timestamp}*

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
'''


# =============================================================================
# GENERATOR
# =============================================================================

def generate_architecture(output_dir: Path = None) -> tuple:
    """
    Generate architecture diagram and summary.

    Returns:
        Tuple of (mermaid_path, summary_path)
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate Mermaid diagram
    mermaid_path = output_dir / "ARCHITECTURE.mmd"
    mermaid_path.write_text(MERMAID_DIAGRAM, encoding="utf-8")
    print(f"[OK] Generated: {mermaid_path}")

    # Generate summary
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    summary_content = ARCHITECTURE_SUMMARY.format(timestamp=timestamp)

    summary_path = output_dir / "ARCHITECTURE_SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")
    print(f"[OK] Generated: {summary_path}")

    return mermaid_path, summary_path


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate ReCog architecture documentation")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})"
    )

    args = parser.parse_args()

    print("\n" + "=" * 50)
    print("  ReCog Architecture Generator")
    print("=" * 50 + "\n")

    mermaid_path, summary_path = generate_architecture(args.output_dir)

    print("\n" + "-" * 50)
    print("  Generated files:")
    print(f"  - {mermaid_path}")
    print(f"  - {summary_path}")
    print("-" * 50)
    print("\nTo view the Mermaid diagram:")
    print("  - Paste into https://mermaid.live/")
    print("  - Or use VS Code Mermaid extension")
    print()


if __name__ == "__main__":
    main()

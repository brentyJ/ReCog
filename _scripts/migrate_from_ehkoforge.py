"""
ReCog Migration Script - Phase 1
Copies and adapts recog_engine from EhkoForge to standalone ReCog vault.

Run from: G:\Other computers\Ehko\Obsidian\ReCog\_scripts\
Usage: python migrate_from_ehkoforge.py

Copyright (c) 2025 Brent Lefebure / EhkoLabs
"""

import os
import shutil
import re
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

SOURCE_BASE = Path(r"G:\Other computers\Ehko\Obsidian\EhkoForge\5.0 Scripts")
TARGET_BASE = Path(r"G:\Other computers\Ehko\Obsidian\ReCog\_scripts")

# Files to copy from recog_engine/core/
CORE_FILES = [
    "types.py",
    "config.py", 
    "llm.py",
    "signal.py",
    "extractor.py",
    "correlator.py",
    "synthesizer.py",
]

# Files to copy from recog_engine/adapters/ (excluding ehkoforge.py)
ADAPTER_FILES = [
    "base.py",
    "memory.py",
]

# Files to SKIP (EhkoForge-specific)
SKIP_FILES = [
    "ehkoforge.py",
    "authority_mana.py", 
    "mana_manager.py",
]

# Files to copy from ingestion/
INGESTION_FILES = [
    "service.py",
    "chunker.py",
]

PARSER_FILES = [
    "pdf.py",
    "markdown.py",
    "plaintext.py",
    "messages.py",
]


# =============================================================================
# HEADER UPDATES
# =============================================================================

OLD_COPYRIGHT = "Copyright (c) 2025 Brent Lefebure"
NEW_COPYRIGHT = "Copyright (c) 2025 Brent Lefebure / EhkoLabs"


def update_header(content: str) -> str:
    """Update copyright header and clean any Ehko-specific references."""
    # Update copyright
    content = content.replace(OLD_COPYRIGHT, NEW_COPYRIGHT)
    return content


# =============================================================================
# FILE OPERATIONS
# =============================================================================

def copy_and_update(src: Path, dst: Path):
    """Copy file and update headers."""
    print(f"  Copying: {src.name}")
    
    with open(src, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = update_header(content)
    
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(content)


def copy_core_files():
    """Copy recog_engine/core/ files."""
    print("\n[1/6] Copying core files...")
    src_dir = SOURCE_BASE / "recog_engine" / "core"
    dst_dir = TARGET_BASE / "recog_engine" / "core"
    
    for filename in CORE_FILES:
        src = src_dir / filename
        dst = dst_dir / filename
        if src.exists():
            copy_and_update(src, dst)
        else:
            print(f"  WARNING: {src} not found")
    
    # Copy __init__.py
    copy_and_update(src_dir / "__init__.py", dst_dir / "__init__.py")


def copy_adapter_files():
    """Copy recog_engine/adapters/ files (excluding ehkoforge.py)."""
    print("\n[2/6] Copying adapter files...")
    src_dir = SOURCE_BASE / "recog_engine" / "adapters"
    dst_dir = TARGET_BASE / "recog_engine" / "adapters"
    
    for filename in ADAPTER_FILES:
        src = src_dir / filename
        dst = dst_dir / filename
        if src.exists():
            copy_and_update(src, dst)


def copy_ingestion_files():
    """Copy ingestion/ files."""
    print("\n[3/6] Copying ingestion files...")
    src_dir = SOURCE_BASE / "ingestion"
    dst_dir = TARGET_BASE / "ingestion"
    
    for filename in INGESTION_FILES:
        src = src_dir / filename
        dst = dst_dir / filename
        if src.exists():
            copy_and_update(src, dst)
    
    # Copy parsers
    src_parsers = src_dir / "parsers"
    dst_parsers = dst_dir / "parsers"
    
    for filename in PARSER_FILES:
        src = src_parsers / filename
        dst = dst_parsers / filename
        if src.exists():
            copy_and_update(src, dst)


# =============================================================================
# GENERATED FILES
# =============================================================================

def create_adapters_init():
    """Create adapters/__init__.py without EhkoForge reference."""
    print("\n[4/6] Creating adapters/__init__.py...")
    
    content = '''"""
ReCog Adapters - Adapter Module

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Adapters connect ReCog to specific applications.
"""

from .base import RecogAdapter
from .memory import MemoryAdapter
from .sqlite import SQLiteAdapter


__all__ = [
    "RecogAdapter",
    "MemoryAdapter",
    "SQLiteAdapter",
]
'''
    
    dst = TARGET_BASE / "recog_engine" / "adapters" / "__init__.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(content)


def create_sqlite_adapter():
    """Create standalone SQLite adapter."""
    print("  Creating sqlite.py adapter...")
    
    content = '''"""
ReCog Adapters - SQLite Adapter v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

SQLite-based adapter for persistent storage.
Standalone version for ReCog without EhkoForge dependencies.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Optional, Iterator, Dict, Any
from datetime import datetime

from .base import RecogAdapter
from recog_engine.core.types import (
    Document,
    Insight,
    Pattern,
    Synthesis,
    ProcessingState,
    PatternType,
    SynthesisType,
    ProcessingStatus,
)

logger = logging.getLogger(__name__)


class SQLiteAdapter(RecogAdapter):
    """
    SQLite-based adapter for ReCog.
    
    Stores documents, insights, patterns, and syntheses in a SQLite database.
    
    Usage:
        adapter = SQLiteAdapter("path/to/recog.db")
        adapter.initialize()  # Creates tables if needed
        
        # Add documents
        adapter.save_document(Document.create(...))
        
        # Process with engine
        engine = RecogEngine(adapter, config)
        engine.process_corpus("my-corpus")
        
        # Retrieve results
        insights = adapter.get_insights()
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str, context: str = None):
        """
        Initialize SQLite adapter.
        
        Args:
            db_path: Path to SQLite database file
            context: Optional context string for prompts
        """
        self.db_path = Path(db_path)
        self._context = context
        self._conn: Optional[sqlite3.Connection] = None
    
    def initialize(self) -> None:
        """Create database tables if they don't exist."""
        self._connect()
        self._create_tables()
    
    def _connect(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _create_tables(self) -> None:
        """Create database schema."""
        conn = self._connect()
        cursor = conn.cursor()
        
        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                metadata TEXT,
                signals TEXT,
                created_at TEXT NOT NULL,
                processed_at TEXT
            )
        """)
        
        # Insights table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                themes TEXT NOT NULL,
                significance REAL NOT NULL,
                confidence REAL NOT NULL,
                source_ids TEXT NOT NULL,
                excerpts TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                pass_count INTEGER DEFAULT 1
            )
        """)
        
        # Patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                insight_ids TEXT NOT NULL,
                strength REAL NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Syntheses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS syntheses (
                id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                synthesis_type TEXT NOT NULL,
                pattern_ids TEXT NOT NULL,
                significance REAL NOT NULL,
                confidence REAL NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Processing state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_state (
                corpus_id TEXT PRIMARY KEY,
                current_tier INTEGER,
                documents_processed INTEGER,
                documents_total INTEGER,
                insights_extracted INTEGER,
                patterns_found INTEGER,
                passes_completed INTEGER,
                status TEXT,
                error TEXT,
                started_at TEXT,
                completed_at TEXT
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_insights_themes ON insights(themes)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_type)")
        
        conn.commit()
    
    # =========================================================================
    # DOCUMENT METHODS
    # =========================================================================
    
    def save_document(self, document: Document) -> None:
        """Save a document to the database."""
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO documents 
            (id, content, source_type, source_ref, metadata, signals, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            document.id,
            document.content,
            document.source_type,
            document.source_ref,
            json.dumps(document.metadata),
            json.dumps(document.signals) if document.signals else None,
            document.created_at.isoformat(),
        ))
        conn.commit()
    
    def load_documents(self, **filters) -> Iterator[Document]:
        """Yield documents, optionally filtered."""
        conn = self._connect()
        cursor = conn.cursor()
        
        query = "SELECT * FROM documents WHERE 1=1"
        params = []
        
        if "source_type" in filters:
            query += " AND source_type = ?"
            params.append(filters["source_type"])
        
        if "unprocessed" in filters and filters["unprocessed"]:
            query += " AND processed_at IS NULL"
        
        cursor.execute(query, params)
        
        for row in cursor.fetchall():
            yield self._row_to_document(row)
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get document by ID."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return self._row_to_document(row) if row else None
    
    def count_documents(self, **filters) -> int:
        """Count documents matching filters."""
        conn = self._connect()
        cursor = conn.cursor()
        
        query = "SELECT COUNT(*) FROM documents WHERE 1=1"
        params = []
        
        if "source_type" in filters:
            query += " AND source_type = ?"
            params.append(filters["source_type"])
        
        cursor.execute(query, params)
        return cursor.fetchone()[0]
    
    def _row_to_document(self, row) -> Document:
        """Convert database row to Document."""
        return Document(
            id=row["id"],
            content=row["content"],
            source_type=row["source_type"],
            source_ref=row["source_ref"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            signals=json.loads(row["signals"]) if row["signals"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
    
    # =========================================================================
    # INSIGHT METHODS
    # =========================================================================
    
    def save_insight(self, insight: Insight) -> None:
        """Save an insight to the database."""
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO insights
            (id, summary, themes, significance, confidence, source_ids, 
             excerpts, metadata, created_at, updated_at, pass_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            insight.id,
            insight.summary,
            json.dumps(insight.themes),
            insight.significance,
            insight.confidence,
            json.dumps(insight.source_ids),
            json.dumps(insight.excerpts),
            json.dumps(insight.metadata),
            insight.created_at.isoformat(),
            insight.updated_at.isoformat(),
            insight.pass_count,
        ))
        conn.commit()
    
    def get_insights(self, **filters) -> List[Insight]:
        """Get insights, optionally filtered."""
        conn = self._connect()
        cursor = conn.cursor()
        
        query = "SELECT * FROM insights WHERE 1=1"
        params = []
        
        if "min_significance" in filters:
            query += " AND significance >= ?"
            params.append(filters["min_significance"])
        
        if "min_confidence" in filters:
            query += " AND confidence >= ?"
            params.append(filters["min_confidence"])
        
        query += " ORDER BY significance DESC"
        
        if "limit" in filters:
            query += " LIMIT ?"
            params.append(filters["limit"])
        
        cursor.execute(query, params)
        return [self._row_to_insight(row) for row in cursor.fetchall()]
    
    def _row_to_insight(self, row) -> Insight:
        """Convert database row to Insight."""
        return Insight(
            id=row["id"],
            summary=row["summary"],
            themes=json.loads(row["themes"]),
            significance=row["significance"],
            confidence=row["confidence"],
            source_ids=json.loads(row["source_ids"]),
            excerpts=json.loads(row["excerpts"]) if row["excerpts"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            pass_count=row["pass_count"],
        )
    
    # =========================================================================
    # PATTERN METHODS
    # =========================================================================
    
    def save_pattern(self, pattern: Pattern) -> None:
        """Save a pattern to the database."""
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO patterns
            (id, summary, pattern_type, insight_ids, strength, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern.id,
            pattern.summary,
            pattern.pattern_type.value,
            json.dumps(pattern.insight_ids),
            pattern.strength,
            json.dumps(pattern.metadata),
            pattern.created_at.isoformat(),
        ))
        conn.commit()
    
    def get_patterns(self, **filters) -> List[Pattern]:
        """Get patterns, optionally filtered."""
        conn = self._connect()
        cursor = conn.cursor()
        
        query = "SELECT * FROM patterns ORDER BY strength DESC"
        cursor.execute(query)
        return [self._row_to_pattern(row) for row in cursor.fetchall()]
    
    def _row_to_pattern(self, row) -> Pattern:
        """Convert database row to Pattern."""
        return Pattern(
            id=row["id"],
            summary=row["summary"],
            pattern_type=PatternType(row["pattern_type"]),
            insight_ids=json.loads(row["insight_ids"]),
            strength=row["strength"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )
    
    # =========================================================================
    # SYNTHESIS METHODS
    # =========================================================================
    
    def save_synthesis(self, synthesis: Synthesis) -> None:
        """Save a synthesis to the database."""
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO syntheses
            (id, summary, synthesis_type, pattern_ids, significance, confidence, 
             metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            synthesis.id,
            synthesis.summary,
            synthesis.synthesis_type.value,
            json.dumps(synthesis.pattern_ids),
            synthesis.significance,
            synthesis.confidence,
            json.dumps(synthesis.metadata),
            synthesis.created_at.isoformat(),
        ))
        conn.commit()
    
    def get_syntheses(self, **filters) -> List[Synthesis]:
        """Get syntheses, optionally filtered."""
        conn = self._connect()
        cursor = conn.cursor()
        
        query = "SELECT * FROM syntheses ORDER BY significance DESC"
        cursor.execute(query)
        return [self._row_to_synthesis(row) for row in cursor.fetchall()]
    
    def _row_to_synthesis(self, row) -> Synthesis:
        """Convert database row to Synthesis."""
        return Synthesis(
            id=row["id"],
            summary=row["summary"],
            synthesis_type=SynthesisType(row["synthesis_type"]),
            pattern_ids=json.loads(row["pattern_ids"]),
            significance=row["significance"],
            confidence=row["confidence"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )
    
    # =========================================================================
    # CONTEXT METHODS
    # =========================================================================
    
    def set_context(self, context: str) -> None:
        """Set domain context for prompts."""
        self._context = context
    
    def get_context(self) -> Optional[str]:
        """Get domain context."""
        return self._context
    
    def get_existing_themes(self) -> List[str]:
        """Get all themes from existing insights."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT themes FROM insights")
        
        all_themes = set()
        for row in cursor.fetchall():
            themes = json.loads(row["themes"])
            all_themes.update(themes)
        
        return list(all_themes)
    
    # =========================================================================
    # STATE METHODS
    # =========================================================================
    
    def save_state(self, state: ProcessingState) -> None:
        """Save processing state."""
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO processing_state
            (corpus_id, current_tier, documents_processed, documents_total,
             insights_extracted, patterns_found, passes_completed, status,
             error, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state.corpus_id,
            state.current_tier,
            state.documents_processed,
            state.documents_total,
            state.insights_extracted,
            state.patterns_found,
            state.passes_completed,
            state.status.value,
            state.error,
            state.started_at.isoformat() if state.started_at else None,
            state.completed_at.isoformat() if state.completed_at else None,
        ))
        conn.commit()
    
    def load_state(self, corpus_id: str) -> Optional[ProcessingState]:
        """Load processing state."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processing_state WHERE corpus_id = ?", (corpus_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return ProcessingState(
            corpus_id=row["corpus_id"],
            current_tier=row["current_tier"],
            documents_processed=row["documents_processed"],
            documents_total=row["documents_total"],
            insights_extracted=row["insights_extracted"],
            patterns_found=row["patterns_found"],
            passes_completed=row["passes_completed"],
            status=ProcessingStatus(row["status"]),
            error=row["error"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )
    
    # =========================================================================
    # UTILITY
    # =========================================================================
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def stats(self) -> Dict[str, int]:
        """Get database statistics."""
        conn = self._connect()
        cursor = conn.cursor()
        
        return {
            "documents": cursor.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            "insights": cursor.execute("SELECT COUNT(*) FROM insights").fetchone()[0],
            "patterns": cursor.execute("SELECT COUNT(*) FROM patterns").fetchone()[0],
            "syntheses": cursor.execute("SELECT COUNT(*) FROM syntheses").fetchone()[0],
        }
    
    def __repr__(self) -> str:
        stats = self.stats() if self._conn else {}
        return f"SQLiteAdapter({self.db_path}, stats={stats})"


__all__ = ["SQLiteAdapter"]
'''
    
    dst = TARGET_BASE / "recog_engine" / "adapters" / "sqlite.py"
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(content)


def create_package_init():
    """Create main recog_engine/__init__.py."""
    print("  Creating recog_engine/__init__.py...")
    
    content = '''"""
ReCog Engine - Recursive Cognition Engine v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Commercial licenses available: brent@ehkolabs.io

ReCog is a standalone text analysis engine that extracts, correlates, 
and synthesises insights from unstructured text corpora.
"""

__version__ = '1.0.0'


from .core import (
    # Enums
    ProcessingStatus,
    PatternType,
    SynthesisType,
    # Core types
    Document,
    Insight,
    Pattern,
    Synthesis,
    # State
    ProcessingState,
    Corpus,
    # Config
    RecogConfig,
    # LLM interface
    LLMResponse,
    LLMProvider,
    MockLLMProvider,
    # Signal processing (Tier 0)
    SignalProcessor,
    process_text,
    process_document,
    # Extraction (Tier 1)
    Extractor,
    extract_from_text,
    # Correlation (Tier 2)
    Correlator,
    find_patterns,
    # Synthesis (Tier 3)
    Synthesizer,
    synthesise_patterns,
)

from .adapters import (
    RecogAdapter,
    MemoryAdapter,
    SQLiteAdapter,
)


__all__ = [
    '__version__',
    'ProcessingStatus', 'PatternType', 'SynthesisType',
    'Document', 'Insight', 'Pattern', 'Synthesis',
    'ProcessingState', 'Corpus', 'RecogConfig',
    'LLMResponse', 'LLMProvider', 'MockLLMProvider',
    'SignalProcessor', 'process_text', 'process_document',
    'Extractor', 'extract_from_text',
    'Correlator', 'find_patterns',
    'Synthesizer', 'synthesise_patterns',
    'RecogAdapter', 'MemoryAdapter', 'SQLiteAdapter',
]
'''
    
    dst = TARGET_BASE / "recog_engine" / "__init__.py"
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(content)


def create_project_files():
    """Create README, LICENSE, requirements.txt."""
    print("\n[5/6] Creating project files...")
    
    # README.md
    readme = '''# ReCog Engine

**Recursive Cognition Engine** - AI-powered text analysis that extracts, correlates, and synthesises insights from unstructured data.

## Overview

ReCog processes text through four tiers:

1. **Signal (Tier 0)** - Zero-cost keyword and pattern detection
2. **Extract (Tier 1)** - LLM-powered insight extraction  
3. **Correlate (Tier 2)** - Pattern detection across insights
4. **Synthesise (Tier 3)** - High-level conclusions and themes

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from recog_engine import Document, Extractor, SQLiteAdapter, RecogConfig

# Setup
adapter = SQLiteAdapter("recog.db")
adapter.initialize()

# Create document
doc = Document.create(
    content="Your text here...",
    source_type="document",
    source_ref="example.txt"
)
adapter.save_document(doc)

# Process (requires LLM provider - see docs)
# extractor = Extractor(llm_provider, RecogConfig())
# insights = extractor.extract(doc)
```

## Adapters

- **MemoryAdapter** - In-memory storage for testing
- **SQLiteAdapter** - Persistent SQLite database

## Configuration

See `RecogConfig` for all tuneable parameters including:
- LLM model selection per tier
- Quality thresholds
- Batch sizes
- Temperature settings

## License

AGPLv3 - See LICENSE file.

Commercial licenses available: brent@ehkolabs.io

## Author

Brent Lefebure / EhkoLabs
'''
    
    with open(TARGET_BASE.parent / "README.md", 'w', encoding='utf-8') as f:
        f.write(readme)
    print("  Created README.md")
    
    # LICENSE (AGPLv3)
    license_text = '''GNU AFFERO GENERAL PUBLIC LICENSE
Version 3, 19 November 2007

Copyright (c) 2025 Brent Lefebure / EhkoLabs

ReCog Engine - Recursive Cognition Engine

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

---

COMMERCIAL LICENSING

For commercial use without AGPL obligations, contact: brent@ehkolabs.io

---

For the complete AGPL v3 license text, see:
https://www.gnu.org/licenses/agpl-3.0.txt
'''
    
    with open(TARGET_BASE.parent / "LICENSE", 'w', encoding='utf-8') as f:
        f.write(license_text)
    print("  Created LICENSE")
    
    # requirements.txt
    requirements = '''# ReCog Engine Dependencies

# Core
anthropic>=0.18.0
openai>=1.12.0

# Data handling
pyyaml>=6.0

# PDF parsing (optional)
pypdf>=3.0.0
pdfplumber>=0.9.0

# Development
pytest>=7.0.0
'''
    
    with open(TARGET_BASE.parent / "requirements.txt", 'w', encoding='utf-8') as f:
        f.write(requirements)
    print("  Created requirements.txt")


def create_ingestion_init():
    """Create ingestion/__init__.py."""
    print("\n[6/6] Creating ingestion package...")
    
    content = '''"""
ReCog Ingestion - File Parsing and Chunking

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
"""

from .service import IngestionService
from .chunker import Chunker

__all__ = ["IngestionService", "Chunker"]
'''
    
    dst = TARGET_BASE / "ingestion" / "__init__.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Parsers init
    parsers_init = '''"""
ReCog Ingestion - Parsers

Copyright (c) 2025 Brent Lefebure / EhkoLabs
"""

from .pdf import PDFParser
from .markdown import MarkdownParser
from .plaintext import PlaintextParser
from .messages import MessagesParser

__all__ = ["PDFParser", "MarkdownParser", "PlaintextParser", "MessagesParser"]
'''
    
    dst = TARGET_BASE / "ingestion" / "parsers" / "__init__.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(parsers_init)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the migration."""
    print("=" * 60)
    print("ReCog Migration Script")
    print(f"Source: {SOURCE_BASE}")
    print(f"Target: {TARGET_BASE}")
    print("=" * 60)
    
    # Ensure target directories exist
    (TARGET_BASE / "recog_engine" / "core").mkdir(parents=True, exist_ok=True)
    (TARGET_BASE / "recog_engine" / "adapters").mkdir(parents=True, exist_ok=True)
    (TARGET_BASE / "ingestion" / "parsers").mkdir(parents=True, exist_ok=True)
    
    # Run migration steps
    copy_core_files()
    copy_adapter_files()
    copy_ingestion_files()
    create_adapters_init()
    create_sqlite_adapter()
    create_package_init()
    create_project_files()
    create_ingestion_init()
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review copied files")
    print("2. Test imports: python -c \"from recog_engine import *\"")
    print("3. Run: pip install -r requirements.txt")


if __name__ == "__main__":
    main()

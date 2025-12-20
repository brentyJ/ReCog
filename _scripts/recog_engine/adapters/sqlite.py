"""
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

"""
ReCog Adapters - Memory Adapter

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

In-memory adapter for testing and standalone use.
Stores all data in memory - no persistence.
"""

from typing import List, Optional, Iterator, Dict, Any
from datetime import datetime

from .base import RecogAdapter
from recog_engine.core.types import (
    Document,
    Insight,
    Pattern,
    Synthesis,
    ProcessingState,
)


class MemoryAdapter(RecogAdapter):
    """
    In-memory adapter for testing and standalone use.
    
    All data is stored in dictionaries - nothing persists
    after the adapter is destroyed.
    
    Usage:
        adapter = MemoryAdapter()
        adapter.add_document(Document.create(
            content="Some text to analyse",
            source_type="note",
            source_ref="test.txt"
        ))
        
        engine = RecogEngine(adapter, config)
        engine.process_corpus("test-run")
        
        insights = adapter.get_insights()
    """
    
    def __init__(self):
        """Initialise empty storage."""
        self._documents: Dict[str, Document] = {}
        self._insights: Dict[str, Insight] = {}
        self._patterns: Dict[str, Pattern] = {}
        self._syntheses: Dict[str, Synthesis] = {}
        self._states: Dict[str, ProcessingState] = {}
        self._context: Optional[str] = None
        self._themes: List[str] = []
    
    # =========================================================================
    # DOCUMENT MANAGEMENT
    # =========================================================================
    
    def add_document(self, document: Document) -> None:
        """
        Add a document to the store.
        
        Args:
            document: Document to add
        """
        self._documents[document.id] = document
    
    def add_documents(self, documents: List[Document]) -> None:
        """
        Add multiple documents to the store.
        
        Args:
            documents: List of documents to add
        """
        for doc in documents:
            self._documents[doc.id] = doc
    
    def load_documents(self, **filters) -> Iterator[Document]:
        """
        Yield documents, optionally filtered.
        
        Supported filters:
            source_type: Filter by source type
            since: Filter by created_at >= datetime
            until: Filter by created_at <= datetime
        """
        source_type = filters.get("source_type")
        since = filters.get("since")
        until = filters.get("until")
        
        for doc in self._documents.values():
            if source_type and doc.source_type != source_type:
                continue
            if since and doc.created_at < since:
                continue
            if until and doc.created_at > until:
                continue
            yield doc
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get document by ID."""
        return self._documents.get(doc_id)
    
    def count_documents(self, **filters) -> int:
        """Count documents matching filters."""
        return sum(1 for _ in self.load_documents(**filters))
    
    def clear_documents(self) -> None:
        """Remove all documents."""
        self._documents.clear()
    
    # =========================================================================
    # INSIGHT MANAGEMENT
    # =========================================================================
    
    def save_insight(self, insight: Insight) -> None:
        """Save or update an insight."""
        self._insights[insight.id] = insight
    
    def get_insights(self, **filters) -> List[Insight]:
        """
        Get insights, optionally filtered.
        
        Supported filters:
            min_significance: Filter by significance >= threshold
            themes: Filter by any theme match
            source_id: Filter by source document
        """
        min_sig = filters.get("min_significance")
        themes = filters.get("themes")
        source_id = filters.get("source_id")
        
        results = []
        for insight in self._insights.values():
            if min_sig and insight.significance < min_sig:
                continue
            if themes and not set(themes) & set(insight.themes):
                continue
            if source_id and source_id not in insight.source_ids:
                continue
            results.append(insight)
        
        return results
    
    def get_insight(self, insight_id: str) -> Optional[Insight]:
        """Get insight by ID."""
        return self._insights.get(insight_id)
    
    def clear_insights(self) -> None:
        """Remove all insights."""
        self._insights.clear()
    
    # =========================================================================
    # PATTERN MANAGEMENT
    # =========================================================================
    
    def save_pattern(self, pattern: Pattern) -> None:
        """Save or update a pattern."""
        self._patterns[pattern.id] = pattern
    
    def get_patterns(self, **filters) -> List[Pattern]:
        """
        Get patterns, optionally filtered.
        
        Supported filters:
            pattern_type: Filter by PatternType
            min_strength: Filter by strength >= threshold
            insight_id: Filter by linked insight
        """
        pattern_type = filters.get("pattern_type")
        min_strength = filters.get("min_strength")
        insight_id = filters.get("insight_id")
        
        results = []
        for pattern in self._patterns.values():
            if pattern_type and pattern.pattern_type != pattern_type:
                continue
            if min_strength and pattern.strength < min_strength:
                continue
            if insight_id and insight_id not in pattern.insight_ids:
                continue
            results.append(pattern)
        
        return results
    
    def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        """Get pattern by ID."""
        return self._patterns.get(pattern_id)
    
    def clear_patterns(self) -> None:
        """Remove all patterns."""
        self._patterns.clear()
    
    # =========================================================================
    # SYNTHESIS MANAGEMENT
    # =========================================================================
    
    def save_synthesis(self, synthesis: Synthesis) -> None:
        """Save or update a synthesis."""
        self._syntheses[synthesis.id] = synthesis
    
    def get_syntheses(self, **filters) -> List[Synthesis]:
        """
        Get syntheses, optionally filtered.
        
        Supported filters:
            synthesis_type: Filter by SynthesisType
        """
        synthesis_type = filters.get("synthesis_type")
        
        results = []
        for synthesis in self._syntheses.values():
            if synthesis_type and synthesis.synthesis_type != synthesis_type:
                continue
            results.append(synthesis)
        
        return results
    
    def clear_syntheses(self) -> None:
        """Remove all syntheses."""
        self._syntheses.clear()
    
    # =========================================================================
    # CONTEXT MANAGEMENT
    # =========================================================================
    
    def set_context(self, context: str) -> None:
        """
        Set domain context for prompts.
        
        Args:
            context: Context string to include in extraction prompts
        """
        self._context = context
    
    def get_context(self) -> Optional[str]:
        """Get domain context."""
        return self._context
    
    def set_themes(self, themes: List[str]) -> None:
        """
        Set known themes for consistency.
        
        Args:
            themes: List of theme strings
        """
        self._themes = themes
    
    def get_existing_themes(self) -> List[str]:
        """Get known themes, including those from insights."""
        # Combine explicit themes with those found in insights
        insight_themes = set()
        for insight in self._insights.values():
            insight_themes.update(insight.themes)
        
        return list(set(self._themes) | insight_themes)
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def save_state(self, state: ProcessingState) -> None:
        """Save processing state."""
        self._states[state.corpus_id] = state
    
    def load_state(self, corpus_id: str) -> Optional[ProcessingState]:
        """Load processing state."""
        return self._states.get(corpus_id)
    
    # =========================================================================
    # UTILITY
    # =========================================================================
    
    def clear_all(self) -> None:
        """Clear all stored data."""
        self._documents.clear()
        self._insights.clear()
        self._patterns.clear()
        self._syntheses.clear()
        self._states.clear()
        self._context = None
        self._themes.clear()
    
    def stats(self) -> Dict[str, int]:
        """Get storage statistics."""
        return {
            "documents": len(self._documents),
            "insights": len(self._insights),
            "patterns": len(self._patterns),
            "syntheses": len(self._syntheses),
        }
    
    def __repr__(self) -> str:
        stats = self.stats()
        return (
            f"MemoryAdapter("
            f"documents={stats['documents']}, "
            f"insights={stats['insights']}, "
            f"patterns={stats['patterns']}, "
            f"syntheses={stats['syntheses']})"
        )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = ["MemoryAdapter"]

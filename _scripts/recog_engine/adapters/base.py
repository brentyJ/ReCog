"""
ReCog Adapters - Base Adapter Interface

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Abstract base class defining the adapter interface.
Adapters connect ReCog to specific applications by handling:
- Input: Loading documents into the engine
- Output: Storing/displaying results
- Context: Providing domain-specific knowledge
- Persistence: Saving state between runs
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Iterator, Dict, Any

from recog_engine.core.types import (
    Document,
    Insight,
    Pattern,
    Synthesis,
    ProcessingState,
)


class RecogAdapter(ABC):
    """
    Abstract base class for ReCog adapters.
    
    Implement this class to connect ReCog to your application.
    The adapter is responsible for all I/O - ReCog core only
    processes data, it doesn't know where it comes from or
    where it goes.
    """
    
    # =========================================================================
    # INPUT: Loading documents
    # =========================================================================
    
    @abstractmethod
    def load_documents(self, **filters) -> Iterator[Document]:
        """
        Yield documents to process.
        
        Args:
            **filters: Adapter-specific filters (date range, source type, etc.)
            
        Yields:
            Document objects to process
        """
        pass
    
    @abstractmethod
    def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Retrieve a specific document by ID.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Document if found, None otherwise
        """
        pass
    
    def count_documents(self, **filters) -> int:
        """
        Count documents matching filters.
        
        Default implementation iterates - override for efficiency.
        
        Args:
            **filters: Same filters as load_documents
            
        Returns:
            Number of matching documents
        """
        return sum(1 for _ in self.load_documents(**filters))
    
    # =========================================================================
    # OUTPUT: Storing results
    # =========================================================================
    
    @abstractmethod
    def save_insight(self, insight: Insight) -> None:
        """
        Persist an extracted insight.
        
        Args:
            insight: Insight to save
        """
        pass
    
    @abstractmethod
    def save_pattern(self, pattern: Pattern) -> None:
        """
        Persist a detected pattern.
        
        Args:
            pattern: Pattern to save
        """
        pass
    
    @abstractmethod
    def save_synthesis(self, synthesis: Synthesis) -> None:
        """
        Persist a synthesis.
        
        Args:
            synthesis: Synthesis to save
        """
        pass
    
    @abstractmethod
    def get_insights(self, **filters) -> List[Insight]:
        """
        Retrieve insights, optionally filtered.
        
        Args:
            **filters: Adapter-specific filters
            
        Returns:
            List of matching insights
        """
        pass
    
    @abstractmethod
    def get_patterns(self, **filters) -> List[Pattern]:
        """
        Retrieve patterns, optionally filtered.
        
        Args:
            **filters: Adapter-specific filters
            
        Returns:
            List of matching patterns
        """
        pass
    
    def get_syntheses(self, **filters) -> List[Synthesis]:
        """
        Retrieve syntheses, optionally filtered.
        
        Args:
            **filters: Adapter-specific filters
            
        Returns:
            List of matching syntheses
        """
        return []
    
    def get_insight(self, insight_id: str) -> Optional[Insight]:
        """
        Retrieve a specific insight by ID.
        
        Default implementation searches all insights - override for efficiency.
        
        Args:
            insight_id: Insight identifier
            
        Returns:
            Insight if found, None otherwise
        """
        for insight in self.get_insights():
            if insight.id == insight_id:
                return insight
        return None
    
    def update_insight(self, insight: Insight) -> None:
        """
        Update an existing insight.
        
        Default implementation just saves - override if needed.
        
        Args:
            insight: Insight with updated data
        """
        self.save_insight(insight)
    
    # =========================================================================
    # CONTEXT: Domain knowledge (optional)
    # =========================================================================
    
    def get_context(self) -> Optional[str]:
        """
        Return domain context to include in LLM prompts.
        
        Examples:
        - EhkoForge: Identity pillars, core memories
        - Enterprise: Company glossary, project background
        - Research: Prior findings, hypotheses
        
        Returns:
            Context string or None if no context available
        """
        return None
    
    def get_existing_themes(self) -> List[str]:
        """
        Return known themes for consistency.
        
        Helps extraction use consistent terminology across
        multiple processing runs.
        
        Returns:
            List of theme strings
        """
        return []
    
    # =========================================================================
    # STATE: Processing persistence (optional)
    # =========================================================================
    
    def save_state(self, state: ProcessingState) -> None:
        """
        Persist processing state.
        
        Override to enable resume functionality.
        
        Args:
            state: Current processing state
        """
        pass
    
    def load_state(self, corpus_id: str) -> Optional[ProcessingState]:
        """
        Load processing state.
        
        Override to enable resume functionality.
        
        Args:
            corpus_id: Identifier for the processing run
            
        Returns:
            ProcessingState if found, None otherwise
        """
        return None
    
    # =========================================================================
    # LIFECYCLE (optional)
    # =========================================================================
    
    def on_processing_start(self, corpus_id: str) -> None:
        """
        Called when processing begins.
        
        Override for setup tasks (logging, notifications, etc.)
        
        Args:
            corpus_id: Identifier for this processing run
        """
        pass
    
    def on_processing_complete(self, corpus_id: str, state: ProcessingState) -> None:
        """
        Called when processing completes.
        
        Override for cleanup tasks (notifications, reports, etc.)
        
        Args:
            corpus_id: Identifier for this processing run
            state: Final processing state
        """
        pass
    
    def on_processing_error(self, corpus_id: str, error: Exception) -> None:
        """
        Called when processing fails.
        
        Override for error handling (logging, notifications, etc.)
        
        Args:
            corpus_id: Identifier for this processing run
            error: The exception that occurred
        """
        pass


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = ["RecogAdapter"]

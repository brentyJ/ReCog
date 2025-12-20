"""
ReCog Core - Type Definitions v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Core data types for the ReCog recursive insight engine.
All types are plain Python dataclasses, JSON-serialisable, 
with no external dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
import json
import uuid


# =============================================================================
# ENUMS
# =============================================================================

class ProcessingStatus(Enum):
    """Status of a processing run."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PatternType(Enum):
    """Types of patterns detected across insights."""
    RECURRING = "recurring"        # Same theme appears multiple times
    CONTRADICTION = "contradiction" # Conflicting insights
    EVOLUTION = "evolution"        # Theme changes over time
    CLUSTER = "cluster"            # Related without temporal relationship


class SynthesisType(Enum):
    """Types of synthesis output."""
    TRAIT = "trait"                # Personality characteristic
    BELIEF = "belief"              # Core belief or value
    TENDENCY = "tendency"          # Behavioural pattern
    THEME = "theme"                # Recurring life theme


# =============================================================================
# CORE DATA TYPES
# =============================================================================

@dataclass
class Document:
    """
    A single unit of text to be processed.
    
    This is the input type - raw text with metadata.
    Documents are processed to extract Insights.
    """
    id: str
    content: str
    source_type: str              # e.g., "transcript", "document", "chat"
    source_ref: str               # Original location/identifier
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    signals: Optional[Dict[str, Any]] = None  # Tier 0 output
    
    @classmethod
    def create(cls, content: str, source_type: str, source_ref: str,
               metadata: Dict[str, Any] = None) -> "Document":
        """Factory method with auto-generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            content=content,
            source_type=source_type,
            source_ref=source_ref,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "signals": self.signals,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Deserialise from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            source_type=data["source_type"],
            source_ref=data["source_ref"],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            signals=data.get("signals"),
        )


@dataclass
class Insight:
    """
    A discrete insight extracted from one or more documents.
    
    This is the primary output of Tier 1 (Extraction).
    Insights are correlated in Tier 2 to form Patterns.
    """
    id: str
    summary: str                  # 1-3 sentence distillation
    themes: List[str]             # Categorical tags
    significance: float           # 0.0-1.0 importance score
    confidence: float             # 0.0-1.0 extraction confidence
    source_ids: List[str]         # Document IDs this came from
    excerpts: List[str]           # Supporting quotes
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    pass_count: int = 1           # How many extraction passes
    
    @classmethod
    def create(cls, summary: str, themes: List[str], significance: float,
               confidence: float, source_ids: List[str], excerpts: List[str] = None,
               metadata: Dict[str, Any] = None) -> "Insight":
        """Factory method with auto-generated ID."""
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            summary=summary,
            themes=themes,
            significance=significance,
            confidence=confidence,
            source_ids=source_ids,
            excerpts=excerpts or [],
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
    
    def merge_with(self, other: "Insight") -> None:
        """
        Merge another insight into this one.
        
        Used when detecting duplicates/similar insights.
        """
        # Combine sources
        self.source_ids = list(set(self.source_ids + other.source_ids))
        self.excerpts = list(set(self.excerpts + other.excerpts))
        
        # Merge themes
        self.themes = list(set(self.themes + other.themes))
        
        # Boost significance slightly for corroborated insights
        self.significance = min(1.0, (self.significance + other.significance) / 2 + 0.05)
        
        # Average confidence
        self.confidence = (self.confidence + other.confidence) / 2
        
        # Increment pass count
        self.pass_count += 1
        
        # Update timestamp
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            "id": self.id,
            "summary": self.summary,
            "themes": self.themes,
            "significance": self.significance,
            "confidence": self.confidence,
            "source_ids": self.source_ids,
            "excerpts": self.excerpts,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "pass_count": self.pass_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Insight":
        """Deserialise from dictionary."""
        return cls(
            id=data["id"],
            summary=data["summary"],
            themes=data["themes"],
            significance=data["significance"],
            confidence=data["confidence"],
            source_ids=data["source_ids"],
            excerpts=data.get("excerpts", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            pass_count=data.get("pass_count", 1),
        )


@dataclass
class Pattern:
    """
    A connection or theme across multiple insights.
    
    This is the output of Tier 2 (Correlation).
    Patterns are synthesised in Tier 3.
    """
    id: str
    summary: str                  # Pattern description
    pattern_type: PatternType     # recurring, contradiction, evolution, cluster
    insight_ids: List[str]        # Insights that form this pattern
    strength: float               # 0.0-1.0 pattern strength
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def create(cls, summary: str, pattern_type: PatternType,
               insight_ids: List[str], strength: float,
               metadata: Dict[str, Any] = None) -> "Pattern":
        """Factory method with auto-generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            summary=summary,
            pattern_type=pattern_type,
            insight_ids=insight_ids,
            strength=strength,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            "id": self.id,
            "summary": self.summary,
            "pattern_type": self.pattern_type.value,
            "insight_ids": self.insight_ids,
            "strength": self.strength,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pattern":
        """Deserialise from dictionary."""
        return cls(
            id=data["id"],
            summary=data["summary"],
            pattern_type=PatternType(data["pattern_type"]),
            insight_ids=data["insight_ids"],
            strength=data["strength"],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class Synthesis:
    """
    High-level conclusion from pattern analysis.
    
    This is the output of Tier 3 (Synthesis).
    """
    id: str
    summary: str                  # 2-4 sentence synthesis
    synthesis_type: SynthesisType # trait, belief, tendency, theme
    pattern_ids: List[str]        # Patterns contributing to this
    significance: float           # 0.0-1.0 how central this is
    confidence: float             # 0.0-1.0 synthesis confidence
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def create(cls, summary: str, synthesis_type: SynthesisType,
               pattern_ids: List[str], significance: float = 0.5,
               confidence: float = 0.5,
               metadata: Dict[str, Any] = None) -> "Synthesis":
        """Factory method with auto-generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            summary=summary,
            synthesis_type=synthesis_type,
            pattern_ids=pattern_ids,
            significance=significance,
            confidence=confidence,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            "id": self.id,
            "summary": self.summary,
            "synthesis_type": self.synthesis_type.value,
            "pattern_ids": self.pattern_ids,
            "significance": self.significance,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Synthesis":
        """Deserialise from dictionary."""
        return cls(
            id=data["id"],
            summary=data["summary"],
            synthesis_type=SynthesisType(data["synthesis_type"]),
            pattern_ids=data["pattern_ids"],
            significance=data.get("significance", 0.5),
            confidence=data.get("confidence", 0.5),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


# =============================================================================
# PROCESSING STATE
# =============================================================================

@dataclass
class ProcessingState:
    """
    Tracks processing progress for a corpus.
    
    Used by the engine to manage and resume processing runs.
    """
    corpus_id: str
    current_tier: int             # 0-3
    documents_processed: int
    documents_total: int
    insights_extracted: int
    patterns_found: int
    passes_completed: int
    status: ProcessingStatus
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @classmethod
    def create(cls, corpus_id: str, documents_total: int) -> "ProcessingState":
        """Create initial processing state."""
        return cls(
            corpus_id=corpus_id,
            current_tier=0,
            documents_processed=0,
            documents_total=documents_total,
            insights_extracted=0,
            patterns_found=0,
            passes_completed=0,
            status=ProcessingStatus.PENDING,
        )
    
    def start(self) -> None:
        """Mark processing as started."""
        self.status = ProcessingStatus.PROCESSING
        self.started_at = datetime.utcnow()
    
    def complete(self) -> None:
        """Mark processing as complete."""
        self.status = ProcessingStatus.COMPLETE
        self.completed_at = datetime.utcnow()
    
    def fail(self, error: str) -> None:
        """Mark processing as failed."""
        self.status = ProcessingStatus.FAILED
        self.error = error
        self.completed_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            "corpus_id": self.corpus_id,
            "current_tier": self.current_tier,
            "documents_processed": self.documents_processed,
            "documents_total": self.documents_total,
            "insights_extracted": self.insights_extracted,
            "patterns_found": self.patterns_found,
            "passes_completed": self.passes_completed,
            "status": self.status.value,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingState":
        """Deserialise from dictionary."""
        return cls(
            corpus_id=data["corpus_id"],
            current_tier=data["current_tier"],
            documents_processed=data["documents_processed"],
            documents_total=data["documents_total"],
            insights_extracted=data["insights_extracted"],
            patterns_found=data["patterns_found"],
            passes_completed=data["passes_completed"],
            status=ProcessingStatus(data["status"]),
            error=data.get("error"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )


# =============================================================================
# CORPUS (CONVENIENCE CONTAINER)
# =============================================================================

@dataclass
class Corpus:
    """
    A collection of documents being processed together.
    
    This is a convenience container - adapters may choose to
    use it or manage documents/insights/patterns separately.
    """
    id: str
    name: str
    documents: List[Document] = field(default_factory=list)
    insights: List[Insight] = field(default_factory=list)
    patterns: List[Pattern] = field(default_factory=list)
    syntheses: List[Synthesis] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def create(cls, name: str, config: Dict[str, Any] = None) -> "Corpus":
        """Factory method with auto-generated ID."""
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            config=config or {},
            created_at=now,
            updated_at=now,
        )
    
    def add_document(self, doc: Document) -> None:
        """Add a document to the corpus."""
        self.documents.append(doc)
        self.updated_at = datetime.utcnow()
    
    def add_insight(self, insight: Insight) -> None:
        """Add an insight to the corpus."""
        self.insights.append(insight)
        self.updated_at = datetime.utcnow()
    
    def add_pattern(self, pattern: Pattern) -> None:
        """Add a pattern to the corpus."""
        self.patterns.append(pattern)
        self.updated_at = datetime.utcnow()
    
    def add_synthesis(self, synthesis: Synthesis) -> None:
        """Add a synthesis to the corpus."""
        self.syntheses.append(synthesis)
        self.updated_at = datetime.utcnow()
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get document by ID."""
        for doc in self.documents:
            if doc.id == doc_id:
                return doc
        return None
    
    def get_insight(self, insight_id: str) -> Optional[Insight]:
        """Get insight by ID."""
        for insight in self.insights:
            if insight.id == insight_id:
                return insight
        return None


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "ProcessingStatus",
    "PatternType", 
    "SynthesisType",
    # Core types
    "Document",
    "Insight",
    "Pattern",
    "Synthesis",
    # State
    "ProcessingState",
    "Corpus",
]

"""
ReCog Core - Configuration v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Engine configuration for ReCog processing.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import json
from pathlib import Path


@dataclass
class RecogConfig:
    """
    Configuration for ReCog engine processing.
    
    All thresholds and limits are tuneable. Defaults are sensible
    starting points based on testing.
    """
    
    # =========================================================================
    # TIER 0: SIGNAL
    # =========================================================================
    
    signal_enabled: bool = True
    
    # =========================================================================
    # TIER 1: EXTRACTION
    # =========================================================================
    
    # LLM settings
    extraction_model: str = "gpt-4o-mini"      # Low-cost, high-volume
    extraction_temperature: float = 0.3        # Lower = more consistent
    extraction_max_tokens: int = 2000
    
    # Batch processing
    extraction_batch_size: int = 10            # Documents per batch
    extraction_max_passes: int = 3             # Max refinement passes
    
    # Content limits
    max_content_chars: int = 8000              # Truncate beyond this
    min_content_words: int = 10                # Skip documents shorter than this
    
    # Quality thresholds
    min_confidence: float = 0.3                # Discard insights below this
    min_significance: float = 0.2              # Discard insights below this
    
    # Deduplication
    similarity_threshold: float = 0.7          # Merge insights above this
    
    # =========================================================================
    # TIER 2: CORRELATION
    # =========================================================================
    
    correlation_model: str = "claude-sonnet-4-20250514"
    correlation_temperature: float = 0.4
    correlation_max_tokens: int = 3000
    
    correlation_min_cluster: int = 3           # Min insights for theme group
    correlation_max_passes: int = 2            # Correlation loop iterations
    correlation_yield_threshold: float = 0.05  # Stop if < 5% new connections
    
    # =========================================================================
    # TIER 3: SYNTHESIS
    # =========================================================================
    
    synthesis_model: str = "claude-sonnet-4-20250514"
    synthesis_temperature: float = 0.5
    synthesis_max_tokens: int = 4000
    
    synthesis_min_patterns: int = 1            # Min patterns for synthesis (lowered from 2)
    synthesis_significance_threshold: float = 0.5
    
    # =========================================================================
    # GENERAL
    # =========================================================================
    
    # Processing
    max_insights_per_document: int = 5         # Cap extraction per doc
    
    # Context injection
    include_adapter_context: bool = True       # Use adapter.get_context()
    include_existing_themes: bool = True       # Use adapter.get_existing_themes()
    
    # =========================================================================
    # METHODS
    # =========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            # Tier 0
            "signal_enabled": self.signal_enabled,
            # Tier 1
            "extraction_model": self.extraction_model,
            "extraction_temperature": self.extraction_temperature,
            "extraction_max_tokens": self.extraction_max_tokens,
            "extraction_batch_size": self.extraction_batch_size,
            "extraction_max_passes": self.extraction_max_passes,
            "max_content_chars": self.max_content_chars,
            "min_content_words": self.min_content_words,
            "min_confidence": self.min_confidence,
            "min_significance": self.min_significance,
            "similarity_threshold": self.similarity_threshold,
            # Tier 2
            "correlation_model": self.correlation_model,
            "correlation_temperature": self.correlation_temperature,
            "correlation_max_tokens": self.correlation_max_tokens,
            "correlation_min_cluster": self.correlation_min_cluster,
            "correlation_max_passes": self.correlation_max_passes,
            "correlation_yield_threshold": self.correlation_yield_threshold,
            # Tier 3
            "synthesis_model": self.synthesis_model,
            "synthesis_temperature": self.synthesis_temperature,
            "synthesis_max_tokens": self.synthesis_max_tokens,
            "synthesis_min_patterns": self.synthesis_min_patterns,
            "synthesis_significance_threshold": self.synthesis_significance_threshold,
            # General
            "max_insights_per_document": self.max_insights_per_document,
            "include_adapter_context": self.include_adapter_context,
            "include_existing_themes": self.include_existing_themes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecogConfig":
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
    
    def save(self, path: Path) -> None:
        """Save config to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "RecogConfig":
        """Load config from JSON file."""
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))
    
    @classmethod
    def for_testing(cls) -> "RecogConfig":
        """Create config optimised for testing (lower thresholds)."""
        return cls(
            min_confidence=0.1,
            min_significance=0.1,
            similarity_threshold=0.8,
            extraction_batch_size=5,
        )
    
    @classmethod
    def for_production(cls) -> "RecogConfig":
        """Create config optimised for production (higher quality)."""
        return cls(
            min_confidence=0.5,
            min_significance=0.4,
            similarity_threshold=0.7,
            extraction_batch_size=10,
        )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = ["RecogConfig"]

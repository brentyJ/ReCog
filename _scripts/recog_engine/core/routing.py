"""
ReCog Core - Provider Routing v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Intelligent routing between LLM providers based on content characteristics.
Optimises cost-to-insight ratio by using expensive models only when justified.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from .providers import create_provider, get_available_providers
from .llm import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


# =============================================================================
# ROUTING CONFIGURATION
# =============================================================================

@dataclass
class RoutingConfig:
    """
    Configuration for provider routing decisions.
    
    All thresholds are tuneable based on empirical testing.
    See _docs/LLM_RESEARCH_LOG.md for findings.
    """
    
    # Default providers by role
    extraction_provider: str = "openai"      # High-volume, cost-efficient
    synthesis_provider: str = "anthropic"    # Complex reasoning
    correlation_provider: str = "anthropic"  # Pattern recognition
    
    # Upgrade triggers - when to use premium provider for extraction
    upgrade_on_high_emotion: bool = True
    upgrade_on_significance_threshold: float = 0.7  # First-pass significance
    upgrade_source_types: List[str] = None  # e.g., ["therapy", "journal"]
    
    # Cost controls
    max_anthropic_per_session: int = 50     # Cap premium calls per session
    anthropic_budget_cents: float = 100.0   # Max spend on premium per session
    
    def __post_init__(self):
        if self.upgrade_source_types is None:
            self.upgrade_source_types = ["therapy", "journal", "personal"]


# =============================================================================
# ROUTING LOGIC
# =============================================================================

class ProviderRouter:
    """
    Routes requests to appropriate LLM provider based on content and context.
    
    Tracks usage to enforce cost limits.
    """
    
    def __init__(self, config: RoutingConfig = None):
        self.config = config or RoutingConfig()
        self.available = get_available_providers()
        
        # Session tracking
        self._anthropic_calls = 0
        self._anthropic_spend_cents = 0.0
        self._total_calls = 0
        
        logger.info(f"ProviderRouter initialised. Available: {self.available}")
    
    def get_extraction_provider(
        self,
        tier0_result: Dict[str, Any] = None,
        source_type: str = None,
        first_pass_significance: float = None,
        force_provider: str = None,
    ) -> LLMProvider:
        """
        Get appropriate provider for extraction based on content signals.
        
        Args:
            tier0_result: Pre-annotation from Tier 0 processing
            source_type: Document source type
            first_pass_significance: Significance from initial extraction (for re-processing)
            force_provider: Override routing logic
            
        Returns:
            LLMProvider instance
        """
        # Explicit override
        if force_provider:
            return create_provider(force_provider)
        
        # Check if premium provider available and within budget
        can_use_premium = self._can_use_premium()
        
        if not can_use_premium:
            logger.debug("Premium provider unavailable or budget exceeded")
            return create_provider(self.config.extraction_provider)
        
        # Check upgrade triggers
        should_upgrade = False
        upgrade_reason = None
        
        # Trigger 1: High emotion flag
        if self.config.upgrade_on_high_emotion and tier0_result:
            flags = tier0_result.get("flags", {})
            if flags.get("high_emotion"):
                should_upgrade = True
                upgrade_reason = "high_emotion flag"
        
        # Trigger 2: Source type
        if source_type and source_type.lower() in self.config.upgrade_source_types:
            should_upgrade = True
            upgrade_reason = f"source_type={source_type}"
        
        # Trigger 3: Re-processing high-significance item
        if first_pass_significance and first_pass_significance >= self.config.upgrade_on_significance_threshold:
            should_upgrade = True
            upgrade_reason = f"significance={first_pass_significance}"
        
        if should_upgrade:
            logger.info(f"Upgrading to premium provider: {upgrade_reason}")
            self._anthropic_calls += 1
            return create_provider("anthropic")
        
        return create_provider(self.config.extraction_provider)
    
    def get_synthesis_provider(self) -> LLMProvider:
        """Get provider for synthesis tasks (always premium if available)."""
        if "anthropic" in self.available:
            return create_provider("anthropic")
        return create_provider(self.config.extraction_provider)
    
    def get_correlation_provider(self) -> LLMProvider:
        """Get provider for correlation tasks."""
        if "anthropic" in self.available:
            return create_provider("anthropic")
        return create_provider(self.config.extraction_provider)
    
    def _can_use_premium(self) -> bool:
        """Check if premium provider is available and within budget."""
        if "anthropic" not in self.available:
            return False
        
        if self._anthropic_calls >= self.config.max_anthropic_per_session:
            logger.warning(f"Anthropic call limit reached: {self._anthropic_calls}")
            return False
        
        if self._anthropic_spend_cents >= self.config.anthropic_budget_cents:
            logger.warning(f"Anthropic budget exceeded: ${self._anthropic_spend_cents/100:.2f}")
            return False
        
        return True
    
    def record_usage(self, provider: str, tokens: int, cost_cents: float = None):
        """Record usage for budget tracking."""
        self._total_calls += 1
        
        if provider == "anthropic":
            self._anthropic_calls += 1
            if cost_cents:
                self._anthropic_spend_cents += cost_cents
            else:
                # Estimate cost if not provided
                # Approx $0.008 per 1K tokens for Sonnet
                estimated_cost = (tokens / 1000) * 0.8
                self._anthropic_spend_cents += estimated_cost
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current session usage statistics."""
        return {
            "total_calls": self._total_calls,
            "anthropic_calls": self._anthropic_calls,
            "anthropic_spend_cents": round(self._anthropic_spend_cents, 2),
            "anthropic_budget_remaining": round(
                self.config.anthropic_budget_cents - self._anthropic_spend_cents, 2
            ),
            "anthropic_calls_remaining": self.config.max_anthropic_per_session - self._anthropic_calls,
        }
    
    def reset_session(self):
        """Reset session counters (call at start of new processing batch)."""
        self._anthropic_calls = 0
        self._anthropic_spend_cents = 0.0
        self._total_calls = 0


# =============================================================================
# COST ESTIMATION
# =============================================================================

# Approximate costs per 1K tokens (as of Dec 2024)
COST_PER_1K = {
    "openai": {
        "gpt-4o-mini": {"input": 0.015, "output": 0.06},  # cents
        "gpt-4o": {"input": 0.25, "output": 1.0},
    },
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 0.3, "output": 1.5},
        "claude-3-5-sonnet-20241022": {"input": 0.3, "output": 1.5},
    },
}


def estimate_extraction_cost(
    word_count: int,
    provider: str = "openai",
    model: str = None,
) -> float:
    """
    Estimate cost in cents for extracting from content.
    
    Assumes ~1.3 tokens per word for input, ~400 tokens output.
    """
    if model is None:
        model = "gpt-4o-mini" if provider == "openai" else "claude-sonnet-4-20250514"
    
    input_tokens = int(word_count * 1.3) + 500  # Content + prompt overhead
    output_tokens = 400  # Typical extraction response
    
    costs = COST_PER_1K.get(provider, {}).get(model, {"input": 0.1, "output": 0.5})
    
    input_cost = (input_tokens / 1000) * costs["input"]
    output_cost = (output_tokens / 1000) * costs["output"]
    
    return round(input_cost + output_cost, 4)


def estimate_batch_cost(
    documents: List[Dict],
    routing_config: RoutingConfig = None,
) -> Dict[str, Any]:
    """
    Estimate total cost for processing a batch of documents.
    
    Args:
        documents: List of {"word_count": N, "source_type": str, "tier0": {...}}
        routing_config: Routing configuration
        
    Returns:
        Cost breakdown with min/max scenarios
    """
    config = routing_config or RoutingConfig()
    
    openai_count = 0
    anthropic_count = 0
    
    for doc in documents:
        # Simulate routing decision
        would_upgrade = False
        
        source_type = doc.get("source_type", "")
        if source_type.lower() in config.upgrade_source_types:
            would_upgrade = True
        
        tier0 = doc.get("tier0", {})
        if tier0.get("flags", {}).get("high_emotion"):
            would_upgrade = True
        
        if would_upgrade and anthropic_count < config.max_anthropic_per_session:
            anthropic_count += 1
        else:
            openai_count += 1
    
    total_words = sum(d.get("word_count", 100) for d in documents)
    avg_words = total_words / len(documents) if documents else 100
    
    openai_cost = openai_count * estimate_extraction_cost(avg_words, "openai")
    anthropic_cost = anthropic_count * estimate_extraction_cost(avg_words, "anthropic")
    
    return {
        "document_count": len(documents),
        "openai_extractions": openai_count,
        "anthropic_extractions": anthropic_count,
        "estimated_cost_cents": round(openai_cost + anthropic_cost, 2),
        "openai_cost_cents": round(openai_cost, 2),
        "anthropic_cost_cents": round(anthropic_cost, 2),
        "all_openai_cost_cents": round(len(documents) * estimate_extraction_cost(avg_words, "openai"), 2),
        "all_anthropic_cost_cents": round(len(documents) * estimate_extraction_cost(avg_words, "anthropic"), 2),
    }


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "RoutingConfig",
    "ProviderRouter",
    "estimate_extraction_cost",
    "estimate_batch_cost",
    "COST_PER_1K",
]

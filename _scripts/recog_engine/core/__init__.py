"""
ReCog Core - Core Module

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Core types, processors, and configuration for the ReCog recursive insight engine.
"""

from .types import (
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
)

from .config import RecogConfig

from .llm import (
    LLMResponse,
    LLMProvider,
    MockLLMProvider,
)

from .providers import (
    OpenAIProvider,
    AnthropicProvider,
    create_provider,
    get_available_providers,
)

from .routing import (
    RoutingConfig,
    ProviderRouter,
    estimate_extraction_cost,
    estimate_batch_cost,
)

from .signal import (
    SignalProcessor,
    process_text,
    process_document,
)

from .extractor import (
    Extractor,
    extract_from_text,
)

from .correlator import (
    Correlator,
    find_patterns,
)

from .synthesizer import (
    Synthesizer,
    synthesise_patterns,
)


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
    # Config
    "RecogConfig",
    # LLM
    "LLMResponse",
    "LLMProvider",
    "MockLLMProvider",
    # LLM Providers
    "OpenAIProvider",
    "AnthropicProvider",
    "create_provider",
    "get_available_providers",
    # Provider Routing
    "RoutingConfig",
    "ProviderRouter",
    "estimate_extraction_cost",
    "estimate_batch_cost",
    # Signal processing (Tier 0)
    "SignalProcessor",
    "process_text",
    "process_document",
    # Extraction (Tier 1)
    "Extractor",
    "extract_from_text",
    # Correlation (Tier 2)
    "Correlator",
    "find_patterns",
    # Synthesis (Tier 3)
    "Synthesizer",
    "synthesise_patterns",
]

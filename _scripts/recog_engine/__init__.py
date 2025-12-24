"""
ReCog Engine - Recursive Cognition Engine v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Commercial licenses available: brent@ehkolabs.io

ReCog is a standalone text analysis engine that extracts, correlates, 
and synthesises insights from unstructured text corpora.

Processing Tiers:
- Tier 0: Zero-cost signal extraction (emotions, entities, patterns) - no LLM
- Tier 1: Insight extraction via LLM
- Tier 2: Pattern correlation across insights
- Tier 3: Synthesis and report generation
"""

__version__ = '1.0.0'


# =============================================================================
# CORE API
# =============================================================================

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
    # Signal processing (Tier 0) - wrapper
    SignalProcessor,
    process_text,
    process_document,
    # Extraction (Tier 1) - wrapper
    Extractor,
    extract_from_text,
    # Correlation (Tier 2)
    Correlator,
    find_patterns,
    # Synthesis (Tier 3)
    Synthesizer,
    synthesise_patterns,
)


# =============================================================================
# TIER 0: SIGNAL EXTRACTION (No LLM Required)
# =============================================================================

from .tier0 import (
    # Main processor
    Tier0Processor,
    preprocess_text,
    summarise_for_prompt,
    # Utility
    to_json as tier0_to_json,
    from_json as tier0_from_json,
    # Individual extractors
    extract_phone_numbers,
    extract_email_addresses,
    extract_basic_entities,
    extract_emotion_signals,
    extract_intensity_markers,
    analyse_questions,
    extract_temporal_refs,
    analyse_structure,
    compute_flags,
    # Keyword dictionaries (for customisation)
    EMOTION_KEYWORDS,
    INTENSIFIERS,
    HEDGES,
    ABSOLUTES,
)


# =============================================================================
# TIER 1: INSIGHT EXTRACTION (LLM Required)
# =============================================================================

from .extraction import (
    # Types
    ExtractedInsight,
    ExtractionResult,
    # Prompt building
    INSIGHT_EXTRACTION_PROMPT,
    build_extraction_prompt,
    parse_extraction_response,
    # Content preparation
    prepare_chat_content,
    prepare_document_content,
    # Similarity detection
    calculate_similarity,
    find_similar_insight,
    merge_insights,
    SIMILARITY_THRESHOLD,
    # Surfacing logic
    should_surface,
    SURFACING_SIGNIFICANCE_THRESHOLD,
)


# =============================================================================
# ENTITY REGISTRY
# =============================================================================

from .entity_registry import (
    # Class
    EntityRegistry,
    # Utilities
    normalise_phone,
    normalise_email,
    normalise_name,
    # Module-level access
    init_registry,
    get_registry,
)


# =============================================================================
# PREFLIGHT SYSTEM
# =============================================================================

from .preflight import (
    # Class
    PreflightManager,
    # Cost constants
    COST_PER_1K_INPUT,
    COST_PER_1K_OUTPUT,
    OVERHEAD_MULTIPLIER,
    # Module-level access
    init_preflight,
    get_preflight,
)


# =============================================================================
# INSIGHT STORE
# =============================================================================

from .insight_store import (
    InsightStore,
)


# =============================================================================
# ADAPTERS
# =============================================================================

from .adapters import (
    RecogAdapter,
    MemoryAdapter,
    SQLiteAdapter,
)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Version
    '__version__',
    
    # === Core Types ===
    'ProcessingStatus', 'PatternType', 'SynthesisType',
    'Document', 'Insight', 'Pattern', 'Synthesis',
    'ProcessingState', 'Corpus', 'RecogConfig',
    'LLMResponse', 'LLMProvider', 'MockLLMProvider',
    
    # === Core Processors (wrappers) ===
    'SignalProcessor', 'process_text', 'process_document',
    'Extractor', 'extract_from_text',
    'Correlator', 'find_patterns',
    'Synthesizer', 'synthesise_patterns',
    
    # === Tier 0: Signal Extraction ===
    'Tier0Processor',
    'preprocess_text',
    'summarise_for_prompt',
    'tier0_to_json',
    'tier0_from_json',
    'extract_phone_numbers',
    'extract_email_addresses',
    'extract_basic_entities',
    'extract_emotion_signals',
    'extract_intensity_markers',
    'analyse_questions',
    'extract_temporal_refs',
    'analyse_structure',
    'compute_flags',
    'EMOTION_KEYWORDS',
    'INTENSIFIERS',
    'HEDGES',
    'ABSOLUTES',
    
    # === Tier 1: Insight Extraction ===
    'ExtractedInsight',
    'ExtractionResult',
    'INSIGHT_EXTRACTION_PROMPT',
    'build_extraction_prompt',
    'parse_extraction_response',
    'prepare_chat_content',
    'prepare_document_content',
    'calculate_similarity',
    'find_similar_insight',
    'merge_insights',
    'SIMILARITY_THRESHOLD',
    'should_surface',
    'SURFACING_SIGNIFICANCE_THRESHOLD',
    
    # === Entity Registry ===
    'EntityRegistry',
    'normalise_phone',
    'normalise_email',
    'normalise_name',
    'init_registry',
    'get_registry',
    
    # === Preflight System ===
    'PreflightManager',
    'COST_PER_1K_INPUT',
    'COST_PER_1K_OUTPUT',
    'OVERHEAD_MULTIPLIER',
    'init_preflight',
    'get_preflight',
    
    # === Insight Store ===
    'InsightStore',
    
    # === Adapters ===
    'RecogAdapter', 'MemoryAdapter', 'SQLiteAdapter',
]

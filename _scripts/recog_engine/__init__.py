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
# ENTITY GRAPH (Relationship-Aware)
# =============================================================================

from .entity_graph import (
    # Types
    RelationshipType,
    EntityRelationship,
    EntitySentiment,
    CoOccurrence,
    EntityNetwork,
    # Class
    EntityGraph,
    # Module-level access
    init_entity_graph,
    get_entity_graph,
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
# CASE ARCHITECTURE
# =============================================================================

from .case_store import (
    Case,
    CaseDocument,
    CaseContext,
    CaseStore,
)

from .findings_store import (
    Finding,
    FindingsStore,
)

from .timeline_store import (
    TimelineEvent,
    TimelineStore,
    VALID_EVENT_TYPES,
    create_case_created_event,
    create_doc_added_event,
    create_finding_verified_event,
    create_pattern_found_event,
)


# =============================================================================
# SYNTH ENGINE (Pattern Synthesis)
# =============================================================================

from .synth import (
    # Types
    ClusterStrategy,
    PatternType,
    InsightCluster,
    SynthesizedPattern,
    SynthResult,
    # Clustering functions
    cluster_by_theme,
    cluster_by_time,
    cluster_by_entity,
    auto_cluster,
    # Main engine
    SynthEngine,
    init_synth_engine,
    get_synth_engine,
)


# =============================================================================
# CRITIQUE ENGINE (Validation Layer)
# =============================================================================

from .critique import (
    # Enums
    CritiqueResult,
    CritiqueType,
    StrictnessLevel,
    # Data classes
    CritiqueCheck,
    CritiqueReport,
    # Engine
    CritiqueEngine,
    # Module-level
    init_critique_engine,
    get_critique_engine,
)


# =============================================================================
# COST TRACKING
# =============================================================================

from .cost_tracker import (
    CostTracker,
    CostEntry,
    CostSummary,
    PRICING,
    get_cost_tracker,
    log_llm_cost,
)


# =============================================================================
# FILE VALIDATION
# =============================================================================

from .file_validator import (
    FileValidator,
    ValidationResult,
    validate_file,
    validate_upload,
    get_validator,
    DEFAULT_MAX_SIZE_MB,
    SUPPORTED_MIME_TYPES,
)


# =============================================================================
# RESPONSE CACHE
# =============================================================================

from .response_cache import (
    ResponseCache,
    CacheEntry,
    CacheStats,
    get_response_cache,
    init_response_cache,
    DEFAULT_TTL_SECONDS,
)


# =============================================================================
# CONFIG VALIDATION
# =============================================================================

from .config_validator import (
    ConfigCheck,
    ConfigValidationResult,
    CONFIG_SCHEMA,
    validate_config,
    validate_on_startup,
    get_config_summary,
    print_config_help,
)


# =============================================================================
# RATE LIMITING
# =============================================================================

from .rate_limiter import (
    init_rate_limiter,
    get_limiter,
    rate_limit_expensive,
    rate_limit_upload,
    rate_limit_health,
    exempt_from_rate_limit,
    get_rate_limit_status,
    DEFAULT_LIMIT,
    EXPENSIVE_LIMIT,
    UPLOAD_LIMIT,
    RATE_LIMIT_ENABLED,
)


# =============================================================================
# LOGGING UTILITIES
# =============================================================================

from .logging_utils import (
    setup_logging,
    get_logger,
    set_request_id,
    get_request_id,
    log_request,
    Timer,
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
    
    # === Entity Graph ===
    'RelationshipType',
    'EntityRelationship',
    'EntitySentiment',
    'CoOccurrence',
    'EntityNetwork',
    'EntityGraph',
    'init_entity_graph',
    'get_entity_graph',
    
    # === Preflight System ===
    'PreflightManager',
    'COST_PER_1K_INPUT',
    'COST_PER_1K_OUTPUT',
    'OVERHEAD_MULTIPLIER',
    'init_preflight',
    'get_preflight',
    
    # === Insight Store ===
    'InsightStore',
    
    # === Case Architecture ===
    'Case',
    'CaseDocument',
    'CaseContext',
    'CaseStore',
    'Finding',
    'FindingsStore',
    'TimelineEvent',
    'TimelineStore',
    'VALID_EVENT_TYPES',
    'create_case_created_event',
    'create_doc_added_event',
    'create_finding_verified_event',
    'create_pattern_found_event',
    
    # === Synth Engine ===
    'ClusterStrategy',
    'PatternType',
    'InsightCluster',
    'SynthesizedPattern',
    'SynthResult',
    'cluster_by_theme',
    'cluster_by_time',
    'cluster_by_entity',
    'auto_cluster',
    'SynthEngine',
    'init_synth_engine',
    'get_synth_engine',
    
    # === Critique Engine ===
    'CritiqueResult',
    'CritiqueType',
    'StrictnessLevel',
    'CritiqueCheck',
    'CritiqueReport',
    'CritiqueEngine',
    'init_critique_engine',
    'get_critique_engine',

    # === Cost Tracking ===
    'CostTracker',
    'CostEntry',
    'CostSummary',
    'PRICING',
    'get_cost_tracker',
    'log_llm_cost',

    # === File Validation ===
    'FileValidator',
    'ValidationResult',
    'validate_file',
    'validate_upload',
    'get_validator',
    'DEFAULT_MAX_SIZE_MB',
    'SUPPORTED_MIME_TYPES',

    # === Response Cache ===
    'ResponseCache',
    'CacheEntry',
    'CacheStats',
    'get_response_cache',
    'init_response_cache',
    'DEFAULT_TTL_SECONDS',

    # === Config Validation ===
    'ConfigCheck',
    'ConfigValidationResult',
    'CONFIG_SCHEMA',
    'validate_config',
    'validate_on_startup',
    'get_config_summary',
    'print_config_help',

    # === Rate Limiting ===
    'init_rate_limiter',
    'get_limiter',
    'rate_limit_expensive',
    'rate_limit_upload',
    'rate_limit_health',
    'exempt_from_rate_limit',
    'get_rate_limit_status',
    'DEFAULT_LIMIT',
    'EXPENSIVE_LIMIT',
    'UPLOAD_LIMIT',
    'RATE_LIMIT_ENABLED',

    # === Logging ===
    'setup_logging',
    'get_logger',
    'set_request_id',
    'get_request_id',
    'log_request',
    'Timer',
    
    # === Adapters ===
    'RecogAdapter', 'MemoryAdapter', 'SQLiteAdapter',
]

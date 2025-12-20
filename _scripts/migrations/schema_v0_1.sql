-- =============================================================================
-- ReCog Database Schema v0.1
-- =============================================================================
-- Run: sqlite3 recog.db < schema_v0_1.sql
-- =============================================================================

-- =============================================================================
-- 1. ENTITY REGISTRY - Known entities with user-provided context
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Entity identification
    entity_type TEXT NOT NULL,              -- 'person', 'phone', 'email', 'organisation'
    raw_value TEXT NOT NULL,                -- Original extracted value
    normalised_value TEXT,                  -- Normalised form for matching
    
    -- User-provided context
    display_name TEXT,                      -- Human-friendly name ("Mum", "Jane Smith")
    relationship TEXT,                      -- Relationship to user ("mother", "therapist")
    notes TEXT,                             -- Any additional context
    
    -- Privacy controls
    anonymise_in_prompts INTEGER DEFAULT 0, -- If 1, use placeholder in LLM calls
    placeholder_name TEXT,                  -- Placeholder to use ("Person A")
    
    -- Metadata
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT,
    occurrence_count INTEGER DEFAULT 1,
    source_types TEXT,                      -- JSON array of source types
    
    -- Status
    confirmed INTEGER DEFAULT 0,            -- User has reviewed/confirmed
    merged_into_id INTEGER,                 -- If merged with another entity
    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    
    UNIQUE(entity_type, normalised_value)
);

CREATE INDEX IF NOT EXISTS idx_entity_type ON entity_registry(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_normalised ON entity_registry(normalised_value);
CREATE INDEX IF NOT EXISTS idx_entity_confirmed ON entity_registry(confirmed);


-- =============================================================================
-- 2. ENTITY ALIASES - Multiple values mapping to same entity
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    alias_type TEXT NOT NULL,               -- 'phone', 'email', 'nickname'
    alias_value TEXT NOT NULL,
    normalised_value TEXT,
    
    created_at TEXT NOT NULL,
    
    FOREIGN KEY (entity_id) REFERENCES entity_registry(id) ON DELETE CASCADE,
    UNIQUE(alias_type, normalised_value)
);

CREATE INDEX IF NOT EXISTS idx_alias_entity ON entity_aliases(entity_id);


-- =============================================================================
-- 3. PREFLIGHT SESSIONS - Track batch processing context
-- =============================================================================

CREATE TABLE IF NOT EXISTS preflight_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Session info
    session_type TEXT NOT NULL,             -- 'single_file', 'batch', 'chatgpt_import'
    status TEXT DEFAULT 'pending',          -- 'pending', 'scanned', 'reviewing', 'confirmed', 'processing', 'complete'
    
    -- Source files
    source_files_json TEXT,
    source_count INTEGER DEFAULT 0,
    
    -- Tier 0 results (aggregated)
    total_word_count INTEGER DEFAULT 0,
    total_entities_found INTEGER DEFAULT 0,
    unknown_entities_count INTEGER DEFAULT 0,
    estimated_tokens INTEGER DEFAULT 0,
    estimated_cost_cents INTEGER DEFAULT 0,
    
    -- Filtering applied
    filters_json TEXT,
    items_after_filter INTEGER,
    
    -- Entity resolution
    entity_questions_json TEXT,
    entity_answers_json TEXT,
    
    -- Processing
    started_at TEXT,
    completed_at TEXT,
    operations_created INTEGER DEFAULT 0,
    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_preflight_status ON preflight_sessions(status);


-- =============================================================================
-- 4. PREFLIGHT ITEMS - Individual items in a preflight session
-- =============================================================================

CREATE TABLE IF NOT EXISTS preflight_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preflight_session_id INTEGER NOT NULL,
    
    -- Item info
    source_type TEXT NOT NULL,
    source_id TEXT,
    title TEXT,
    
    -- Content (stored for processing)
    content TEXT,
    
    -- Content summary
    word_count INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    date_range_start TEXT,
    date_range_end TEXT,
    
    -- Tier 0 results
    pre_annotation_json TEXT,
    entities_found_json TEXT,
    
    -- Filtering
    included INTEGER DEFAULT 1,
    exclusion_reason TEXT,
    
    -- Processing
    processed INTEGER DEFAULT 0,
    
    created_at TEXT NOT NULL,
    
    FOREIGN KEY (preflight_session_id) REFERENCES preflight_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_preflight_items_session ON preflight_items(preflight_session_id);
CREATE INDEX IF NOT EXISTS idx_preflight_items_included ON preflight_items(included, processed);


-- =============================================================================
-- 5. INGESTED DOCUMENTS - Tracked documents
-- =============================================================================

CREATE TABLE IF NOT EXISTS ingested_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- File info
    filename TEXT NOT NULL,
    file_hash TEXT,                         -- SHA256 for deduplication
    file_type TEXT,
    file_path TEXT,
    file_size INTEGER,
    
    -- Document metadata
    doc_date TEXT,
    doc_author TEXT,
    doc_subject TEXT,
    doc_recipients TEXT,                    -- JSON array
    metadata TEXT,                          -- JSON object
    
    -- Processing status
    status TEXT DEFAULT 'pending',          -- 'pending', 'processing', 'complete', 'failed'
    chunk_count INTEGER DEFAULT 0,
    error_message TEXT,
    
    -- Timestamps
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed_at TEXT,
    
    UNIQUE(file_hash)
);

CREATE INDEX IF NOT EXISTS idx_documents_status ON ingested_documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON ingested_documents(file_hash);


-- =============================================================================
-- 6. DOCUMENT CHUNKS - Chunked content for processing
-- =============================================================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    
    -- Chunk info
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    
    -- Position info
    start_char INTEGER,
    end_char INTEGER,
    page_number INTEGER,
    
    -- Context
    preceding_context TEXT,
    following_context TEXT,
    
    -- Tier 0 signals
    tier0_signals TEXT,                     -- JSON from preprocess_text()
    
    -- Processing status
    recog_processed INTEGER DEFAULT 0,
    processed_at TEXT,
    
    FOREIGN KEY (document_id) REFERENCES ingested_documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_processed ON document_chunks(recog_processed);


-- =============================================================================
-- 7. INSIGHTS - Extracted insights
-- =============================================================================

CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,                    -- UUID
    
    -- Core content
    summary TEXT NOT NULL,
    themes_json TEXT,                       -- JSON array
    emotional_tags_json TEXT,               -- JSON array
    patterns_json TEXT,                     -- JSON array
    
    -- Scoring
    significance REAL DEFAULT 0.5,
    confidence REAL DEFAULT 0.5,
    
    -- Classification
    insight_type TEXT,                      -- 'observation', 'pattern', 'relationship', etc.
    status TEXT DEFAULT 'raw',              -- 'raw', 'refined', 'surfaced', 'rejected', 'merged'
    
    -- Source tracking
    source_count INTEGER DEFAULT 1,
    earliest_source_date TEXT,
    latest_source_date TEXT,
    excerpt TEXT,
    
    -- Analysis metadata
    last_analysis_at TEXT,
    analysis_model TEXT,
    analysis_pass INTEGER DEFAULT 1,
    
    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_insights_status ON insights(status);
CREATE INDEX IF NOT EXISTS idx_insights_significance ON insights(significance);
CREATE INDEX IF NOT EXISTS idx_insights_type ON insights(insight_type);


-- =============================================================================
-- 8. INSIGHT SOURCES - Link insights to source content
-- =============================================================================

CREATE TABLE IF NOT EXISTS insight_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_id TEXT NOT NULL,
    
    -- Source reference
    source_type TEXT NOT NULL,              -- 'document_chunk', 'preflight_item', etc.
    source_id TEXT NOT NULL,
    
    -- Context
    excerpt TEXT,
    
    added_at TEXT NOT NULL,
    
    FOREIGN KEY (insight_id) REFERENCES insights(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_insight_sources_insight ON insight_sources(insight_id);
CREATE INDEX IF NOT EXISTS idx_insight_sources_source ON insight_sources(source_type, source_id);


-- =============================================================================
-- 9. INSIGHT HISTORY - Track insight evolution
-- =============================================================================

CREATE TABLE IF NOT EXISTS insight_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_id TEXT NOT NULL,
    
    -- Event info
    event_type TEXT NOT NULL,               -- 'created', 'source_added', 'merged', 'surfaced', 'rejected'
    event_at TEXT NOT NULL,
    
    -- Change data
    previous_value TEXT,                    -- JSON
    new_value TEXT,                         -- JSON
    trigger TEXT,                           -- What caused this change
    
    FOREIGN KEY (insight_id) REFERENCES insights(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_insight_history_insight ON insight_history(insight_id);


-- =============================================================================
-- 10. PATTERNS - Detected patterns across insights
-- =============================================================================

CREATE TABLE IF NOT EXISTS patterns (
    id TEXT PRIMARY KEY,                    -- UUID
    
    -- Pattern content
    name TEXT NOT NULL,
    description TEXT,
    pattern_type TEXT,                      -- 'behavioral', 'emotional', 'temporal', 'relational'
    
    -- Related insights
    insight_ids_json TEXT,                  -- JSON array of insight IDs
    insight_count INTEGER DEFAULT 0,
    
    -- Scoring
    strength REAL DEFAULT 0.5,
    confidence REAL DEFAULT 0.5,
    
    -- Status
    status TEXT DEFAULT 'detected',         -- 'detected', 'confirmed', 'rejected'
    
    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_status ON patterns(status);


-- =============================================================================
-- 11. PROCESSING QUEUE - Track pending operations
-- =============================================================================

CREATE TABLE IF NOT EXISTS processing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Operation info
    operation_type TEXT NOT NULL,           -- 'extract', 'correlate', 'synthesize'
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    
    -- Status
    status TEXT DEFAULT 'pending',          -- 'pending', 'processing', 'complete', 'failed'
    priority INTEGER DEFAULT 0,
    
    -- Metadata
    word_count INTEGER,
    pre_annotation_json TEXT,
    pass_count INTEGER DEFAULT 0,
    notes TEXT,
    
    -- Timestamps
    queued_at TEXT NOT NULL,
    last_processed_at TEXT,
    
    UNIQUE(source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue(status, priority);


-- =============================================================================
-- 12. INGESTION LOG - Track ingestion actions
-- =============================================================================

CREATE TABLE IF NOT EXISTS ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    
    action TEXT NOT NULL,
    details TEXT,                           -- JSON
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (document_id) REFERENCES ingested_documents(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_document ON ingestion_log(document_id);

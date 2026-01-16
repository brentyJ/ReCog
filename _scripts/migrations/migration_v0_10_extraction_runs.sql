-- =============================================================================
-- ReCog Schema Migration: Extraction Run Versioning
-- Version: 0.10
-- =============================================================================
-- Adds extraction run tracking for versioned analysis passes.
-- Enables comparison between runs with different context configurations.
--
-- Use case: Track how synthesis changes when adding age context, life events,
-- or other contextual information to extraction prompts.
--
-- Run: sqlite3 recog.db < migration_v0_10_extraction_runs.sql
-- =============================================================================


-- =============================================================================
-- 1. EXTRACTION_RUNS TABLE
-- =============================================================================
-- Tracks each extraction pass with its configuration and metadata

CREATE TABLE IF NOT EXISTS extraction_runs (
    id TEXT PRIMARY KEY,

    -- Human-friendly identification
    name TEXT NOT NULL,                        -- "Baseline - Pure Extraction"
    description TEXT,                          -- What context/changes were made

    -- Run configuration
    context_config_json TEXT,                  -- JSON: what context was injected
                                              -- e.g., {"dob": "1986-02-27", "life_context": true}

    -- Data tracking
    source_description TEXT,                   -- "Instagram DMs 2017-2026"
    source_hash TEXT,                          -- Hash of source data for change detection

    -- Results summary
    insight_count INTEGER DEFAULT 0,
    pattern_count INTEGER DEFAULT 0,

    -- Lineage tracking
    parent_run_id TEXT,                        -- Previous run this is compared against

    -- Status
    status TEXT DEFAULT 'running',             -- 'running', 'complete', 'failed'

    -- Timestamps
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (parent_run_id) REFERENCES extraction_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_extraction_runs_status ON extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_parent ON extraction_runs(parent_run_id);


-- =============================================================================
-- 2. LIFE_CONTEXT TABLE
-- =============================================================================
-- Timeline of life events for context injection into extraction prompts

CREATE TABLE IF NOT EXISTS life_context (
    id TEXT PRIMARY KEY,

    -- Time range
    start_date TEXT NOT NULL,                  -- YYYY-MM-DD
    end_date TEXT,                             -- NULL = ongoing

    -- Event details
    title TEXT NOT NULL,                       -- "Working at NZ Police"
    description TEXT,                          -- More details
    location TEXT,                             -- "Wellington, NZ"

    -- Classification
    context_type TEXT NOT NULL,                -- 'career', 'relationship', 'residence',
                                              -- 'education', 'health', 'event'
    tags_json TEXT,                            -- JSON array of tags

    -- Usage tracking
    active INTEGER DEFAULT 1,                  -- Include in context injection

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_life_context_dates ON life_context(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_life_context_type ON life_context(context_type);


-- =============================================================================
-- 3. ADD RUN_ID TO INSIGHTS TABLE
-- =============================================================================
-- Link insights to specific extraction runs

ALTER TABLE insights ADD COLUMN run_id TEXT REFERENCES extraction_runs(id);

CREATE INDEX IF NOT EXISTS idx_insights_run_id ON insights(run_id);


-- =============================================================================
-- 4. ADD RUN_ID TO PATTERNS TABLE
-- =============================================================================
-- Link patterns to specific extraction runs

ALTER TABLE patterns ADD COLUMN run_id TEXT REFERENCES extraction_runs(id);

CREATE INDEX IF NOT EXISTS idx_patterns_run_id ON patterns(run_id);


-- =============================================================================
-- 5. RUN_DELTAS TABLE
-- =============================================================================
-- Tracks what changed between extraction runs

CREATE TABLE IF NOT EXISTS run_deltas (
    id TEXT PRIMARY KEY,

    -- Run comparison
    run_id TEXT NOT NULL,                      -- New run
    parent_run_id TEXT NOT NULL,               -- Baseline run being compared against

    -- Change classification
    delta_type TEXT NOT NULL,                  -- 'insight_added', 'insight_modified',
                                              -- 'insight_removed', 'pattern_added',
                                              -- 'pattern_modified', 'pattern_removed',
                                              -- 'significance_shift', 'theme_change'

    -- Entity reference
    entity_type TEXT NOT NULL,                 -- 'insight' or 'pattern'
    entity_id TEXT,                            -- The specific insight/pattern

    -- Change details
    change_summary TEXT NOT NULL,              -- Human-readable description
    old_value_json TEXT,                       -- Previous state (for modifications)
    new_value_json TEXT,                       -- New state (for modifications)

    -- Context attribution
    attributed_to TEXT,                        -- What caused this change
                                              -- e.g., "age_context", "life_event:career_change"

    -- Timestamps
    created_at TEXT NOT NULL,

    FOREIGN KEY (run_id) REFERENCES extraction_runs(id),
    FOREIGN KEY (parent_run_id) REFERENCES extraction_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_run_deltas_run_id ON run_deltas(run_id);
CREATE INDEX IF NOT EXISTS idx_run_deltas_type ON run_deltas(delta_type);


-- =============================================================================
-- 6. RUN_SYNTHESIS TABLE
-- =============================================================================
-- Stores synthesis output (Tier 3) per run for comparison

CREATE TABLE IF NOT EXISTS run_synthesis (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,

    -- Synthesis content
    synthesis_type TEXT NOT NULL,              -- 'psychological_profile', 'executive_summary',
                                              -- 'temporal_analysis', 'custom'
    title TEXT NOT NULL,
    content TEXT NOT NULL,                     -- Full synthesis text

    -- Metadata
    model_used TEXT,
    token_count INTEGER,

    -- Timestamps
    created_at TEXT NOT NULL,

    FOREIGN KEY (run_id) REFERENCES extraction_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_run_synthesis_run_id ON run_synthesis(run_id);

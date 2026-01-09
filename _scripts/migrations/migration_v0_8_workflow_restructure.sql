-- =============================================================================
-- ReCog Schema Migration: Workflow Restructure
-- Version: 0.8
-- =============================================================================
-- Adds state machine fields to cases table and creates case_progress table
-- for auto-progression workflow support.
--
-- Run: sqlite3 recog.db < migration_v0_8_workflow_restructure.sql
-- Note: SQLite doesn't support CHECK constraints in ALTER TABLE, so we use DEFAULT only
-- =============================================================================

-- =============================================================================
-- 1. ADD NEW FIELDS TO CASES TABLE
-- =============================================================================

-- Pipeline state tracking (CHECK constraint not supported in ALTER TABLE)
-- Valid states: uploading, scanning, clarifying, processing, complete, watching
ALTER TABLE cases ADD COLUMN state TEXT DEFAULT 'complete';

-- Cost tracking
ALTER TABLE cases ADD COLUMN estimated_cost REAL DEFAULT 0.0;
ALTER TABLE cases ADD COLUMN actual_cost REAL DEFAULT 0.0;

-- Workflow settings
ALTER TABLE cases ADD COLUMN assistant_mode INTEGER DEFAULT 0;
ALTER TABLE cases ADD COLUMN auto_process INTEGER DEFAULT 1;
ALTER TABLE cases ADD COLUMN monitor_directory INTEGER DEFAULT 0;

-- Timestamps for processing
ALTER TABLE cases ADD COLUMN last_activity TEXT;
ALTER TABLE cases ADD COLUMN processing_started_at TEXT;
ALTER TABLE cases ADD COLUMN processing_completed_at TEXT;

-- Index for active case queries
CREATE INDEX IF NOT EXISTS idx_cases_state ON cases(state);
CREATE INDEX IF NOT EXISTS idx_cases_last_activity ON cases(last_activity);


-- =============================================================================
-- 2. CREATE CASE_PROGRESS TABLE
-- =============================================================================
-- Tracks fine-grained progress within processing state for real-time display

CREATE TABLE IF NOT EXISTS case_progress (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,

    -- Stage tracking
    stage TEXT NOT NULL,                    -- 'tier0', 'extraction', 'synthesis', 'critique'
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'complete', 'failed'

    -- Progress metrics
    progress REAL DEFAULT 0.0,              -- 0.0 to 1.0
    current_item TEXT,                      -- e.g., "Processing email_042.txt"
    total_items INTEGER DEFAULT 0,
    completed_items INTEGER DEFAULT 0,

    -- Display data
    recent_insight TEXT,                    -- Latest discovery for terminal display

    -- Error tracking
    error_message TEXT,

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_case_progress_case_id ON case_progress(case_id);
CREATE INDEX IF NOT EXISTS idx_case_progress_status ON case_progress(status);


-- =============================================================================
-- 3. MIGRATE EXISTING CASES TO 'COMPLETE' STATE
-- =============================================================================
-- Existing cases have already been processed, so mark them as complete

UPDATE cases SET state = 'complete' WHERE state IS NULL OR state = 'uploading';


-- =============================================================================
-- 4. ADD PREFLIGHT SESSION STATE FIELD (if not exists)
-- =============================================================================
-- Track which preflight sessions have triggered auto-processing

ALTER TABLE preflight_sessions ADD COLUMN auto_processed INTEGER DEFAULT 0;

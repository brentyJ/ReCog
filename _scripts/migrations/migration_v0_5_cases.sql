-- =============================================================================
-- ReCog Schema Migration: Case Architecture Tables
-- Version: 0.5
-- =============================================================================
-- Run: sqlite3 recog.db < migration_v0_5_cases.sql
-- =============================================================================

-- =============================================================================
-- CASES - Organizational containers for document intelligence
-- =============================================================================

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,                    -- UUID
    
    -- Case definition
    title TEXT NOT NULL,
    context TEXT,                           -- Initial question/assignment
    focus_areas_json TEXT,                  -- JSON array ["pricing", "competition"]
    
    -- Status
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived')),
    
    -- Statistics (denormalized for performance)
    document_count INTEGER DEFAULT 0,
    findings_count INTEGER DEFAULT 0,
    patterns_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_created ON cases(created_at);


-- =============================================================================
-- CASE_DOCUMENTS - Link documents to cases with metadata
-- =============================================================================

CREATE TABLE IF NOT EXISTS case_documents (
    id TEXT PRIMARY KEY,                    -- UUID
    case_id TEXT NOT NULL,
    document_id TEXT NOT NULL,              -- Links to existing document tracking
    
    -- Metadata
    added_at TEXT NOT NULL,
    impact_notes TEXT,                      -- Human annotations about this doc's impact
    
    -- Stats (denormalized)
    findings_count INTEGER DEFAULT 0,
    entities_count INTEGER DEFAULT 0,
    
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
    UNIQUE(case_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_case_docs_case ON case_documents(case_id);
CREATE INDEX IF NOT EXISTS idx_case_docs_document ON case_documents(document_id);


-- =============================================================================
-- FINDINGS - Validated insights promoted for case analysis
-- =============================================================================

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,                    -- UUID
    case_id TEXT NOT NULL,
    insight_id TEXT NOT NULL,               -- Links to insights table
    
    -- Validation status
    status TEXT DEFAULT 'needs_verification' 
        CHECK(status IN ('verified', 'needs_verification', 'rejected')),
    verified_at TEXT,
    verified_by TEXT,                       -- 'user' or 'auto'
    
    -- Categorization
    tags_json TEXT,                         -- JSON array for filtering
    
    -- Annotations
    user_notes TEXT,                        -- Human commentary
    
    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
    FOREIGN KEY (insight_id) REFERENCES insights(id) ON DELETE CASCADE,
    UNIQUE(case_id, insight_id)             -- Prevent duplicate promotions
);

CREATE INDEX IF NOT EXISTS idx_findings_case ON findings(case_id);
CREATE INDEX IF NOT EXISTS idx_findings_insight ON findings(insight_id);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);


-- =============================================================================
-- CASE_TIMELINE - Auto-generated chronicle of case evolution
-- =============================================================================

CREATE TABLE IF NOT EXISTS case_timeline (
    id TEXT PRIMARY KEY,                    -- UUID
    case_id TEXT NOT NULL,
    
    -- Event info
    event_type TEXT NOT NULL CHECK(event_type IN (
        'case_created', 
        'doc_added', 
        'doc_removed',
        'finding_added',
        'finding_verified', 
        'finding_rejected',
        'pattern_found', 
        'note_added',
        'context_updated',
        'status_changed',
        'insights_extracted'
    )),
    event_data_json TEXT,                   -- Flexible payload {doc_id, count, etc}
    
    -- Human annotation
    human_annotation TEXT,                  -- User notes on this event
    
    -- Timestamp
    timestamp TEXT NOT NULL,
    
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_timeline_case ON case_timeline(case_id);
CREATE INDEX IF NOT EXISTS idx_timeline_type ON case_timeline(event_type);
CREATE INDEX IF NOT EXISTS idx_timeline_time ON case_timeline(timestamp);


-- =============================================================================
-- ADD CASE_ID FOREIGN KEYS TO EXISTING TABLES
-- =============================================================================
-- Note: SQLite doesn't support ADD COLUMN IF NOT EXISTS, so these may fail
-- if already present. The Python migration handler catches these errors.

-- Add case_id to insights (nullable - standalone insights still allowed)
ALTER TABLE insights ADD COLUMN case_id TEXT REFERENCES cases(id);

-- Add case_id to patterns (nullable - standalone patterns still allowed)
ALTER TABLE patterns ADD COLUMN case_id TEXT REFERENCES cases(id);

-- Add case_id to preflight_sessions (associate upload session with case)
ALTER TABLE preflight_sessions ADD COLUMN case_id TEXT REFERENCES cases(id);

-- Create indexes for the new columns
CREATE INDEX IF NOT EXISTS idx_insights_case ON insights(case_id);
CREATE INDEX IF NOT EXISTS idx_patterns_case ON patterns(case_id);
CREATE INDEX IF NOT EXISTS idx_preflight_case ON preflight_sessions(case_id);

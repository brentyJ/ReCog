-- =============================================================================
-- ReCog Schema Migration: Fix Timeline Event Types
-- Version: 0.5.1
-- =============================================================================
-- Adds 'insights_extracted' to valid event types
-- Run: sqlite3 recog.db < migration_v0_5_1_timeline_fix.sql
-- =============================================================================

-- SQLite doesn't allow ALTER CONSTRAINT, so we recreate the table

-- Step 1: Rename existing table
ALTER TABLE case_timeline RENAME TO case_timeline_old;

-- Step 2: Create new table with updated constraint
CREATE TABLE case_timeline (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    
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
    event_data_json TEXT,
    human_annotation TEXT,
    timestamp TEXT NOT NULL,
    
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

-- Step 3: Copy data from old table
INSERT INTO case_timeline SELECT * FROM case_timeline_old;

-- Step 4: Drop old table
DROP TABLE case_timeline_old;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_timeline_case ON case_timeline(case_id);
CREATE INDEX IF NOT EXISTS idx_timeline_type ON case_timeline(event_type);
CREATE INDEX IF NOT EXISTS idx_timeline_time ON case_timeline(timestamp);

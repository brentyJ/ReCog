-- =============================================================================
-- ReCog Schema Migration: Add insights_extracted event type
-- Version: 0.5.2
-- =============================================================================
-- This fixes the case_timeline table to allow 'insights_extracted' events.
-- SQLite doesn't support ALTER TABLE to modify CHECK constraints, so we
-- recreate the table.
-- =============================================================================

-- Create new table with updated constraint
CREATE TABLE IF NOT EXISTS case_timeline_new (
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

-- Copy existing data
INSERT OR IGNORE INTO case_timeline_new 
SELECT * FROM case_timeline;

-- Drop old table
DROP TABLE IF EXISTS case_timeline;

-- Rename new table
ALTER TABLE case_timeline_new RENAME TO case_timeline;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_timeline_case ON case_timeline(case_id);
CREATE INDEX IF NOT EXISTS idx_timeline_type ON case_timeline(event_type);
CREATE INDEX IF NOT EXISTS idx_timeline_time ON case_timeline(timestamp);

-- =============================================================================
-- ReCog Schema Migration: Add case_id to processing_queue
-- Version: 0.6
-- =============================================================================
-- Run: sqlite3 recog.db < migration_v0_6_queue_case_id.sql
-- =============================================================================

-- Add case_id to processing_queue so worker can inject case context
ALTER TABLE processing_queue ADD COLUMN case_id TEXT REFERENCES cases(id);

-- Create index for case-based queue queries
CREATE INDEX IF NOT EXISTS idx_queue_case ON processing_queue(case_id);

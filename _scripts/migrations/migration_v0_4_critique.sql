-- =============================================================================
-- ReCog Schema Migration: Critique Layer Tables
-- Version: 0.4
-- =============================================================================
-- Run: sqlite3 recog.db < migration_v0_4_critique.sql
-- =============================================================================

-- =============================================================================
-- CRITIQUE REPORTS - Validation results for insights and patterns
-- =============================================================================

CREATE TABLE IF NOT EXISTS critique_reports (
    id TEXT PRIMARY KEY,
    
    -- What was critiqued
    target_type TEXT NOT NULL,          -- 'insight' or 'pattern'
    target_id TEXT NOT NULL,
    
    -- Overall verdict
    overall_result TEXT NOT NULL,       -- 'pass', 'fail', 'warn', 'refine'
    overall_score REAL DEFAULT 0.5,     -- 0-1 aggregate confidence
    
    -- Detailed checks
    checks_json TEXT,                   -- JSON array of check results
    
    -- Recommendations
    recommendation TEXT,                -- What to do with this item
    refinement_prompt TEXT,             -- If refine, how to fix
    
    -- Metadata
    model_used TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_critique_target ON critique_reports(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_critique_result ON critique_reports(overall_result);
CREATE INDEX IF NOT EXISTS idx_critique_score ON critique_reports(overall_score);
CREATE INDEX IF NOT EXISTS idx_critique_date ON critique_reports(created_at);


-- =============================================================================
-- REFINEMENT HISTORY - Track refinement iterations
-- =============================================================================

CREATE TABLE IF NOT EXISTS refinement_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    
    iteration INTEGER DEFAULT 1,
    
    -- Before/after
    original_content_json TEXT,
    refined_content_json TEXT,
    
    -- What triggered refinement
    critique_id TEXT,
    refinement_prompt TEXT,
    
    -- Result
    refinement_successful INTEGER DEFAULT 0,
    
    created_at TEXT NOT NULL,
    
    FOREIGN KEY (critique_id) REFERENCES critique_reports(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_refine_target ON refinement_history(target_type, target_id);


-- =============================================================================
-- ADD CRITIQUE STATUS TO INSIGHTS AND PATTERNS
-- =============================================================================

-- Add critique_status to insights if not exists
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we check via pragma
-- This is handled in Python migration code instead

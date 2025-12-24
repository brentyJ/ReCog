-- =============================================================================
-- ReCog Schema Migration: Add insight_clusters table for Synth Engine
-- Version: 0.2
-- =============================================================================
-- Run: sqlite3 recog.db < migration_v0_2_synth.sql
-- =============================================================================

-- =============================================================================
-- INSIGHT CLUSTERS - Groups of insights awaiting synthesis
-- =============================================================================

CREATE TABLE IF NOT EXISTS insight_clusters (
    id TEXT PRIMARY KEY,
    
    -- Clustering info
    strategy TEXT NOT NULL,                 -- 'thematic', 'temporal', 'entity', 'emotional'
    cluster_key TEXT NOT NULL,              -- What groups them (theme name, date range, etc.)
    
    -- Members
    insight_ids_json TEXT NOT NULL,         -- JSON array of insight IDs
    insight_count INTEGER DEFAULT 0,
    
    -- Temporal bounds
    date_range_start TEXT,
    date_range_end TEXT,
    
    -- Shared attributes
    shared_themes_json TEXT,                -- JSON array
    shared_entities_json TEXT,              -- JSON array
    
    -- Quality metrics
    avg_significance REAL DEFAULT 0.5,
    
    -- Processing status
    status TEXT DEFAULT 'pending',          -- 'pending', 'synthesizing', 'complete', 'failed'
    
    -- Timestamps
    created_at TEXT NOT NULL,
    
    UNIQUE(strategy, cluster_key)
);

CREATE INDEX IF NOT EXISTS idx_clusters_status ON insight_clusters(status);
CREATE INDEX IF NOT EXISTS idx_clusters_strategy ON insight_clusters(strategy);


-- =============================================================================
-- PATTERN DETAILS - Extended pattern metadata (supplements patterns table)
-- =============================================================================

CREATE TABLE IF NOT EXISTS pattern_details (
    pattern_id TEXT PRIMARY KEY,
    
    -- Extended evidence
    supporting_excerpts_json TEXT,          -- JSON array of key quotes
    contradictions_json TEXT,               -- JSON array of conflicting evidence
    
    -- Related entities
    entities_involved_json TEXT,            -- JSON array
    
    -- Source tracking
    source_cluster_id TEXT,
    analysis_model TEXT,
    
    -- Follow-up suggestions
    suggested_followups_json TEXT,          -- JSON array
    
    FOREIGN KEY (pattern_id) REFERENCES patterns(id) ON DELETE CASCADE
);


-- =============================================================================
-- Add columns to patterns table if they don't exist
-- =============================================================================

-- Note: SQLite doesn't support IF NOT EXISTS for ALTER TABLE
-- These will fail silently if columns already exist

-- ALTER TABLE patterns ADD COLUMN date_range_start TEXT;
-- ALTER TABLE patterns ADD COLUMN date_range_end TEXT;

-- =============================================================================
-- ReCog Schema Migration: Add Missing Indexes
-- Version: 0.7
-- =============================================================================
-- Run: sqlite3 recog.db < migration_v0_7_missing_indexes.sql
-- =============================================================================
-- This migration adds indexes for:
-- 1. Foreign keys that were missing indexes
-- 2. Frequently queried columns (timestamps for sorting)
-- =============================================================================

-- =============================================================================
-- FOREIGN KEY INDEXES
-- =============================================================================

-- entity_registry: self-referential FK for merged entities
CREATE INDEX IF NOT EXISTS idx_entity_merged_into ON entity_registry(merged_into_id);

-- refinement_history: FK to critique_reports
CREATE INDEX IF NOT EXISTS idx_refine_critique ON refinement_history(critique_id);

-- pattern_details: logical reference to insight_clusters
CREATE INDEX IF NOT EXISTS idx_pattern_details_cluster ON pattern_details(source_cluster_id);


-- =============================================================================
-- TIMESTAMP INDEXES (for sorting and filtering)
-- =============================================================================

-- insights: frequently sorted by creation date
CREATE INDEX IF NOT EXISTS idx_insights_created ON insights(created_at);

-- patterns: frequently sorted by creation date
CREATE INDEX IF NOT EXISTS idx_patterns_created ON patterns(created_at);

-- processing_queue: ordered by queue time for FIFO processing
CREATE INDEX IF NOT EXISTS idx_queue_queued_at ON processing_queue(queued_at);

-- ingested_documents: frequently listed by ingestion date
CREATE INDEX IF NOT EXISTS idx_documents_ingested ON ingested_documents(ingested_at);

-- entity_registry: for timeline/history views
CREATE INDEX IF NOT EXISTS idx_entity_created ON entity_registry(created_at);

-- entity_registry: for finding recently seen entities
CREATE INDEX IF NOT EXISTS idx_entity_last_seen ON entity_registry(last_seen_at);

-- insight_clusters: for ordering by creation
CREATE INDEX IF NOT EXISTS idx_clusters_created ON insight_clusters(created_at);

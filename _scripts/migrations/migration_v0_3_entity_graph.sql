-- =============================================================================
-- ReCog Schema Migration: Entity Graph Tables
-- Version: 0.3
-- =============================================================================
-- Run: sqlite3 recog.db < migration_v0_3_entity_graph.sql
-- =============================================================================

-- =============================================================================
-- ENTITY RELATIONSHIPS - Links between entities
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- The two entities
    source_entity_id INTEGER NOT NULL,
    target_entity_id INTEGER NOT NULL,
    
    -- Relationship info
    relationship_type TEXT NOT NULL,    -- 'manages', 'works_with', 'family_of', etc.
    strength REAL DEFAULT 0.5,          -- 0-1, confidence/strength of relationship
    bidirectional INTEGER DEFAULT 0,    -- 1 if relationship works both ways
    context TEXT,                       -- How we know about this relationship
    
    -- Evidence
    source_ids_json TEXT,               -- JSON array of insight/document IDs
    
    -- Temporal
    first_seen_at TEXT,
    last_seen_at TEXT,
    occurrence_count INTEGER DEFAULT 1,
    
    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    
    FOREIGN KEY (source_entity_id) REFERENCES entity_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (target_entity_id) REFERENCES entity_registry(id) ON DELETE CASCADE,
    UNIQUE(source_entity_id, target_entity_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_rel_source ON entity_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON entity_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON entity_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_rel_strength ON entity_relationships(strength);


-- =============================================================================
-- ENTITY SENTIMENT - Sentiment tracking per entity over time
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    entity_id INTEGER NOT NULL,
    
    -- Sentiment data
    sentiment_score REAL NOT NULL,      -- -1 (negative) to 1 (positive)
    sentiment_label TEXT NOT NULL,      -- 'negative', 'neutral', 'positive', 'mixed'
    
    -- Source
    source_type TEXT NOT NULL,          -- 'insight', 'document', etc.
    source_id TEXT NOT NULL,
    excerpt TEXT,                       -- Relevant text snippet
    
    -- Timestamp
    recorded_at TEXT NOT NULL,
    
    FOREIGN KEY (entity_id) REFERENCES entity_registry(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sentiment_entity ON entity_sentiment(entity_id);
CREATE INDEX IF NOT EXISTS idx_sentiment_label ON entity_sentiment(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_sentiment_date ON entity_sentiment(recorded_at);


-- =============================================================================
-- ENTITY CO-OCCURRENCES - Entities appearing together
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_co_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Always store smaller ID first for consistency
    entity_a_id INTEGER NOT NULL,
    entity_b_id INTEGER NOT NULL,
    
    -- Occurrence data
    count INTEGER DEFAULT 1,
    source_ids_json TEXT,               -- JSON array of "type:id" strings
    
    -- Temporal
    first_seen_at TEXT,
    last_seen_at TEXT,
    
    FOREIGN KEY (entity_a_id) REFERENCES entity_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_b_id) REFERENCES entity_registry(id) ON DELETE CASCADE,
    UNIQUE(entity_a_id, entity_b_id),
    CHECK(entity_a_id < entity_b_id)    -- Enforce ordering
);

CREATE INDEX IF NOT EXISTS idx_cooccur_a ON entity_co_occurrences(entity_a_id);
CREATE INDEX IF NOT EXISTS idx_cooccur_b ON entity_co_occurrences(entity_b_id);
CREATE INDEX IF NOT EXISTS idx_cooccur_count ON entity_co_occurrences(count);


-- =============================================================================
-- ENTITY INSIGHTS LINK - Track which insights mention which entities
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_insight_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    entity_id INTEGER NOT NULL,
    insight_id TEXT NOT NULL,
    
    -- How entity appears in insight
    mention_type TEXT DEFAULT 'mentioned',  -- 'mentioned', 'subject', 'object'
    excerpt TEXT,                            -- Context of mention
    
    created_at TEXT NOT NULL,
    
    FOREIGN KEY (entity_id) REFERENCES entity_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (insight_id) REFERENCES insights(id) ON DELETE CASCADE,
    UNIQUE(entity_id, insight_id)
);

CREATE INDEX IF NOT EXISTS idx_eil_entity ON entity_insight_links(entity_id);
CREATE INDEX IF NOT EXISTS idx_eil_insight ON entity_insight_links(insight_id);

-- =============================================================================
-- ReCog Migration v0.2 - Entity Blacklist
-- =============================================================================
-- Adds entity_blacklist table for tracking rejected entity detections
-- This enables learning from user feedback to reduce false positives
-- =============================================================================

-- Entity Blacklist - stores values that should NOT be detected as entities
CREATE TABLE IF NOT EXISTS entity_blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- What was rejected
    entity_type TEXT NOT NULL,              -- 'person', 'phone', 'email', 'organisation'
    raw_value TEXT NOT NULL,                -- Original value as detected
    normalised_value TEXT NOT NULL,         -- Normalised for matching
    
    -- Why it was rejected
    rejection_reason TEXT,                  -- 'not_a_person', 'common_word', 'false_positive', etc.
    rejected_by TEXT DEFAULT 'user',        -- 'user', 'llm_validation', 'system'
    
    -- Context for debugging
    source_context TEXT,                    -- Where it was originally detected
    
    -- Metadata
    rejection_count INTEGER DEFAULT 1,      -- How many times rejected (for weighting)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    
    UNIQUE(entity_type, normalised_value)
);

CREATE INDEX IF NOT EXISTS idx_blacklist_type ON entity_blacklist(entity_type);
CREATE INDEX IF NOT EXISTS idx_blacklist_normalised ON entity_blacklist(normalised_value);


-- Add confidence column to entity_registry if not exists
-- This tracks the original detection confidence
ALTER TABLE entity_registry ADD COLUMN detection_confidence TEXT DEFAULT 'medium';

-- =============================================================================
-- ReCog Schema Migration: Cost Tracking
-- Version: 0.9
-- =============================================================================
-- Adds cost_logs table to track token usage and costs per LLM request.
-- Enables visibility into LLM spending before costs spiral.
--
-- Run: sqlite3 recog.db < migration_v0_9_cost_tracking.sql
-- =============================================================================

-- =============================================================================
-- 1. CREATE COST_LOGS TABLE
-- =============================================================================
-- Tracks every LLM API call with token counts and calculated costs

CREATE TABLE IF NOT EXISTS cost_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Request context
    user_id TEXT DEFAULT 'default',          -- For future multi-user support
    feature TEXT NOT NULL,                    -- 'extraction', 'synthesis', 'critique', 'cypher', etc.
    case_id TEXT,                             -- Optional link to case

    -- Provider details
    provider TEXT NOT NULL,                   -- 'anthropic', 'openai'
    model TEXT NOT NULL,                      -- 'claude-3-5-sonnet-20241022', 'gpt-4o-mini'

    -- Token usage
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,

    -- Cost calculation (in USD)
    input_cost REAL NOT NULL DEFAULT 0.0,
    output_cost REAL NOT NULL DEFAULT 0.0,
    total_cost REAL NOT NULL DEFAULT 0.0,

    -- Request metadata
    latency_ms INTEGER,                       -- Response time in milliseconds
    success INTEGER NOT NULL DEFAULT 1,       -- 1 = success, 0 = failed
    error_message TEXT,                       -- Error details if failed

    -- Timestamp
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_cost_logs_created_at ON cost_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_cost_logs_feature ON cost_logs(feature);
CREATE INDEX IF NOT EXISTS idx_cost_logs_provider ON cost_logs(provider);
CREATE INDEX IF NOT EXISTS idx_cost_logs_user_id ON cost_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_cost_logs_case_id ON cost_logs(case_id);


-- =============================================================================
-- 2. CREATE DAILY COST SUMMARY VIEW
-- =============================================================================
-- Convenience view for daily spending summaries

CREATE VIEW IF NOT EXISTS v_daily_costs AS
SELECT
    date(created_at) as day,
    provider,
    feature,
    COUNT(*) as request_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(total_tokens) as total_tokens,
    ROUND(SUM(total_cost), 4) as total_cost_usd,
    ROUND(AVG(latency_ms), 0) as avg_latency_ms,
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests
FROM cost_logs
GROUP BY date(created_at), provider, feature
ORDER BY date(created_at) DESC, total_cost_usd DESC;

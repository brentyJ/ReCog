"""
ReCog Core - Cost Tracking v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Tracks token usage and costs per LLM request.
Provides visibility into spending before costs spiral.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# =============================================================================
# PRICING CONFIGURATION
# =============================================================================
# Prices in USD per 1M tokens (as of 2025)
# Update these when provider pricing changes

PRICING = {
    "anthropic": {
        # Claude 3.5 Sonnet
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
        # Claude 3 Haiku (fallback)
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        # Default for unknown models
        "_default": {"input": 3.00, "output": 15.00},
    },
    "openai": {
        # GPT-4o mini (primary cost-effective)
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
        # GPT-4o (premium)
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
        # Default for unknown models
        "_default": {"input": 0.15, "output": 0.60},
    },
    # Fallback for unknown providers
    "_default": {"input": 1.00, "output": 5.00},
}


@dataclass
class CostEntry:
    """A single cost log entry."""
    id: int
    user_id: str
    feature: str
    case_id: Optional[str]
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    latency_ms: Optional[int]
    success: bool
    error_message: Optional[str]
    created_at: datetime


@dataclass
class CostSummary:
    """Summary of costs over a period."""
    period_start: datetime
    period_end: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost: float
    by_provider: Dict[str, Dict[str, Any]]
    by_feature: Dict[str, Dict[str, Any]]


class CostTracker:
    """
    Tracks LLM API costs to SQLite.

    Usage:
        tracker = CostTracker(db_path)
        tracker.log_request(
            feature="extraction",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            input_tokens=1000,
            output_tokens=500,
        )

        summary = tracker.get_summary(days=7)
        print(f"Last 7 days: ${summary.total_cost:.2f}")
    """

    def __init__(self, db_path: Path):
        """
        Initialize cost tracker.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self):
        """Ensure cost_logs table exists (for fresh DBs)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cost_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                feature TEXT NOT NULL,
                case_id TEXT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                input_cost REAL NOT NULL DEFAULT 0.0,
                output_cost REAL NOT NULL DEFAULT 0.0,
                total_cost REAL NOT NULL DEFAULT 0.0,
                latency_ms INTEGER,
                success INTEGER NOT NULL DEFAULT 1,
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Create indexes if not exist
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_logs_created_at ON cost_logs(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_logs_feature ON cost_logs(feature)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_logs_provider ON cost_logs(provider)")

        conn.commit()
        conn.close()

    def _calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> tuple[float, float, float]:
        """
        Calculate cost for token usage.

        Args:
            provider: Provider name
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Tuple of (input_cost, output_cost, total_cost) in USD
        """
        # Get pricing for provider/model
        provider_pricing = PRICING.get(provider, PRICING["_default"])

        if isinstance(provider_pricing, dict) and model in provider_pricing:
            model_pricing = provider_pricing[model]
        elif isinstance(provider_pricing, dict) and "_default" in provider_pricing:
            model_pricing = provider_pricing["_default"]
        else:
            model_pricing = PRICING["_default"]

        # Calculate costs (prices are per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
        output_cost = (output_tokens / 1_000_000) * model_pricing["output"]
        total_cost = input_cost + output_cost

        return input_cost, output_cost, total_cost

    def log_request(
        self,
        feature: str,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        user_id: str = "default",
        case_id: Optional[str] = None,
        latency_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> int:
        """
        Log an LLM API request.

        Args:
            feature: Feature that made the request (extraction, synthesis, etc.)
            provider: LLM provider name
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            user_id: User identifier (default: "default")
            case_id: Optional case ID
            latency_ms: Response time in milliseconds
            success: Whether request succeeded
            error_message: Error details if failed

        Returns:
            ID of the created log entry
        """
        # Calculate costs
        input_cost, output_cost, total_cost = self._calculate_cost(
            provider, model, input_tokens, output_tokens
        )
        total_tokens = input_tokens + output_tokens

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO cost_logs (
                user_id, feature, case_id, provider, model,
                input_tokens, output_tokens, total_tokens,
                input_cost, output_cost, total_cost,
                latency_ms, success, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            user_id, feature, case_id, provider, model,
            input_tokens, output_tokens, total_tokens,
            input_cost, output_cost, total_cost,
            latency_ms, 1 if success else 0, error_message
        ))

        log_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Log for debugging
        logger.debug(
            f"Cost logged: {feature} via {provider}/{model} - "
            f"{total_tokens} tokens, ${total_cost:.4f}"
        )

        return log_id

    def get_summary(
        self,
        days: int = 7,
        user_id: Optional[str] = None,
        feature: Optional[str] = None,
    ) -> CostSummary:
        """
        Get cost summary for a period.

        Args:
            days: Number of days to include (default: 7)
            user_id: Filter by user (optional)
            feature: Filter by feature (optional)

        Returns:
            CostSummary with totals and breakdowns
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build query
        period_start = datetime.now() - timedelta(days=days)
        period_end = datetime.now()

        where_clauses = ["created_at >= ?"]
        params = [period_start.isoformat()]

        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)

        if feature:
            where_clauses.append("feature = ?")
            params.append(feature)

        where_sql = " AND ".join(where_clauses)

        # Get totals
        cursor.execute(f"""
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests,
                COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(total_cost), 0) as total_cost
            FROM cost_logs
            WHERE {where_sql}
        """, params)

        row = cursor.fetchone()

        # Get breakdown by provider
        cursor.execute(f"""
            SELECT
                provider,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM cost_logs
            WHERE {where_sql}
            GROUP BY provider
        """, params)

        by_provider = {}
        for prow in cursor.fetchall():
            by_provider[prow["provider"]] = {
                "requests": prow["requests"],
                "tokens": prow["tokens"] or 0,
                "cost": prow["cost"] or 0,
            }

        # Get breakdown by feature
        cursor.execute(f"""
            SELECT
                feature,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM cost_logs
            WHERE {where_sql}
            GROUP BY feature
        """, params)

        by_feature = {}
        for frow in cursor.fetchall():
            by_feature[frow["feature"]] = {
                "requests": frow["requests"],
                "tokens": frow["tokens"] or 0,
                "cost": frow["cost"] or 0,
            }

        conn.close()

        return CostSummary(
            period_start=period_start,
            period_end=period_end,
            total_requests=row["total_requests"] or 0,
            successful_requests=row["successful_requests"] or 0,
            failed_requests=row["failed_requests"] or 0,
            total_input_tokens=row["total_input_tokens"] or 0,
            total_output_tokens=row["total_output_tokens"] or 0,
            total_tokens=row["total_tokens"] or 0,
            total_cost=row["total_cost"] or 0,
            by_provider=by_provider,
            by_feature=by_feature,
        )

    def get_daily_breakdown(
        self,
        days: int = 7,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get day-by-day cost breakdown.

        Args:
            days: Number of days to include
            user_id: Filter by user (optional)

        Returns:
            List of daily summaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        period_start = datetime.now() - timedelta(days=days)

        params = [period_start.isoformat()]
        user_filter = ""
        if user_id:
            user_filter = "AND user_id = ?"
            params.append(user_id)

        cursor.execute(f"""
            SELECT
                date(created_at) as day,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                ROUND(SUM(total_cost), 4) as cost,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
            FROM cost_logs
            WHERE created_at >= ? {user_filter}
            GROUP BY date(created_at)
            ORDER BY day DESC
        """, params)

        results = []
        for row in cursor.fetchall():
            results.append({
                "day": row["day"],
                "requests": row["requests"],
                "tokens": row["tokens"] or 0,
                "cost": row["cost"] or 0,
                "failed": row["failed"],
            })

        conn.close()
        return results

    def get_recent_requests(
        self,
        limit: int = 20,
        feature: Optional[str] = None,
    ) -> List[CostEntry]:
        """
        Get most recent cost log entries.

        Args:
            limit: Maximum entries to return
            feature: Filter by feature (optional)

        Returns:
            List of CostEntry objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if feature:
            cursor.execute("""
                SELECT * FROM cost_logs
                WHERE feature = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (feature, limit))
        else:
            cursor.execute("""
                SELECT * FROM cost_logs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

        entries = []
        for row in cursor.fetchall():
            entries.append(CostEntry(
                id=row["id"],
                user_id=row["user_id"],
                feature=row["feature"],
                case_id=row["case_id"],
                provider=row["provider"],
                model=row["model"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                total_tokens=row["total_tokens"],
                input_cost=row["input_cost"],
                output_cost=row["output_cost"],
                total_cost=row["total_cost"],
                latency_ms=row["latency_ms"],
                success=bool(row["success"]),
                error_message=row["error_message"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ))

        conn.close()
        return entries


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================
# Global tracker instance for convenience

_tracker_instance: Optional[CostTracker] = None


def get_cost_tracker(db_path: Optional[Path] = None) -> CostTracker:
    """
    Get the global cost tracker instance.

    Args:
        db_path: Database path (only needed on first call)

    Returns:
        CostTracker instance
    """
    global _tracker_instance

    if _tracker_instance is None:
        if db_path is None:
            # Default to _data/recog.db relative to _scripts directory
            scripts_dir = Path(__file__).parent.parent
            db_path = scripts_dir / "_data" / "recog.db"
        _tracker_instance = CostTracker(db_path)

    return _tracker_instance


def log_llm_cost(
    feature: str,
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    case_id: Optional[str] = None,
) -> None:
    """
    Convenience function to log LLM cost.

    Uses the global tracker instance.
    """
    try:
        tracker = get_cost_tracker()
        tracker.log_request(
            feature=feature,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
            case_id=case_id,
        )
    except Exception as e:
        # Don't let cost tracking failures break the main flow
        logger.warning(f"Failed to log cost: {e}")


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "CostTracker",
    "CostEntry",
    "CostSummary",
    "PRICING",
    "get_cost_tracker",
    "log_llm_cost",
]

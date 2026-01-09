"""
ReCog Engine - Cost Estimator v0.8

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Estimates API costs before extraction/synthesis.
Provides cost breakdowns for user confirmation before LLM operations.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# COST TABLES
# =============================================================================

# Token costs per 1M tokens (as of Jan 2025)
MODEL_COSTS = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},

    # Anthropic
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},

    # Aliases
    "claude-sonnet-4.5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4.5": {"input": 0.80, "output": 4.00},
}

# Default model for cost estimation
DEFAULT_MODEL = "gpt-4o-mini"


# =============================================================================
# COST ESTIMATOR
# =============================================================================

class CostEstimator:
    """
    Estimate token costs for case processing.

    Provides estimates for:
    - Document extraction costs
    - Synthesis costs
    - Total pipeline costs
    """

    def __init__(self, db_path: Path, model: str = None):
        """
        Initialize cost estimator.

        Args:
            db_path: Path to SQLite database
            model: Model name for cost lookup (default: gpt-4o-mini)
        """
        self.db_path = Path(db_path)
        self.model = model or DEFAULT_MODEL

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _get_model_costs(self, model: str = None) -> Dict[str, float]:
        """Get input/output costs for model."""
        model = model or self.model
        return MODEL_COSTS.get(model, MODEL_COSTS[DEFAULT_MODEL])

    def _words_to_tokens(self, word_count: int) -> int:
        """
        Estimate tokens from word count.

        Rule of thumb: ~1.3 tokens per word for English text.
        """
        return int(word_count * 1.3)

    # =========================================================================
    # EXTRACTION COST ESTIMATION
    # =========================================================================

    def estimate_extraction_cost(
        self,
        case_id: str,
        model: str = None
    ) -> Dict[str, Any]:
        """
        Estimate cost for extracting insights from case documents.

        Args:
            case_id: Case UUID
            model: Optional model override

        Returns:
            Dict with:
                - document_count: Number of documents
                - total_words: Total word count
                - estimated_input_tokens: Input tokens estimate
                - estimated_output_tokens: Output tokens estimate
                - estimated_tokens: Total tokens
                - estimated_cost_usd: Cost in USD
                - model: Model used for estimate
        """
        conn = self._connect()
        try:
            # Get total word count and document count from preflight items
            result = conn.execute("""
                SELECT
                    COALESCE(SUM(pi.word_count), 0) as total_words,
                    COUNT(*) as doc_count
                FROM preflight_items pi
                JOIN preflight_sessions ps ON pi.preflight_session_id = ps.id
                WHERE ps.case_id = ? AND pi.included = 1
            """, (case_id,)).fetchone()

            total_words = result["total_words"] or 0
            doc_count = result["doc_count"] or 0

            if doc_count == 0:
                return {
                    "document_count": 0,
                    "total_words": 0,
                    "estimated_input_tokens": 0,
                    "estimated_output_tokens": 0,
                    "estimated_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "model": model or self.model,
                }

            # Calculate tokens
            # Input: document content + system prompt (~1000 tokens per doc)
            content_tokens = self._words_to_tokens(total_words)
            system_prompt_tokens = doc_count * 1000
            input_tokens = content_tokens + system_prompt_tokens

            # Output: ~500 tokens per document for insights
            output_tokens = doc_count * 500

            # Calculate cost
            costs = self._get_model_costs(model)
            input_cost = (input_tokens / 1_000_000) * costs["input"]
            output_cost = (output_tokens / 1_000_000) * costs["output"]
            total_cost = input_cost + output_cost

            return {
                "document_count": doc_count,
                "total_words": total_words,
                "estimated_input_tokens": input_tokens,
                "estimated_output_tokens": output_tokens,
                "estimated_tokens": input_tokens + output_tokens,
                "estimated_cost_usd": round(total_cost, 4),
                "model": model or self.model,
            }

        finally:
            conn.close()

    # =========================================================================
    # SYNTHESIS COST ESTIMATION
    # =========================================================================

    def estimate_synthesis_cost(
        self,
        case_id: str,
        model: str = None
    ) -> Dict[str, Any]:
        """
        Estimate cost for running synthesis on case insights.

        Args:
            case_id: Case UUID
            model: Optional model override

        Returns:
            Dict with token and cost estimates
        """
        conn = self._connect()
        try:
            # Get insight count for case
            result = conn.execute("""
                SELECT COUNT(*) as insight_count
                FROM insights
                WHERE case_id = ?
            """, (case_id,)).fetchone()

            insight_count = result["insight_count"] or 0

            if insight_count == 0:
                return {
                    "insight_count": 0,
                    "estimated_clusters": 0,
                    "estimated_input_tokens": 0,
                    "estimated_output_tokens": 0,
                    "estimated_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "model": model or self.model,
                }

            # Estimate clusters (roughly 1 cluster per 5-10 insights)
            estimated_clusters = max(1, insight_count // 7)

            # Input: ~200 tokens per insight summary + system prompt per cluster
            input_tokens = (insight_count * 200) + (estimated_clusters * 500)

            # Output: ~300 tokens per pattern
            output_tokens = estimated_clusters * 300

            # Calculate cost
            costs = self._get_model_costs(model)
            input_cost = (input_tokens / 1_000_000) * costs["input"]
            output_cost = (output_tokens / 1_000_000) * costs["output"]
            total_cost = input_cost + output_cost

            return {
                "insight_count": insight_count,
                "estimated_clusters": estimated_clusters,
                "estimated_input_tokens": input_tokens,
                "estimated_output_tokens": output_tokens,
                "estimated_tokens": input_tokens + output_tokens,
                "estimated_cost_usd": round(total_cost, 4),
                "model": model or self.model,
            }

        finally:
            conn.close()

    # =========================================================================
    # TOTAL PIPELINE COST
    # =========================================================================

    def estimate_total_cost(
        self,
        case_id: str,
        model: str = None
    ) -> Dict[str, Any]:
        """
        Estimate total cost for full pipeline (extraction + synthesis).

        Args:
            case_id: Case UUID
            model: Optional model override

        Returns:
            Dict with combined estimates
        """
        extraction = self.estimate_extraction_cost(case_id, model)
        synthesis = self.estimate_synthesis_cost(case_id, model)

        total_tokens = extraction["estimated_tokens"] + synthesis["estimated_tokens"]
        total_cost = extraction["estimated_cost_usd"] + synthesis["estimated_cost_usd"]

        return {
            "extraction": extraction,
            "synthesis": synthesis,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "model": model or self.model,
        }

    # =========================================================================
    # COST TRACKING
    # =========================================================================

    def record_actual_cost(
        self,
        case_id: str,
        cost_usd: float,
        operation: str = None
    ):
        """
        Record actual cost to case.

        Args:
            case_id: Case UUID
            cost_usd: Cost in USD
            operation: Optional operation description
        """
        conn = self._connect()
        try:
            conn.execute("""
                UPDATE cases
                SET actual_cost = COALESCE(actual_cost, 0) + ?
                WHERE id = ?
            """, (cost_usd, case_id))
            conn.commit()

            if operation:
                logger.info(f"Case {case_id} {operation}: ${cost_usd:.4f}")
        finally:
            conn.close()

    def update_estimated_cost(self, case_id: str, cost_usd: float):
        """Update estimated cost on case record."""
        conn = self._connect()
        try:
            conn.execute("""
                UPDATE cases
                SET estimated_cost = ?
                WHERE id = ?
            """, (cost_usd, case_id))
            conn.commit()
        finally:
            conn.close()


# =============================================================================
# STANDALONE FUNCTIONS
# =============================================================================

def estimate_extraction_cost(case_id: str, db_path: Path, model: str = None) -> Dict[str, Any]:
    """Convenience function for extraction cost estimate."""
    estimator = CostEstimator(db_path, model)
    return estimator.estimate_extraction_cost(case_id)


def estimate_total_cost(case_id: str, db_path: Path, model: str = None) -> Dict[str, Any]:
    """Convenience function for total cost estimate."""
    estimator = CostEstimator(db_path, model)
    return estimator.estimate_total_cost(case_id)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "CostEstimator",
    "MODEL_COSTS",
    "estimate_extraction_cost",
    "estimate_total_cost",
]

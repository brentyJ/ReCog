"""
ReCog Engine - Insight Store v0.1

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Database persistence layer for extracted insights.
Handles CRUD operations, similarity checking, and history tracking.
"""

import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4

from .extraction import (
    ExtractedInsight,
    find_similar_insight,
    merge_insights,
    should_surface,
)

logger = logging.getLogger(__name__)


class InsightStore:
    """
    Database persistence for extracted insights.
    
    Handles:
    - Insight CRUD operations
    - Source linking
    - History tracking
    - Similarity-based deduplication
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize insight store.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        
    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    # =========================================================================
    # CORE CRUD
    # =========================================================================
    
    def save_insight(
        self,
        insight: ExtractedInsight,
        check_similarity: bool = True,
        similarity_threshold: float = 0.7,
        case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save an insight to the database.
        
        If check_similarity is True, will look for existing similar insights
        and merge rather than create duplicate.
        
        Args:
            insight: The ExtractedInsight to save
            check_similarity: Whether to check for existing similar insights
            similarity_threshold: Threshold for similarity matching
            
        Returns:
            Dict with 'id', 'action' ('created', 'merged', 'updated'), and insight data
        """
        conn = self._connect()
        try:
            # Check for similarity if requested
            if check_similarity:
                existing = self._get_all_active_insights(conn)
                match = find_similar_insight(insight, existing, similarity_threshold)
                
                if match:
                    existing_insight, score = match
                    merged = merge_insights(existing_insight, insight)
                    self._update_insight(conn, merged)
                    self._add_source(conn, merged.id, insight.source_type, insight.source_id)
                    self._log_history(conn, merged.id, "source_added", {
                        "new_source_type": insight.source_type,
                        "new_source_id": insight.source_id,
                        "similarity_score": score,
                    })
                    conn.commit()
                    
                    logger.info(f"Merged insight {insight.id} into {merged.id} (score: {score:.2f})")
                    return {
                        "id": merged.id,
                        "action": "merged",
                        "merged_into": merged.id,
                        "similarity_score": score,
                        "insight": merged.to_dict(),
                    }
            
            # Check if this exact ID exists (update case)
            existing = self._get_insight_by_id(conn, insight.id)
            if existing:
                self._update_insight(conn, insight)
                self._log_history(conn, insight.id, "updated", {"trigger": "save_insight"})
                conn.commit()
                return {
                    "id": insight.id,
                    "action": "updated",
                    "insight": insight.to_dict(),
                }
            
            # Create new insight
            self._insert_insight(conn, insight, case_id=case_id)
            self._add_source(conn, insight.id, insight.source_type, insight.source_id)
            self._log_history(conn, insight.id, "created", {
                "source_type": insight.source_type,
                "source_id": insight.source_id,
            })
            conn.commit()
            
            logger.info(f"Created insight {insight.id}")
            return {
                "id": insight.id,
                "action": "created",
                "insight": insight.to_dict(),
            }
            
        finally:
            conn.close()
    
    def save_insights_batch(
        self,
        insights: List[ExtractedInsight],
        check_similarity: bool = True,
        case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save multiple insights in a batch.
        
        Args:
            insights: List of ExtractedInsight objects
            check_similarity: Whether to check for duplicates
            case_id: Optional case UUID to associate insights with
            
        Returns:
            Dict with counts and results
        """
        results = []
        created = 0
        merged = 0
        
        for insight in insights:
            result = self.save_insight(insight, check_similarity=check_similarity, case_id=case_id)
            results.append(result)
            if result["action"] == "created":
                created += 1
            elif result["action"] == "merged":
                merged += 1
        
        return {
            "total": len(insights),
            "created": created,
            "merged": merged,
            "results": results,
        }
    
    def get_insight(self, insight_id: str) -> Optional[Dict]:
        """
        Get a single insight by ID.
        
        Args:
            insight_id: UUID of the insight
            
        Returns:
            Insight dict or None if not found
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM insights WHERE id = ?",
                (insight_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return self._row_to_dict(row)
        finally:
            conn.close()
    
    def list_insights(
        self,
        status: Optional[str] = None,
        min_significance: Optional[float] = None,
        insight_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "significance",
        order_dir: str = "DESC",
    ) -> Dict[str, Any]:
        """
        List insights with filters.
        
        Args:
            status: Filter by status (raw, refined, surfaced, rejected)
            min_significance: Minimum significance score
            insight_type: Filter by insight type
            limit: Maximum results
            offset: Pagination offset
            order_by: Column to sort by
            order_dir: ASC or DESC
            
        Returns:
            Dict with 'insights' list and 'total' count
        """
        conn = self._connect()
        try:
            # Build query
            conditions = ["status != 'merged'"]  # Don't show merged insights
            params = []
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            if min_significance is not None:
                conditions.append("significance >= ?")
                params.append(min_significance)
            
            if insight_type:
                conditions.append("insight_type = ?")
                params.append(insight_type)
            
            where_clause = " AND ".join(conditions)
            
            # Validate order_by to prevent SQL injection
            valid_columns = ["significance", "confidence", "created_at", "updated_at", "source_count"]
            if order_by not in valid_columns:
                order_by = "significance"
            
            order_dir = "DESC" if order_dir.upper() == "DESC" else "ASC"
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM insights WHERE {where_clause}"
            total = conn.execute(count_query, params).fetchone()[0]
            
            # Get results with source info (first source for each insight)
            query = f"""
                SELECT i.*,
                       (SELECT source_id FROM insight_sources WHERE insight_id = i.id ORDER BY added_at LIMIT 1) as source_id,
                       (SELECT source_type FROM insight_sources WHERE insight_id = i.id ORDER BY added_at LIMIT 1) as source_type
                FROM insights i
                WHERE {where_clause}
                ORDER BY {order_by} {order_dir}
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            rows = conn.execute(query, params).fetchall()
            
            return {
                "insights": [self._row_to_dict(row) for row in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
            
        finally:
            conn.close()
    
    def update_insight(
        self,
        insight_id: str,
        status: Optional[str] = None,
        significance: Optional[float] = None,
        themes: Optional[List[str]] = None,
        patterns: Optional[List[str]] = None,
    ) -> bool:
        """
        Update specific fields of an insight.
        
        Args:
            insight_id: UUID of the insight
            status: New status
            significance: New significance score
            themes: New themes list
            patterns: New patterns list
            
        Returns:
            True if updated, False if not found
        """
        conn = self._connect()
        try:
            # Build update
            updates = []
            params = []
            
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            
            if significance is not None:
                updates.append("significance = ?")
                params.append(significance)
            
            if themes is not None:
                updates.append("themes_json = ?")
                params.append(json.dumps(themes))
            
            if patterns is not None:
                updates.append("patterns_json = ?")
                params.append(json.dumps(patterns))
            
            if not updates:
                return False
            
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat() + "Z")
            params.append(insight_id)
            
            query = f"UPDATE insights SET {', '.join(updates)} WHERE id = ?"
            cursor = conn.execute(query, params)
            
            if cursor.rowcount > 0:
                self._log_history(conn, insight_id, "updated", {
                    "status": status,
                    "significance": significance,
                })
                conn.commit()
                return True
            
            return False
            
        finally:
            conn.close()
    
    def delete_insight(self, insight_id: str, soft: bool = True) -> bool:
        """
        Delete an insight.
        
        Args:
            insight_id: UUID of the insight
            soft: If True, set status to 'rejected' instead of deleting
            
        Returns:
            True if deleted/rejected, False if not found
        """
        conn = self._connect()
        try:
            if soft:
                cursor = conn.execute(
                    "UPDATE insights SET status = 'rejected', updated_at = ? WHERE id = ?",
                    (datetime.utcnow().isoformat() + "Z", insight_id)
                )
            else:
                cursor = conn.execute("DELETE FROM insights WHERE id = ?", (insight_id,))
            
            if cursor.rowcount > 0:
                self._log_history(conn, insight_id, "rejected" if soft else "deleted", {})
                conn.commit()
                return True
            
            return False
            
        finally:
            conn.close()
    
    # =========================================================================
    # SOURCE MANAGEMENT
    # =========================================================================
    
    def get_sources(self, insight_id: str) -> List[Dict]:
        """
        Get all sources for an insight.
        
        Args:
            insight_id: UUID of the insight
            
        Returns:
            List of source dicts
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM insight_sources WHERE insight_id = ? ORDER BY added_at",
                (insight_id,)
            ).fetchall()
            
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_source_count(self, insight_id: str) -> int:
        """Get count of sources for an insight."""
        conn = self._connect()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM insight_sources WHERE insight_id = ?",
                (insight_id,)
            ).fetchone()[0]
            return count
        finally:
            conn.close()
    
    # =========================================================================
    # HISTORY
    # =========================================================================
    
    def get_history(self, insight_id: str) -> List[Dict]:
        """
        Get history for an insight.
        
        Args:
            insight_id: UUID of the insight
            
        Returns:
            List of history event dicts
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM insight_history WHERE insight_id = ? ORDER BY event_at DESC",
                (insight_id,)
            ).fetchall()
            
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get insight statistics."""
        conn = self._connect()
        try:
            # Count by status
            status_counts = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) as count FROM insights GROUP BY status"
            ).fetchall():
                status_counts[row["status"]] = row["count"]
            
            # Count by type
            type_counts = {}
            for row in conn.execute(
                "SELECT insight_type, COUNT(*) as count FROM insights GROUP BY insight_type"
            ).fetchall():
                type_counts[row["insight_type"] or "unknown"] = row["count"]
            
            # Averages
            averages = conn.execute("""
                SELECT 
                    AVG(significance) as avg_significance,
                    AVG(confidence) as avg_confidence,
                    AVG(source_count) as avg_sources
                FROM insights
                WHERE status != 'rejected'
            """).fetchone()
            
            # Total
            total = conn.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
            
            return {
                "total": total,
                "by_status": status_counts,
                "by_type": type_counts,
                "averages": {
                    "significance": round(averages["avg_significance"] or 0, 3),
                    "confidence": round(averages["avg_confidence"] or 0, 3),
                    "sources": round(averages["avg_sources"] or 0, 1),
                },
            }
            
        finally:
            conn.close()
    
    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================
    
    def _insert_insight(
        self,
        conn: sqlite3.Connection,
        insight: ExtractedInsight,
        case_id: Optional[str] = None,
    ) -> None:
        """Insert a new insight."""
        now = datetime.utcnow().isoformat() + "Z"
        
        conn.execute("""
            INSERT INTO insights (
                id, summary, themes_json, emotional_tags_json, patterns_json,
                significance, confidence, insight_type, status,
                source_count, excerpt, created_at, updated_at, case_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            insight.id,
            insight.summary,
            json.dumps(insight.themes),
            json.dumps(insight.emotional_tags),
            json.dumps(insight.patterns),
            insight.significance,
            insight.confidence,
            insight.insight_type,
            "raw",
            1,
            insight.excerpt,
            insight.created_at or now,
            now,
            case_id,
        ))
    
    def _update_insight(self, conn: sqlite3.Connection, insight: ExtractedInsight) -> None:
        """Update an existing insight."""
        now = datetime.utcnow().isoformat() + "Z"
        
        # Get current source count
        source_count = conn.execute(
            "SELECT COUNT(*) FROM insight_sources WHERE insight_id = ?",
            (insight.id,)
        ).fetchone()[0] + 1  # +1 for new source being added
        
        conn.execute("""
            UPDATE insights SET
                themes_json = ?,
                emotional_tags_json = ?,
                patterns_json = ?,
                significance = ?,
                confidence = ?,
                source_count = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            json.dumps(insight.themes),
            json.dumps(insight.emotional_tags),
            json.dumps(insight.patterns),
            insight.significance,
            insight.confidence,
            source_count,
            now,
            insight.id,
        ))
    
    def _add_source(
        self,
        conn: sqlite3.Connection,
        insight_id: str,
        source_type: str,
        source_id: str,
        excerpt: str = "",
    ) -> None:
        """Add a source link for an insight."""
        # Check if this exact source already exists
        existing = conn.execute(
            "SELECT id FROM insight_sources WHERE insight_id = ? AND source_type = ? AND source_id = ?",
            (insight_id, source_type, source_id)
        ).fetchone()
        
        if not existing:
            conn.execute("""
                INSERT INTO insight_sources (insight_id, source_type, source_id, excerpt, added_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                insight_id,
                source_type,
                source_id,
                excerpt,
                datetime.utcnow().isoformat() + "Z",
            ))
    
    def _log_history(
        self,
        conn: sqlite3.Connection,
        insight_id: str,
        event_type: str,
        data: Dict,
    ) -> None:
        """Log an event to insight history."""
        conn.execute("""
            INSERT INTO insight_history (insight_id, event_type, event_at, new_value, trigger)
            VALUES (?, ?, ?, ?, ?)
        """, (
            insight_id,
            event_type,
            datetime.utcnow().isoformat() + "Z",
            json.dumps(data),
            data.get("trigger", event_type),
        ))
    
    def _get_insight_by_id(
        self,
        conn: sqlite3.Connection,
        insight_id: str,
    ) -> Optional[ExtractedInsight]:
        """Get insight by ID (internal, returns ExtractedInsight)."""
        row = conn.execute(
            "SELECT * FROM insights WHERE id = ?",
            (insight_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return ExtractedInsight(
            id=row["id"],
            summary=row["summary"],
            themes=json.loads(row["themes_json"] or "[]"),
            emotional_tags=json.loads(row["emotional_tags_json"] or "[]"),
            patterns=json.loads(row["patterns_json"] or "[]"),
            significance=row["significance"],
            confidence=row["confidence"],
            excerpt=row["excerpt"] or "",
            insight_type=row["insight_type"] or "observation",
            created_at=row["created_at"],
        )
    
    def _get_all_active_insights(self, conn: sqlite3.Connection) -> List[ExtractedInsight]:
        """Get all non-rejected insights for similarity checking."""
        rows = conn.execute(
            "SELECT * FROM insights WHERE status NOT IN ('rejected', 'merged')"
        ).fetchall()
        
        insights = []
        for row in rows:
            insights.append(ExtractedInsight(
                id=row["id"],
                summary=row["summary"],
                themes=json.loads(row["themes_json"] or "[]"),
                emotional_tags=json.loads(row["emotional_tags_json"] or "[]"),
                patterns=json.loads(row["patterns_json"] or "[]"),
                significance=row["significance"],
                confidence=row["confidence"],
                excerpt=row["excerpt"] or "",
                insight_type=row["insight_type"] or "observation",
                created_at=row["created_at"],
            ))
        
        return insights
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert a database row to a dict with parsed JSON fields."""
        keys = row.keys()
        result = {
            "id": row["id"],
            "summary": row["summary"],
            "themes": json.loads(row["themes_json"] or "[]"),
            "emotional_tags": json.loads(row["emotional_tags_json"] or "[]"),
            "patterns": json.loads(row["patterns_json"] or "[]"),
            "significance": row["significance"],
            "confidence": row["confidence"],
            "insight_type": row["insight_type"],
            "status": row["status"],
            "source_count": row["source_count"],
            "excerpt": row["excerpt"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "case_id": row["case_id"] if "case_id" in keys else None,
        }
        # Include source info if available (from joined query)
        if "source_id" in keys:
            result["source_id"] = row["source_id"]
        if "source_type" in keys:
            result["source_type"] = row["source_type"]
        return result


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "InsightStore",
]

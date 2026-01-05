"""
ReCog Engine - Findings Store v0.1

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Database persistence layer for Findings.
Findings are validated insights promoted for case analysis.
"""

import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Finding:
    """A validated insight promoted for case analysis."""
    id: str
    case_id: str
    insight_id: str
    status: str  # verified, needs_verification, rejected
    tags: List[str] = field(default_factory=list)
    user_notes: str = ""
    verified_at: Optional[str] = None
    verified_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    
    # Populated when joined with insight
    insight_summary: str = ""
    insight_significance: float = 0.5
    insight_confidence: float = 0.5
    insight_excerpt: str = ""
    insight_themes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "case_id": self.case_id,
            "insight_id": self.insight_id,
            "status": self.status,
            "tags": self.tags,
            "user_notes": self.user_notes,
            "verified_at": self.verified_at,
            "verified_by": self.verified_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            # Include insight details if populated
            "insight": {
                "summary": self.insight_summary,
                "significance": self.insight_significance,
                "confidence": self.insight_confidence,
                "excerpt": self.insight_excerpt,
                "themes": self.insight_themes,
            } if self.insight_summary else None,
        }
    
    @classmethod
    def from_row(cls, row: sqlite3.Row, include_insight: bool = False) -> "Finding":
        """Create from database row."""
        finding = cls(
            id=row["id"],
            case_id=row["case_id"],
            insight_id=row["insight_id"],
            status=row["status"],
            tags=json.loads(row["tags_json"] or "[]"),
            user_notes=row["user_notes"] or "",
            verified_at=row["verified_at"],
            verified_by=row["verified_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        
        # Populate insight details if available in row
        if include_insight and "insight_summary" in row.keys():
            finding.insight_summary = row["insight_summary"] or ""
            finding.insight_significance = row["insight_significance"] or 0.5
            finding.insight_confidence = row["insight_confidence"] or 0.5
            finding.insight_excerpt = row["insight_excerpt"] or ""
            finding.insight_themes = json.loads(row["insight_themes_json"] or "[]")
        
        return finding


# =============================================================================
# FINDINGS STORE
# =============================================================================

class FindingsStore:
    """
    Database persistence for Findings.
    
    Handles:
    - Promoting insights to findings
    - Finding status management (verified/rejected)
    - Finding annotations
    - Auto-promotion logic
    """
    
    def __init__(self, db_path: Path):
        """Initialize findings store."""
        self.db_path = Path(db_path)
        
    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _now(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.utcnow().isoformat() + "Z"
    
    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================
    
    def promote_insight(
        self,
        case_id: str,
        insight_id: str,
        auto_verify: bool = False,
        tags: Optional[List[str]] = None,
        user_notes: str = "",
    ) -> Optional[Finding]:
        """
        Promote an insight to a finding.
        
        Args:
            case_id: UUID of the case
            insight_id: UUID of the insight to promote
            auto_verify: If True, set status to 'verified' immediately
            tags: Optional tags for categorization
            user_notes: Optional notes
            
        Returns:
            Finding object or None if case/insight not found or already promoted
        """
        conn = self._connect()
        try:
            # Verify case exists
            case = conn.execute(
                "SELECT id FROM cases WHERE id = ?",
                (case_id,)
            ).fetchone()
            if not case:
                logger.warning(f"Case {case_id} not found")
                return None
            
            # Verify insight exists
            insight = conn.execute(
                "SELECT id FROM insights WHERE id = ?",
                (insight_id,)
            ).fetchone()
            if not insight:
                logger.warning(f"Insight {insight_id} not found")
                return None
            
            finding_id = str(uuid4())
            now = self._now()
            status = "verified" if auto_verify else "needs_verification"
            verified_at = now if auto_verify else None
            verified_by = "auto" if auto_verify else None
            
            try:
                conn.execute("""
                    INSERT INTO findings (
                        id, case_id, insight_id, status, verified_at, verified_by,
                        tags_json, user_notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    finding_id, case_id, insight_id, status, verified_at, verified_by,
                    json.dumps(tags or []), user_notes, now, now
                ))
            except sqlite3.IntegrityError:
                logger.warning(f"Insight {insight_id} already promoted in case {case_id}")
                return None
            
            # Update insight's case_id
            conn.execute(
                "UPDATE insights SET case_id = ? WHERE id = ?",
                (case_id, insight_id)
            )
            
            # Update case findings count
            conn.execute(
                "UPDATE cases SET findings_count = findings_count + 1, updated_at = ? WHERE id = ?",
                (now, case_id)
            )
            
            # Log timeline event
            self._log_timeline_event(conn, case_id, "finding_added", {
                "finding_id": finding_id,
                "insight_id": insight_id,
                "auto_verified": auto_verify,
            })
            
            conn.commit()
            
            logger.info(f"Promoted insight {insight_id} to finding {finding_id}")
            
            return Finding(
                id=finding_id,
                case_id=case_id,
                insight_id=insight_id,
                status=status,
                tags=tags or [],
                user_notes=user_notes,
                verified_at=verified_at,
                verified_by=verified_by,
                created_at=now,
                updated_at=now,
            )
            
        finally:
            conn.close()
    
    def get_finding(self, finding_id: str, include_insight: bool = True) -> Optional[Finding]:
        """
        Get a finding by ID.
        
        Args:
            finding_id: UUID of the finding
            include_insight: If True, include insight details
            
        Returns:
            Finding object or None
        """
        conn = self._connect()
        try:
            if include_insight:
                row = conn.execute("""
                    SELECT 
                        f.*,
                        i.summary as insight_summary,
                        i.significance as insight_significance,
                        i.confidence as insight_confidence,
                        i.excerpt as insight_excerpt,
                        i.themes_json as insight_themes_json
                    FROM findings f
                    LEFT JOIN insights i ON f.insight_id = i.id
                    WHERE f.id = ?
                """, (finding_id,)).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM findings WHERE id = ?",
                    (finding_id,)
                ).fetchone()
            
            if not row:
                return None
            
            return Finding.from_row(row, include_insight=include_insight)
            
        finally:
            conn.close()
    
    def list_findings(
        self,
        case_id: str,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        include_insight: bool = True,
    ) -> Dict[str, Any]:
        """
        List findings for a case.
        
        Args:
            case_id: UUID of the case
            status: Filter by status
            tags: Filter by tags (any match)
            limit: Max results
            offset: Pagination offset
            include_insight: Include insight details
            
        Returns:
            Dict with 'findings' list and 'total' count
        """
        conn = self._connect()
        try:
            conditions = ["f.case_id = ?"]
            params = [case_id]
            
            if status:
                conditions.append("f.status = ?")
                params.append(status)
            
            # Tag filtering - check if any of the provided tags are in tags_json
            if tags:
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("f.tags_json LIKE ?")
                    params.append(f'%"{tag}"%')
                conditions.append(f"({' OR '.join(tag_conditions)})")
            
            where_clause = " AND ".join(conditions)
            
            # Get total
            total = conn.execute(
                f"SELECT COUNT(*) FROM findings f WHERE {where_clause}",
                params
            ).fetchone()[0]
            
            # Build query
            if include_insight:
                query = f"""
                    SELECT 
                        f.*,
                        i.summary as insight_summary,
                        i.significance as insight_significance,
                        i.confidence as insight_confidence,
                        i.excerpt as insight_excerpt,
                        i.themes_json as insight_themes_json
                    FROM findings f
                    LEFT JOIN insights i ON f.insight_id = i.id
                    WHERE {where_clause}
                    ORDER BY f.created_at DESC
                    LIMIT ? OFFSET ?
                """
            else:
                query = f"""
                    SELECT * FROM findings f
                    WHERE {where_clause}
                    ORDER BY f.created_at DESC
                    LIMIT ? OFFSET ?
                """
            
            params.extend([limit, offset])
            rows = conn.execute(query, params).fetchall()
            
            return {
                "findings": [Finding.from_row(row, include_insight).to_dict() for row in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
            
        finally:
            conn.close()
    
    def update_status(
        self,
        finding_id: str,
        status: str,
        verified_by: str = "user",
    ) -> bool:
        """
        Update finding status.
        
        Args:
            finding_id: UUID of the finding
            status: New status (verified, needs_verification, rejected)
            verified_by: Who verified ('user' or 'auto')
            
        Returns:
            True if updated, False if not found
        """
        if status not in ("verified", "needs_verification", "rejected"):
            raise ValueError(f"Invalid status: {status}")
        
        conn = self._connect()
        try:
            now = self._now()
            verified_at = now if status == "verified" else None
            
            cursor = conn.execute("""
                UPDATE findings SET 
                    status = ?,
                    verified_at = ?,
                    verified_by = ?,
                    updated_at = ?
                WHERE id = ?
            """, (status, verified_at, verified_by if status == "verified" else None, now, finding_id))
            
            if cursor.rowcount > 0:
                # Get case_id for timeline
                row = conn.execute(
                    "SELECT case_id FROM findings WHERE id = ?",
                    (finding_id,)
                ).fetchone()
                
                if row:
                    event_type = "finding_verified" if status == "verified" else "finding_rejected"
                    self._log_timeline_event(conn, row["case_id"], event_type, {
                        "finding_id": finding_id,
                        "status": status,
                    })
                
                conn.commit()
                logger.info(f"Updated finding {finding_id} status to {status}")
                return True
            
            return False
            
        finally:
            conn.close()
    
    def add_note(self, finding_id: str, note: str) -> bool:
        """
        Add or update user notes on a finding.
        
        Args:
            finding_id: UUID of the finding
            note: Note text
            
        Returns:
            True if updated, False if not found
        """
        conn = self._connect()
        try:
            now = self._now()
            cursor = conn.execute(
                "UPDATE findings SET user_notes = ?, updated_at = ? WHERE id = ?",
                (note, now, finding_id)
            )
            
            if cursor.rowcount > 0:
                conn.commit()
                return True
            
            return False
            
        finally:
            conn.close()
    
    def update_tags(self, finding_id: str, tags: List[str]) -> bool:
        """
        Update finding tags.
        
        Args:
            finding_id: UUID of the finding
            tags: New tags list
            
        Returns:
            True if updated, False if not found
        """
        conn = self._connect()
        try:
            now = self._now()
            cursor = conn.execute(
                "UPDATE findings SET tags_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(tags), now, finding_id)
            )
            
            if cursor.rowcount > 0:
                conn.commit()
                return True
            
            return False
            
        finally:
            conn.close()
    
    def delete_finding(self, finding_id: str) -> bool:
        """
        Remove a finding (demote insight back to standalone).
        
        Args:
            finding_id: UUID of the finding
            
        Returns:
            True if deleted, False if not found
        """
        conn = self._connect()
        try:
            # Get finding details first
            row = conn.execute(
                "SELECT case_id, insight_id FROM findings WHERE id = ?",
                (finding_id,)
            ).fetchone()
            
            if not row:
                return False
            
            case_id = row["case_id"]
            insight_id = row["insight_id"]
            
            # Delete finding
            conn.execute("DELETE FROM findings WHERE id = ?", (finding_id,))
            
            # Clear case_id from insight (make it standalone again)
            conn.execute(
                "UPDATE insights SET case_id = NULL WHERE id = ?",
                (insight_id,)
            )
            
            # Update case count
            conn.execute(
                "UPDATE cases SET findings_count = findings_count - 1, updated_at = ? WHERE id = ?",
                (self._now(), case_id)
            )
            
            conn.commit()
            logger.info(f"Deleted finding {finding_id}")
            return True
            
        finally:
            conn.close()
    
    # =========================================================================
    # AUTO-PROMOTION LOGIC
    # =========================================================================
    
    def auto_promote_insights(
        self,
        case_id: str,
        insight_ids: List[str],
        min_confidence: float = 0.7,
        min_significance: float = 0.6,
    ) -> Dict[str, Any]:
        """
        Auto-promote high-quality insights to findings.
        
        Args:
            case_id: UUID of the case
            insight_ids: List of insight IDs to consider
            min_confidence: Minimum confidence threshold
            min_significance: Minimum significance threshold
            
        Returns:
            Dict with promoted count and details
        """
        conn = self._connect()
        try:
            promoted = []
            skipped = []
            
            for insight_id in insight_ids:
                # Get insight details
                insight = conn.execute("""
                    SELECT id, confidence, significance, status
                    FROM insights WHERE id = ?
                """, (insight_id,)).fetchone()
                
                if not insight:
                    skipped.append({"insight_id": insight_id, "reason": "not_found"})
                    continue
                
                # Check if already a finding
                existing = conn.execute(
                    "SELECT id FROM findings WHERE case_id = ? AND insight_id = ?",
                    (case_id, insight_id)
                ).fetchone()
                
                if existing:
                    skipped.append({"insight_id": insight_id, "reason": "already_promoted"})
                    continue
                
                # Check thresholds
                if insight["confidence"] >= min_confidence and insight["significance"] >= min_significance:
                    # Promote with auto-verify
                    finding = self.promote_insight(
                        case_id, insight_id, 
                        auto_verify=True,
                        tags=["auto-promoted"]
                    )
                    if finding:
                        promoted.append(finding.to_dict())
                else:
                    # Promote without verify
                    finding = self.promote_insight(
                        case_id, insight_id,
                        auto_verify=False,
                        tags=["auto-promoted", "needs-review"]
                    )
                    if finding:
                        promoted.append(finding.to_dict())
            
            return {
                "promoted": len(promoted),
                "skipped": len(skipped),
                "findings": promoted,
                "skip_details": skipped,
            }
            
        finally:
            conn.close()
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self, case_id: str) -> Dict[str, Any]:
        """Get findings statistics for a case."""
        conn = self._connect()
        try:
            # Count by status
            status_counts = {}
            for row in conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM findings 
                WHERE case_id = ?
                GROUP BY status
            """, (case_id,)):
                status_counts[row["status"]] = row["count"]
            
            # Total
            total = sum(status_counts.values())
            
            # Verified rate
            verified = status_counts.get("verified", 0)
            verified_rate = (verified / total * 100) if total > 0 else 0
            
            return {
                "total": total,
                "by_status": status_counts,
                "verified_rate": round(verified_rate, 1),
            }
            
        finally:
            conn.close()
    
    # =========================================================================
    # TIMELINE HELPERS
    # =========================================================================
    
    def _log_timeline_event(
        self,
        conn: sqlite3.Connection,
        case_id: str,
        event_type: str,
        event_data: Dict,
    ) -> None:
        """Log an event to case timeline."""
        conn.execute("""
            INSERT INTO case_timeline (id, case_id, event_type, event_data_json, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(uuid4()),
            case_id,
            event_type,
            json.dumps(event_data),
            self._now(),
        ))


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "Finding",
    "FindingsStore",
]

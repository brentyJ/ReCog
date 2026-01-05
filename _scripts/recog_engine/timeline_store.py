"""
ReCog Engine - Timeline Store v0.1

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Database persistence layer for Case Timeline.
Auto-generated chronicle of case evolution with human annotation support.
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
class TimelineEvent:
    """An event in the case timeline."""
    id: str
    case_id: str
    event_type: str
    event_data: Dict = field(default_factory=dict)
    human_annotation: str = ""
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "case_id": self.case_id,
            "event_type": self.event_type,
            "event_data": self.event_data,
            "human_annotation": self.human_annotation,
            "timestamp": self.timestamp,
            # Include human-readable description
            "description": self._get_description(),
        }
    
    def _get_description(self) -> str:
        """Generate human-readable description of event."""
        descriptions = {
            "case_created": lambda d: f"Case created: {d.get('title', 'Untitled')}",
            "doc_added": lambda d: f"Document added{': ' + d.get('impact_notes') if d.get('impact_notes') else ''}",
            "doc_removed": lambda d: "Document removed",
            "finding_added": lambda d: f"Finding added (ID: {d.get('finding_id', 'unknown')[:8]}...)",
            "finding_verified": lambda d: f"Finding verified",
            "finding_rejected": lambda d: f"Finding rejected",
            "pattern_found": lambda d: f"Pattern detected: {d.get('pattern_name', 'Unknown')}",
            "note_added": lambda d: f"Note: {d.get('note', '')[:50]}...",
            "context_updated": lambda d: "Case context updated",
            "status_changed": lambda d: f"Status changed to: {d.get('status', 'unknown')}",
            "insights_extracted": lambda d: f"Extracted {d.get('count', 0)} insights from {d.get('source_type', 'document')}",
        }
        
        formatter = descriptions.get(self.event_type, lambda d: self.event_type)
        return formatter(self.event_data)
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TimelineEvent":
        """Create from database row."""
        return cls(
            id=row["id"],
            case_id=row["case_id"],
            event_type=row["event_type"],
            event_data=json.loads(row["event_data_json"] or "{}"),
            human_annotation=row["human_annotation"] or "",
            timestamp=row["timestamp"],
        )


# =============================================================================
# VALID EVENT TYPES
# =============================================================================

VALID_EVENT_TYPES = [
    "case_created",
    "doc_added",
    "doc_removed",
    "finding_added",
    "finding_verified",
    "finding_rejected",
    "pattern_found",
    "note_added",
    "context_updated",
    "status_changed",
    "insights_extracted",
]


# =============================================================================
# TIMELINE STORE
# =============================================================================

class TimelineStore:
    """
    Database persistence for Case Timeline.
    
    Handles:
    - Timeline event logging (auto-generated)
    - Human annotations on events
    - Timeline queries and filtering
    """
    
    def __init__(self, db_path: Path):
        """Initialize timeline store."""
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
    # EVENT LOGGING
    # =========================================================================
    
    def log_event(
        self,
        case_id: str,
        event_type: str,
        event_data: Optional[Dict] = None,
        human_annotation: str = "",
    ) -> TimelineEvent:
        """
        Log an event to the timeline.
        
        Args:
            case_id: UUID of the case
            event_type: Type of event (must be in VALID_EVENT_TYPES)
            event_data: Flexible payload for event details
            human_annotation: Optional human note
            
        Returns:
            Created TimelineEvent object
        """
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event type: {event_type}. Must be one of {VALID_EVENT_TYPES}")
        
        conn = self._connect()
        try:
            event_id = str(uuid4())
            now = self._now()
            data = event_data or {}
            
            conn.execute("""
                INSERT INTO case_timeline (
                    id, case_id, event_type, event_data_json, human_annotation, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (event_id, case_id, event_type, json.dumps(data), human_annotation, now))
            
            conn.commit()
            
            logger.debug(f"Logged timeline event: {event_type} for case {case_id}")
            
            return TimelineEvent(
                id=event_id,
                case_id=case_id,
                event_type=event_type,
                event_data=data,
                human_annotation=human_annotation,
                timestamp=now,
            )
            
        finally:
            conn.close()
    
    def add_annotation(self, event_id: str, annotation: str) -> bool:
        """
        Add or update human annotation on a timeline event.
        
        Args:
            event_id: UUID of the event
            annotation: Annotation text
            
        Returns:
            True if updated, False if not found
        """
        conn = self._connect()
        try:
            cursor = conn.execute(
                "UPDATE case_timeline SET human_annotation = ? WHERE id = ?",
                (annotation, event_id)
            )
            
            if cursor.rowcount > 0:
                conn.commit()
                return True
            
            return False
            
        finally:
            conn.close()
    
    # =========================================================================
    # QUERIES
    # =========================================================================
    
    def get_timeline(
        self,
        case_id: str,
        event_types: Optional[List[str]] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "DESC",
    ) -> Dict[str, Any]:
        """
        Get timeline events for a case.
        
        Args:
            case_id: UUID of the case
            event_types: Filter to specific event types
            since: Filter events after this timestamp
            until: Filter events before this timestamp
            limit: Max results
            offset: Pagination offset
            order: ASC (oldest first) or DESC (newest first)
            
        Returns:
            Dict with 'events' list and 'total' count
        """
        conn = self._connect()
        try:
            conditions = ["case_id = ?"]
            params = [case_id]
            
            if event_types:
                placeholders = ",".join(["?" for _ in event_types])
                conditions.append(f"event_type IN ({placeholders})")
                params.extend(event_types)
            
            if since:
                conditions.append("timestamp >= ?")
                params.append(since)
            
            if until:
                conditions.append("timestamp <= ?")
                params.append(until)
            
            where_clause = " AND ".join(conditions)
            order = "DESC" if order.upper() == "DESC" else "ASC"
            
            # Get total
            total = conn.execute(
                f"SELECT COUNT(*) FROM case_timeline WHERE {where_clause}",
                params
            ).fetchone()[0]
            
            # Get events
            query = f"""
                SELECT * FROM case_timeline
                WHERE {where_clause}
                ORDER BY timestamp {order}
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            rows = conn.execute(query, params).fetchall()
            
            return {
                "events": [TimelineEvent.from_row(row).to_dict() for row in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
            
        finally:
            conn.close()
    
    def get_event(self, event_id: str) -> Optional[TimelineEvent]:
        """
        Get a single timeline event.
        
        Args:
            event_id: UUID of the event
            
        Returns:
            TimelineEvent or None
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM case_timeline WHERE id = ?",
                (event_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return TimelineEvent.from_row(row)
            
        finally:
            conn.close()
    
    def get_recent_activity(
        self,
        case_id: str,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Get most recent activity for a case.
        
        Args:
            case_id: UUID of the case
            limit: Number of events to return
            
        Returns:
            List of event dicts (newest first)
        """
        result = self.get_timeline(case_id, limit=limit, order="DESC")
        return result["events"]
    
    # =========================================================================
    # SUMMARIES
    # =========================================================================
    
    def get_summary(self, case_id: str) -> Dict[str, Any]:
        """
        Get timeline summary statistics.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            Summary dict with counts by type, date range, etc.
        """
        conn = self._connect()
        try:
            # Count by event type
            type_counts = {}
            for row in conn.execute("""
                SELECT event_type, COUNT(*) as count
                FROM case_timeline
                WHERE case_id = ?
                GROUP BY event_type
            """, (case_id,)):
                type_counts[row["event_type"]] = row["count"]
            
            # Date range
            date_range = conn.execute("""
                SELECT MIN(timestamp) as earliest, MAX(timestamp) as latest
                FROM case_timeline
                WHERE case_id = ?
            """, (case_id,)).fetchone()
            
            # Total events
            total = sum(type_counts.values())
            
            # Annotations count
            annotations = conn.execute("""
                SELECT COUNT(*) FROM case_timeline
                WHERE case_id = ? AND human_annotation IS NOT NULL AND human_annotation != ''
            """, (case_id,)).fetchone()[0]
            
            return {
                "total_events": total,
                "by_type": type_counts,
                "earliest_event": date_range["earliest"],
                "latest_event": date_range["latest"],
                "annotated_events": annotations,
            }
            
        finally:
            conn.close()
    
    def get_daily_summary(self, case_id: str, days: int = 7) -> List[Dict]:
        """
        Get daily event counts.
        
        Args:
            case_id: UUID of the case
            days: Number of days to summarize
            
        Returns:
            List of dicts with date and event counts
        """
        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as event_count,
                    GROUP_CONCAT(DISTINCT event_type) as event_types
                FROM case_timeline
                WHERE case_id = ? 
                    AND timestamp >= DATE('now', ?)
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """, (case_id, f"-{days} days")).fetchall()
            
            return [
                {
                    "date": row["date"],
                    "event_count": row["event_count"],
                    "event_types": row["event_types"].split(",") if row["event_types"] else [],
                }
                for row in rows
            ]
            
        finally:
            conn.close()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_case_created_event(
    timeline_store: TimelineStore,
    case_id: str,
    title: str,
    focus_areas: List[str],
) -> TimelineEvent:
    """Log a case creation event."""
    return timeline_store.log_event(
        case_id,
        "case_created",
        {"title": title, "focus_areas": focus_areas},
    )


def create_doc_added_event(
    timeline_store: TimelineStore,
    case_id: str,
    document_id: str,
    findings_count: int = 0,
) -> TimelineEvent:
    """Log a document added event."""
    return timeline_store.log_event(
        case_id,
        "doc_added",
        {"document_id": document_id, "findings_count": findings_count},
    )


def create_finding_verified_event(
    timeline_store: TimelineStore,
    case_id: str,
    finding_id: str,
) -> TimelineEvent:
    """Log a finding verification event."""
    return timeline_store.log_event(
        case_id,
        "finding_verified",
        {"finding_id": finding_id},
    )


def create_pattern_found_event(
    timeline_store: TimelineStore,
    case_id: str,
    pattern_id: str,
    pattern_name: str,
) -> TimelineEvent:
    """Log a pattern detection event."""
    return timeline_store.log_event(
        case_id,
        "pattern_found",
        {"pattern_id": pattern_id, "pattern_name": pattern_name},
    )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "TimelineEvent",
    "TimelineStore",
    "VALID_EVENT_TYPES",
    "create_case_created_event",
    "create_doc_added_event",
    "create_finding_verified_event",
    "create_pattern_found_event",
]

"""
ReCog Engine - Case Store v0.1

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Database persistence layer for Cases.
Handles case CRUD, document linking, and context management.
"""

import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Case:
    """Represents a case container for document intelligence."""
    id: str
    title: str
    context: str = ""
    focus_areas: List[str] = field(default_factory=list)
    status: str = "active"  # active, archived
    document_count: int = 0
    findings_count: int = 0
    patterns_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "context": self.context,
            "focus_areas": self.focus_areas,
            "status": self.status,
            "document_count": self.document_count,
            "findings_count": self.findings_count,
            "patterns_count": self.patterns_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Case":
        """Create from database row."""
        return cls(
            id=row["id"],
            title=row["title"],
            context=row["context"] or "",
            focus_areas=json.loads(row["focus_areas_json"] or "[]"),
            status=row["status"],
            document_count=row["document_count"],
            findings_count=row["findings_count"],
            patterns_count=row["patterns_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class CaseDocument:
    """Link between a case and a document."""
    id: str
    case_id: str
    document_id: str
    added_at: str
    impact_notes: str = ""
    findings_count: int = 0
    entities_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CaseDocument":
        return cls(
            id=row["id"],
            case_id=row["case_id"],
            document_id=row["document_id"],
            added_at=row["added_at"],
            impact_notes=row["impact_notes"] or "",
            findings_count=row["findings_count"],
            entities_count=row["entities_count"],
        )


@dataclass
class CaseContext:
    """Context object for injection into extraction prompts."""
    title: str
    context: str
    focus_areas: List[str]
    
    def to_prompt_string(self) -> str:
        """Format for injection into LLM prompts."""
        focus = ", ".join(self.focus_areas) if self.focus_areas else "general analysis"
        return f"""CASE CONTEXT:
Title: {self.title}
Context: {self.context}
Focus Areas: {focus}

Extract insights that are:
1. Directly supported by text (cite excerpts)
2. Relevant to the case context above
3. Factual observations, not speculation

Do NOT infer causation without explicit evidence."""


# =============================================================================
# CASE STORE
# =============================================================================

class CaseStore:
    """
    Database persistence for Cases.
    
    Handles:
    - Case CRUD operations
    - Document linking
    - Statistics updates
    - Context injection helpers
    """
    
    def __init__(self, db_path: Path):
        """Initialize case store."""
        self.db_path = Path(db_path)
        
    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _now(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat() + "Z"
    
    # =========================================================================
    # CASE CRUD
    # =========================================================================
    
    def create_case(
        self,
        title: str,
        context: str = "",
        focus_areas: Optional[List[str]] = None,
    ) -> Case:
        """
        Create a new case.
        
        Args:
            title: Case title
            context: Initial question/assignment context
            focus_areas: List of focus area keywords
            
        Returns:
            Created Case object
        """
        conn = self._connect()
        try:
            case_id = str(uuid4())
            now = self._now()
            focus = focus_areas or []
            
            conn.execute("""
                INSERT INTO cases (
                    id, title, context, focus_areas_json, status,
                    document_count, findings_count, patterns_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'active', 0, 0, 0, ?, ?)
            """, (
                case_id, title, context, json.dumps(focus), now, now
            ))
            
            conn.commit()
            
            # Log timeline event
            self._log_timeline_event(
                conn, case_id, "case_created",
                {"title": title, "focus_areas": focus}
            )
            conn.commit()
            
            logger.info(f"Created case {case_id}: {title}")
            
            return Case(
                id=case_id,
                title=title,
                context=context,
                focus_areas=focus,
                status="active",
                document_count=0,
                findings_count=0,
                patterns_count=0,
                created_at=now,
                updated_at=now,
            )
            
        finally:
            conn.close()
    
    def get_case(self, case_id: str) -> Optional[Case]:
        """
        Get a case by ID.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            Case object or None
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM cases WHERE id = ?",
                (case_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return Case.from_row(row)
        finally:
            conn.close()
    
    def list_cases(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "updated_at",
        order_dir: str = "DESC",
    ) -> Dict[str, Any]:
        """
        List cases with filters.
        
        Args:
            status: Filter by status (active, archived)
            limit: Max results
            offset: Pagination offset
            order_by: Sort column
            order_dir: ASC or DESC
            
        Returns:
            Dict with 'cases' list and 'total' count
        """
        conn = self._connect()
        try:
            conditions = []
            params = []
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # Validate order_by
            valid_columns = ["created_at", "updated_at", "title", "document_count", "findings_count"]
            if order_by not in valid_columns:
                order_by = "updated_at"
            order_dir = "DESC" if order_dir.upper() == "DESC" else "ASC"
            
            # Get total
            total = conn.execute(
                f"SELECT COUNT(*) FROM cases WHERE {where_clause}",
                params
            ).fetchone()[0]
            
            # Get results with insight counts
            query = f"""
                SELECT c.*,
                       COALESCE(ic.insight_count, 0) as insight_count
                FROM cases c
                LEFT JOIN (
                    SELECT case_id, COUNT(*) as insight_count
                    FROM insights
                    GROUP BY case_id
                ) ic ON c.id = ic.case_id
                WHERE {where_clause}
                ORDER BY {order_by} {order_dir}
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()

            # Build case dicts with insight_count
            cases = []
            for row in rows:
                case_dict = Case.from_row(row).to_dict()
                # Get insight_count from the last column
                case_dict["insight_count"] = row["insight_count"] if "insight_count" in row.keys() else 0
                cases.append(case_dict)

            return {
                "cases": cases,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
            
        finally:
            conn.close()
    
    def update_case(
        self,
        case_id: str,
        title: Optional[str] = None,
        context: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> bool:
        """
        Update case fields.
        
        Args:
            case_id: UUID of the case
            title: New title
            context: New context
            focus_areas: New focus areas
            status: New status
            
        Returns:
            True if updated, False if not found
        """
        conn = self._connect()
        try:
            updates = []
            params = []
            changes = {}
            
            if title is not None:
                updates.append("title = ?")
                params.append(title)
                changes["title"] = title
            
            if context is not None:
                updates.append("context = ?")
                params.append(context)
                changes["context"] = context
            
            if focus_areas is not None:
                updates.append("focus_areas_json = ?")
                params.append(json.dumps(focus_areas))
                changes["focus_areas"] = focus_areas
            
            if status is not None:
                if status not in ("active", "archived"):
                    raise ValueError(f"Invalid status: {status}")
                updates.append("status = ?")
                params.append(status)
                changes["status"] = status
            
            if not updates:
                return False
            
            updates.append("updated_at = ?")
            now = self._now()
            params.append(now)
            params.append(case_id)
            
            cursor = conn.execute(
                f"UPDATE cases SET {', '.join(updates)} WHERE id = ?",
                params
            )
            
            if cursor.rowcount > 0:
                # Log timeline event
                event_type = "status_changed" if "status" in changes else "context_updated"
                self._log_timeline_event(conn, case_id, event_type, changes)
                conn.commit()
                logger.info(f"Updated case {case_id}")
                return True
            
            return False
            
        finally:
            conn.close()
    
    def delete_case(self, case_id: str) -> bool:
        """
        Delete a case and all related data (cascade).
        
        Args:
            case_id: UUID of the case
            
        Returns:
            True if deleted, False if not found
        """
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM cases WHERE id = ?",
                (case_id,)
            )
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"Deleted case {case_id}")
                return True
            
            return False
            
        finally:
            conn.close()
    
    # =========================================================================
    # DOCUMENT LINKING
    # =========================================================================
    
    def add_document(
        self,
        case_id: str,
        document_id: str,
        impact_notes: str = "",
    ) -> Optional[CaseDocument]:
        """
        Link a document to a case.
        
        Args:
            case_id: UUID of the case
            document_id: ID of the document (preflight item, ingested doc, etc.)
            impact_notes: Optional notes about this document's relevance
            
        Returns:
            CaseDocument object or None if case not found
        """
        conn = self._connect()
        try:
            # Verify case exists
            case = conn.execute(
                "SELECT id FROM cases WHERE id = ?",
                (case_id,)
            ).fetchone()
            
            if not case:
                return None
            
            doc_id = str(uuid4())
            now = self._now()
            
            try:
                conn.execute("""
                    INSERT INTO case_documents (
                        id, case_id, document_id, added_at, impact_notes,
                        findings_count, entities_count
                    ) VALUES (?, ?, ?, ?, ?, 0, 0)
                """, (doc_id, case_id, document_id, now, impact_notes))
            except sqlite3.IntegrityError:
                # Document already linked to this case
                logger.warning(f"Document {document_id} already linked to case {case_id}")
                return None
            
            # Update case document count
            conn.execute(
                "UPDATE cases SET document_count = document_count + 1, updated_at = ? WHERE id = ?",
                (now, case_id)
            )
            
            # Log timeline event
            self._log_timeline_event(conn, case_id, "doc_added", {
                "document_id": document_id,
                "impact_notes": impact_notes,
            })
            
            conn.commit()
            
            logger.info(f"Added document {document_id} to case {case_id}")
            
            return CaseDocument(
                id=doc_id,
                case_id=case_id,
                document_id=document_id,
                added_at=now,
                impact_notes=impact_notes,
                findings_count=0,
                entities_count=0,
            )
            
        finally:
            conn.close()
    
    def remove_document(self, case_id: str, document_id: str) -> bool:
        """
        Remove a document from a case.
        
        Args:
            case_id: UUID of the case
            document_id: ID of the document
            
        Returns:
            True if removed, False if not found
        """
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM case_documents WHERE case_id = ? AND document_id = ?",
                (case_id, document_id)
            )
            
            if cursor.rowcount > 0:
                now = self._now()
                conn.execute(
                    "UPDATE cases SET document_count = document_count - 1, updated_at = ? WHERE id = ?",
                    (now, case_id)
                )
                self._log_timeline_event(conn, case_id, "doc_removed", {
                    "document_id": document_id,
                })
                conn.commit()
                return True
            
            return False
            
        finally:
            conn.close()
    
    def list_documents(self, case_id: str) -> List[Dict]:
        """
        List all documents in a case.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            List of CaseDocument dicts
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM case_documents WHERE case_id = ? ORDER BY added_at",
                (case_id,)
            ).fetchall()
            
            return [CaseDocument.from_row(row).to_dict() for row in rows]
            
        finally:
            conn.close()
    
    # =========================================================================
    # CONTEXT INJECTION
    # =========================================================================
    
    def get_context(self, case_id: str) -> Optional[CaseContext]:
        """
        Get case context for prompt injection.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            CaseContext object or None
        """
        case = self.get_case(case_id)
        if not case:
            return None
        
        return CaseContext(
            title=case.title,
            context=case.context,
            focus_areas=case.focus_areas,
        )
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed statistics for a case.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            Statistics dict or None if case not found
        """
        conn = self._connect()
        try:
            case = conn.execute(
                "SELECT * FROM cases WHERE id = ?",
                (case_id,)
            ).fetchone()
            
            if not case:
                return None
            
            # Get findings breakdown
            findings_by_status = {}
            for row in conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM findings 
                WHERE case_id = ? 
                GROUP BY status
            """, (case_id,)):
                findings_by_status[row["status"]] = row["count"]
            
            # Get timeline event count
            timeline_count = conn.execute(
                "SELECT COUNT(*) FROM case_timeline WHERE case_id = ?",
                (case_id,)
            ).fetchone()[0]
            
            return {
                "case_id": case_id,
                "document_count": case["document_count"],
                "findings_count": case["findings_count"],
                "patterns_count": case["patterns_count"],
                "findings_by_status": findings_by_status,
                "timeline_event_count": timeline_count,
            }
            
        finally:
            conn.close()
    
    def update_counts(self, case_id: str) -> None:
        """
        Recalculate and update denormalized counts.
        
        Args:
            case_id: UUID of the case
        """
        conn = self._connect()
        try:
            # Count documents
            doc_count = conn.execute(
                "SELECT COUNT(*) FROM case_documents WHERE case_id = ?",
                (case_id,)
            ).fetchone()[0]
            
            # Count findings
            findings_count = conn.execute(
                "SELECT COUNT(*) FROM findings WHERE case_id = ?",
                (case_id,)
            ).fetchone()[0]
            
            # Count patterns
            patterns_count = conn.execute(
                "SELECT COUNT(*) FROM patterns WHERE case_id = ?",
                (case_id,)
            ).fetchone()[0]
            
            conn.execute("""
                UPDATE cases SET 
                    document_count = ?,
                    findings_count = ?,
                    patterns_count = ?,
                    updated_at = ?
                WHERE id = ?
            """, (doc_count, findings_count, patterns_count, self._now(), case_id))
            
            conn.commit()
            
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
        """Log an event to case timeline (internal)."""
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
    "Case",
    "CaseDocument", 
    "CaseContext",
    "CaseStore",
]

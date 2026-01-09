"""
ReCog Engine - Case State Machine v0.8

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Manages case state transitions and auto-progression through the processing pipeline.

States:
    UPLOADING  - Files being added to case
    SCANNING   - Running Tier 0 (free signal extraction)
    CLARIFYING - Need user input for entity identification
    PROCESSING - Running extraction + synthesis (LLM)
    COMPLETE   - Analysis finished
    WATCHING   - Background directory monitor active
"""

import logging
import sqlite3
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# =============================================================================
# STATE DEFINITIONS
# =============================================================================

class CaseState(Enum):
    """Valid states for a case in the processing pipeline."""
    UPLOADING = "uploading"
    SCANNING = "scanning"
    CLARIFYING = "clarifying"
    PROCESSING = "processing"
    COMPLETE = "complete"
    WATCHING = "watching"


class StateTransition:
    """Defines valid state transitions and their conditions."""

    # Map of current state -> list of valid next states
    TRANSITIONS = {
        "uploading": ["scanning"],
        "scanning": ["clarifying", "processing"],  # Skip clarifying if no unknowns
        "clarifying": ["processing"],
        "processing": ["complete"],
        "complete": ["watching", "processing"],  # Can reprocess or watch
        "watching": ["complete"],
    }

    @staticmethod
    def can_transition(from_state: str, to_state: str) -> bool:
        """Check if transition is valid."""
        return to_state in StateTransition.TRANSITIONS.get(from_state, [])

    @staticmethod
    def next_state(current_state: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Determine next state based on context.

        Args:
            current_state: Current state string
            context: Dict with keys:
                - files_uploaded: bool - Files have been added
                - tier0_complete: bool - Tier 0 scan is done
                - unknown_entities: bool - There are unconfirmed entities
                - entities_clarified: bool - All entities are confirmed
                - processing_started: bool - Extraction has begun
                - synthesis_complete: bool - Synthesis is done

        Returns:
            Next state string or None if no transition available
        """
        if current_state == "uploading":
            if context.get("files_uploaded"):
                return "scanning"

        elif current_state == "scanning":
            if context.get("tier0_complete"):
                if context.get("unknown_entities"):
                    return "clarifying"
                else:
                    return "processing"

        elif current_state == "clarifying":
            if context.get("entities_clarified"):
                return "processing"

        elif current_state == "processing":
            if context.get("synthesis_complete"):
                return "complete"

        return None


# =============================================================================
# CASE STATE MACHINE
# =============================================================================

class CaseStateMachine:
    """
    Manages case state transitions and auto-progression.

    Handles:
    - State transition validation
    - Timeline event logging
    - Triggering next-stage actions (queue jobs)
    - Progress tracking
    """

    def __init__(self, db_path: Path):
        """
        Initialize state machine.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _now(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # =========================================================================
    # STATE QUERIES
    # =========================================================================

    def get_case_state(self, case_id: str) -> Optional[str]:
        """Get current state of a case."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT state FROM cases WHERE id = ?",
                (case_id,)
            ).fetchone()
            return row["state"] if row else None
        finally:
            conn.close()

    def get_case_progress(self, case_id: str) -> Dict[str, Any]:
        """
        Get detailed progress for a case.

        Returns dict with:
            - stage: Current processing stage
            - status: Stage status (pending/running/complete/failed)
            - progress: 0.0-1.0 completion
            - current_item: What's being processed
            - total_items: Total items to process
            - completed_items: Items done
            - recent_insight: Latest discovery
        """
        conn = self._connect()
        try:
            row = conn.execute("""
                SELECT * FROM case_progress
                WHERE case_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
            """, (case_id,)).fetchone()

            if row:
                return {
                    "id": row["id"],
                    "stage": row["stage"],
                    "status": row["status"],
                    "progress": row["progress"] or 0.0,
                    "current_item": row["current_item"],
                    "total_items": row["total_items"] or 0,
                    "completed_items": row["completed_items"] or 0,
                    "recent_insight": row["recent_insight"],
                    "error_message": row["error_message"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }

            return {
                "stage": "idle",
                "status": "pending",
                "progress": 0.0,
                "current_item": None,
                "total_items": 0,
                "completed_items": 0,
                "recent_insight": None,
            }
        finally:
            conn.close()

    # =========================================================================
    # STATE TRANSITIONS
    # =========================================================================

    def advance_case(self, case_id: str, context: Dict[str, Any] = None) -> bool:
        """
        Try to advance case to next state based on context.

        Args:
            case_id: Case UUID
            context: Dict with condition flags

        Returns:
            True if state was advanced, False otherwise
        """
        context = context or {}
        current_state = self.get_case_state(case_id)

        if not current_state:
            logger.warning(f"Case not found: {case_id}")
            return False

        next_state = StateTransition.next_state(current_state, context)

        if next_state and StateTransition.can_transition(current_state, next_state):
            self.transition_to(case_id, next_state)
            logger.info(f"Case {case_id}: {current_state} -> {next_state}")
            return True

        return False

    def transition_to(self, case_id: str, new_state: str) -> bool:
        """
        Execute state transition.

        Args:
            case_id: Case UUID
            new_state: Target state

        Returns:
            True if successful
        """
        conn = self._connect()
        try:
            now = self._now()
            old_state = self.get_case_state(case_id)

            # Update case state
            cursor = conn.execute("""
                UPDATE cases
                SET state = ?, last_activity = ?, updated_at = ?
                WHERE id = ?
            """, (new_state, now, now, case_id))

            if cursor.rowcount == 0:
                logger.warning(f"Case not found for transition: {case_id}")
                return False

            # Update processing timestamps
            if new_state == "processing":
                conn.execute("""
                    UPDATE cases SET processing_started_at = ? WHERE id = ?
                """, (now, case_id))
            elif new_state == "complete":
                conn.execute("""
                    UPDATE cases SET processing_completed_at = ? WHERE id = ?
                """, (now, case_id))

            # Log timeline event
            conn.execute("""
                INSERT INTO case_timeline (id, case_id, event_type, event_data_json, timestamp)
                VALUES (?, ?, 'status_changed', ?, ?)
            """, (
                str(uuid4()),
                case_id,
                f'{{"old_state": "{old_state}", "new_state": "{new_state}"}}',
                now
            ))

            conn.commit()
            logger.info(f"Transitioned case {case_id}: {old_state} -> {new_state}")

            # Trigger next action (outside transaction)
            self._trigger_action(case_id, new_state)

            return True

        except Exception as e:
            logger.error(f"Transition error for case {case_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def _trigger_action(self, case_id: str, state: str):
        """
        Trigger appropriate action for new state.

        This queues background jobs for processing states.
        """
        if state == "scanning":
            # Tier 0 is already run during upload via scan_session()
            # No additional action needed - scan happens synchronously
            logger.debug(f"Case {case_id} entered scanning (Tier 0 runs during upload)")

        elif state == "processing":
            # Queue extraction jobs for all preflight items
            self._queue_extraction_jobs(case_id)

        elif state == "watching":
            # Future: Start background directory monitor
            logger.info(f"Case {case_id} entered watching mode (not yet implemented)")

    def _queue_extraction_jobs(self, case_id: str):
        """Queue extraction jobs for case preflight items."""
        conn = self._connect()
        try:
            now = self._now()

            # Get preflight session for this case
            session = conn.execute("""
                SELECT id FROM preflight_sessions
                WHERE case_id = ? AND status IN ('scanned', 'confirmed', 'reviewing')
                ORDER BY created_at DESC LIMIT 1
            """, (case_id,)).fetchone()

            if not session:
                logger.warning(f"No preflight session found for case {case_id}")
                return

            session_id = session["id"]

            # Get items not yet queued
            items = conn.execute("""
                SELECT pi.id, pi.word_count, pi.pre_annotation_json
                FROM preflight_items pi
                WHERE pi.preflight_session_id = ?
                  AND pi.included = 1
                  AND pi.processed = 0
                  AND NOT EXISTS (
                      SELECT 1 FROM processing_queue pq
                      WHERE pq.source_type = 'preflight_item'
                        AND pq.source_id = pi.id
                  )
            """, (session_id,)).fetchall()

            if not items:
                logger.info(f"No items to queue for case {case_id}")
                return

            # Create progress tracker
            progress_id = str(uuid4())
            conn.execute("""
                INSERT INTO case_progress
                (id, case_id, stage, status, total_items, completed_items, progress, created_at, updated_at)
                VALUES (?, ?, 'extraction', 'pending', ?, 0, 0.0, ?, ?)
            """, (progress_id, case_id, len(items), now, now))

            # Queue extraction jobs
            queued = 0
            for item in items:
                try:
                    conn.execute("""
                        INSERT INTO processing_queue
                        (operation_type, source_type, source_id, status, priority,
                         word_count, pre_annotation_json, case_id, queued_at)
                        VALUES ('extract', 'preflight_item', ?, 'pending', 0, ?, ?, ?, ?)
                    """, (
                        str(item["id"]),
                        item["word_count"],
                        item["pre_annotation_json"],
                        case_id,
                        now
                    ))
                    queued += 1
                except sqlite3.IntegrityError:
                    # Already queued
                    pass

            conn.commit()
            logger.info(f"Queued {queued} extraction jobs for case {case_id}")

        except Exception as e:
            logger.error(f"Error queuing extraction jobs: {e}")
            conn.rollback()
        finally:
            conn.close()

    # =========================================================================
    # PROGRESS TRACKING
    # =========================================================================

    def create_progress(
        self,
        case_id: str,
        stage: str,
        total_items: int = 0
    ) -> str:
        """
        Create a progress tracker for a processing stage.

        Returns progress ID.
        """
        conn = self._connect()
        try:
            now = self._now()
            progress_id = str(uuid4())

            conn.execute("""
                INSERT INTO case_progress
                (id, case_id, stage, status, total_items, completed_items, progress, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, 0, 0.0, ?, ?)
            """, (progress_id, case_id, stage, total_items, now, now))

            conn.commit()
            return progress_id
        finally:
            conn.close()

    def update_progress(
        self,
        progress_id: str,
        status: str = None,
        completed_items: int = None,
        current_item: str = None,
        recent_insight: str = None,
        error_message: str = None,
    ):
        """Update progress tracker."""
        conn = self._connect()
        try:
            now = self._now()
            updates = ["updated_at = ?"]
            values = [now]

            if status:
                updates.append("status = ?")
                values.append(status)

            if completed_items is not None:
                updates.append("completed_items = ?")
                values.append(completed_items)

                # Calculate progress percentage
                total = conn.execute(
                    "SELECT total_items FROM case_progress WHERE id = ?",
                    (progress_id,)
                ).fetchone()
                if total and total["total_items"] > 0:
                    progress = completed_items / total["total_items"]
                    updates.append("progress = ?")
                    values.append(progress)

            if current_item is not None:
                updates.append("current_item = ?")
                values.append(current_item)

            if recent_insight is not None:
                updates.append("recent_insight = ?")
                values.append(recent_insight[:200] if recent_insight else None)

            if error_message is not None:
                updates.append("error_message = ?")
                values.append(error_message)

            values.append(progress_id)

            conn.execute(
                f"UPDATE case_progress SET {', '.join(updates)} WHERE id = ?",
                values
            )
            conn.commit()
        finally:
            conn.close()

    def complete_progress(self, progress_id: str, success: bool = True):
        """Mark progress as complete or failed."""
        status = "complete" if success else "failed"
        conn = self._connect()
        try:
            now = self._now()
            conn.execute("""
                UPDATE case_progress
                SET status = ?, progress = ?, updated_at = ?
                WHERE id = ?
            """, (status, 1.0 if success else None, now, progress_id))
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # HELPER QUERIES
    # =========================================================================

    def has_unconfirmed_entities(self, case_id: str) -> bool:
        """
        Check if case has unconfirmed entities that need clarification.

        Checks entities found in the case's preflight items.
        """
        conn = self._connect()
        try:
            # Get entity count from preflight items for this case
            row = conn.execute("""
                SELECT COUNT(DISTINCT e.id) as count
                FROM entity_registry e
                JOIN preflight_items pi ON pi.entities_found_json LIKE '%' || e.raw_value || '%'
                JOIN preflight_sessions ps ON pi.preflight_session_id = ps.id
                WHERE ps.case_id = ? AND e.confirmed = 0
            """, (case_id,)).fetchone()

            # Fallback: check unknown_entities_count in preflight session
            if row["count"] == 0:
                row = conn.execute("""
                    SELECT unknown_entities_count
                    FROM preflight_sessions
                    WHERE case_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (case_id,)).fetchone()
                return (row["unknown_entities_count"] or 0) > 0

            return row["count"] > 0
        finally:
            conn.close()

    def is_extraction_complete(self, case_id: str) -> bool:
        """Check if all extraction jobs for case are complete."""
        conn = self._connect()
        try:
            row = conn.execute("""
                SELECT COUNT(*) as pending
                FROM processing_queue
                WHERE case_id = ?
                  AND operation_type = 'extract'
                  AND status IN ('pending', 'processing')
            """, (case_id,)).fetchone()
            return row["pending"] == 0
        finally:
            conn.close()


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "CaseState",
    "StateTransition",
    "CaseStateMachine",
]

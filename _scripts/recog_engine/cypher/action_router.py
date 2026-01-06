"""
Cypher Action Router
Routes classified intents to backend operations
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class CypherActionRouter:
    """Routes classified intents to backend operations"""

    def __init__(
        self,
        db_path: str,
        entity_registry=None,
        insight_store=None,
        case_store=None
    ):
        self.db_path = db_path
        self.entity_registry = entity_registry
        self.insight_store = insight_store
        self.case_store = case_store

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, intent: str, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Main routing function - dispatches to appropriate handler"""
        handlers = {
            "entity_correction": self.handle_entity_correction,
            "filter_request": self.handle_filter,
            "navigation": self.handle_navigation,
            "analysis_query": self.handle_query,
            "file_upload": self.handle_file_upload,
            "processing_control": self.handle_processing_control,
            "pattern_feedback": self.handle_pattern_feedback,
            "clarification": self.handle_clarification,
        }

        handler = handlers.get(intent)
        if not handler:
            return self.handle_unknown(intent, entities, context)

        try:
            return handler(entities, context)
        except Exception as e:
            logger.error(f"Action execution failed: {e}", exc_info=True)
            return {
                "reply": "Operation failed. System error logged.",
                "actions": [],
                "ui_updates": {},
                "suggestions": []
            }

    # =========================================================================
    # ENTITY CORRECTION
    # =========================================================================

    def handle_entity_correction(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle entity corrections like "Webb isn't a person"
        """
        entity_name = entities.get("name")
        correction_type = entities.get("correction_type", "not_a_person")

        if not entity_name:
            return {
                "reply": "Entity name not detected. Rephrase?",
                "actions": [],
                "ui_updates": {},
                "suggestions": [
                    {"text": "View all entities", "action": "navigate_entities", "icon": "Users"}
                ]
            }

        # Find entity in registry by name (case-insensitive search)
        entity = self._find_entity_by_name(entity_name)

        if not entity:
            return {
                "reply": f"Entity '{entity_name}' not in registry. Already removed?",
                "actions": [],
                "ui_updates": {},
                "suggestions": [
                    {"text": "View all entities", "action": "navigate_entities", "icon": "Users"}
                ]
            }

        # Remove from registry and add to blocklist
        try:
            self._remove_entity(entity["id"])
            self._add_to_blocklist(
                normalised_value=entity.get("normalised_value") or entity.get("raw_value"),
                entity_type=entity.get("entity_type", "person"),
                reason=f"User correction: {correction_type}"
            )

            # Log correction for learning
            self._log_user_correction(entity_name, correction_type)

            return {
                "reply": f"Acknowledged. {entity_name} removed from registry. Blocklisted.",
                "actions": [
                    {"type": "entity_remove", "entity_id": entity["id"], "entity_name": entity_name},
                    {"type": "blocklist_add", "term": entity_name}
                ],
                "ui_updates": {
                    "refresh": ["entities_page", "entity_stats"],
                    "navigate": None
                },
                "suggestions": [
                    {"text": "Review other entities", "action": "navigate_entities", "icon": "Users"},
                    {"text": "Continue to insights", "action": "navigate_insights", "icon": "Lightbulb"}
                ]
            }
        except Exception as e:
            logger.error(f"Entity correction failed: {e}")
            return {
                "reply": f"Failed to remove '{entity_name}'. Error logged.",
                "actions": [],
                "ui_updates": {},
                "suggestions": []
            }

    def _find_entity_by_name(self, name: str) -> Optional[Dict]:
        """Find entity by name (case-insensitive)"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, entity_type, raw_value, normalised_value, display_name
                FROM entity_registry
                WHERE merged_into_id IS NULL
                  AND (
                    LOWER(raw_value) = LOWER(?)
                    OR LOWER(normalised_value) = LOWER(?)
                    OR LOWER(display_name) = LOWER(?)
                  )
                LIMIT 1
            """, (name, name, name))

            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "entity_type": row["entity_type"],
                    "raw_value": row["raw_value"],
                    "normalised_value": row["normalised_value"],
                    "display_name": row["display_name"],
                }
            return None
        finally:
            conn.close()

    def _remove_entity(self, entity_id: int) -> None:
        """Delete entity from registry"""
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM entity_registry WHERE id = ?", (entity_id,))
            conn.commit()
            logger.info(f"Removed entity {entity_id}")
        finally:
            conn.close()

    def _add_to_blocklist(self, normalised_value: str, entity_type: str, reason: str) -> None:
        """Add to entity blacklist in database and runtime"""
        conn = self.get_connection()
        try:
            now = datetime.utcnow().isoformat()

            # Try to insert, or update if already exists
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO entity_blacklist (normalised_value, entity_type, rejection_reason, created_at, rejection_count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(normalised_value) DO UPDATE SET
                    rejection_count = rejection_count + 1,
                    rejection_reason = excluded.rejection_reason
            """, (normalised_value.lower(), entity_type, reason, now))
            conn.commit()

            # Update runtime blacklist
            try:
                from recog_engine.tier0 import add_to_blacklist
                add_to_blacklist(normalised_value)
            except ImportError:
                logger.warning("Could not import tier0 blacklist functions")

        finally:
            conn.close()

    def _log_user_correction(self, entity_name: str, correction_type: str) -> None:
        """Log user correction for future learning"""
        # For now just log it - could store in database for ML training later
        logger.info(f"User correction: {entity_name} -> {correction_type}")

    # =========================================================================
    # FILTER REQUEST
    # =========================================================================

    def handle_filter(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle filter requests like "Focus on Seattle documents" """
        focus_term = entities.get("focus", "")

        if not focus_term:
            return {
                "reply": "Filter term not detected. Specify what to filter by.",
                "actions": [],
                "ui_updates": {},
                "suggestions": []
            }

        # Get count of matching insights (basic search)
        count = self._count_insights_matching(focus_term, context.get("case_id"))

        return {
            "reply": f"Filtered to {count} results. Term: '{focus_term}'.",
            "actions": [
                {"type": "apply_filter", "filters": {"query": focus_term}}
            ],
            "ui_updates": {
                "navigate": "insights",
                "highlight": focus_term
            },
            "suggestions": [
                {"text": "Clear filter", "action": "clear_filter", "icon": "X"},
                {"text": "View entities", "action": "navigate_entities", "icon": "Users"}
            ]
        }

    def _count_insights_matching(self, term: str, case_id: str = None) -> int:
        """Count insights matching a search term"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            query = """
                SELECT COUNT(*) FROM insights
                WHERE deleted_at IS NULL
                AND (
                    LOWER(summary) LIKE LOWER(?)
                    OR LOWER(themes) LIKE LOWER(?)
                )
            """
            params = [f"%{term}%", f"%{term}%"]

            if case_id:
                query += " AND case_id = ?"
                params.append(case_id)

            cursor.execute(query, params)
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Insight count failed: {e}")
            return 0
        finally:
            conn.close()

    # =========================================================================
    # NAVIGATION
    # =========================================================================

    def handle_navigation(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle navigation requests like "Show me the timeline" """
        target = entities.get("target", "").lower()

        # Map common terms to actual views
        nav_map = {
            "entities": "entities",
            "entity": "entities",
            "insights": "insights",
            "insight": "insights",
            "findings": "findings",
            "finding": "findings",
            "timeline": "timeline",
            "dashboard": "dashboard",
            "cases": "cases",
            "case": "cases",
            "patterns": "patterns",
            "pattern": "patterns",
            "upload": "upload",
            "preflight": "preflight",
        }

        view = nav_map.get(target)

        if not view:
            return {
                "reply": f"Navigation target '{target}' not recognized. Try: entities, insights, timeline, findings.",
                "actions": [],
                "ui_updates": {},
                "suggestions": [
                    {"text": "Dashboard", "action": "navigate_dashboard", "icon": "LayoutDashboard"},
                    {"text": "Entities", "action": "navigate_entities", "icon": "Users"},
                    {"text": "Insights", "action": "navigate_insights", "icon": "Lightbulb"}
                ]
            }

        return {
            "reply": f"Displaying {view} view.",
            "actions": [],
            "ui_updates": {
                "navigate": view
            },
            "suggestions": []
        }

    # =========================================================================
    # ANALYSIS QUERY
    # =========================================================================

    def handle_query(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analysis queries like "Are there any gaps in April?" """
        query_type = entities.get("query_type", "general")
        case_id = context.get("case_id")

        if query_type == "timeline_gap":
            return self._handle_timeline_gap_query(entities, case_id)
        elif query_type == "pattern_search":
            return self._handle_pattern_query(entities, case_id)
        else:
            return self._handle_general_query(entities, context)

    def _handle_timeline_gap_query(self, entities: Dict[str, Any], case_id: str) -> Dict[str, Any]:
        """Analyze timeline for gaps"""
        month = entities.get("month")

        # This would need more sophisticated implementation
        # For now, return a placeholder response
        return {
            "reply": f"Timeline gap analysis for {month if month else 'all periods'}: Feature in development.",
            "actions": [],
            "ui_updates": {
                "navigate": "timeline"
            },
            "suggestions": [
                {"text": "View timeline", "action": "navigate_timeline", "icon": "Calendar"}
            ]
        }

    def _handle_pattern_query(self, entities: Dict[str, Any], case_id: str) -> Dict[str, Any]:
        """Search for patterns"""
        return {
            "reply": "Pattern search: Feature in development.",
            "actions": [],
            "ui_updates": {
                "navigate": "patterns"
            },
            "suggestions": [
                {"text": "View patterns", "action": "navigate_patterns", "icon": "GitBranch"}
            ]
        }

    def _handle_general_query(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general queries - may need LLM for complex questions"""
        return {
            "reply": "Query processing: Specify entities, timeline, or patterns for targeted analysis.",
            "actions": [],
            "ui_updates": {},
            "suggestions": [
                {"text": "View entities", "action": "navigate_entities", "icon": "Users"},
                {"text": "View timeline", "action": "navigate_timeline", "icon": "Calendar"},
                {"text": "View patterns", "action": "navigate_patterns", "icon": "GitBranch"}
            ]
        }

    # =========================================================================
    # FILE UPLOAD / PROCESSING CONTROL
    # =========================================================================

    def handle_file_upload(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file upload requests"""
        files = entities.get("files", [])
        file_count = entities.get("file_count", len(files))

        if file_count == 0:
            return {
                "reply": "No files detected. Drag files into chat or use upload button.",
                "actions": [],
                "ui_updates": {
                    "navigate": "upload"
                },
                "suggestions": [
                    {"text": "Go to upload", "action": "navigate_upload", "icon": "Upload"}
                ]
            }

        return {
            "reply": f"{file_count} documents queued. Navigate to upload page to proceed.",
            "actions": [],
            "ui_updates": {
                "navigate": "upload"
            },
            "suggestions": [
                {"text": "Start processing", "action": "confirm_preflight", "icon": "Play"},
                {"text": "Review files", "action": "navigate_preflight", "icon": "FileSearch"}
            ]
        }

    def handle_processing_control(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle processing control commands"""
        return {
            "reply": "Processing control: Use upload page for document processing.",
            "actions": [],
            "ui_updates": {
                "navigate": "upload"
            },
            "suggestions": [
                {"text": "Go to upload", "action": "navigate_upload", "icon": "Upload"}
            ]
        }

    # =========================================================================
    # PATTERN FEEDBACK
    # =========================================================================

    def handle_pattern_feedback(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pattern confirmation/rejection"""
        return {
            "reply": "Pattern feedback: Feature in development.",
            "actions": [],
            "ui_updates": {},
            "suggestions": []
        }

    # =========================================================================
    # FALLBACKS
    # =========================================================================

    def handle_clarification(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests that need clarification"""
        return {
            "reply": "Clarify your request. Examples: 'Webb isn't a person', 'Show me entities', 'Focus on Seattle'.",
            "actions": [],
            "ui_updates": {},
            "suggestions": [
                {"text": "View entities", "action": "navigate_entities", "icon": "Users"},
                {"text": "View insights", "action": "navigate_insights", "icon": "Lightbulb"},
                {"text": "View timeline", "action": "navigate_timeline", "icon": "Calendar"}
            ]
        }

    def handle_unknown(self, intent: str, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback for unknown intents"""
        logger.warning(f"Unknown intent: {intent}")
        return {
            "reply": "Intent unclear. Rephrase?",
            "actions": [],
            "ui_updates": {},
            "suggestions": [
                {"text": "View entities", "action": "navigate_entities", "icon": "Users"},
                {"text": "View insights", "action": "navigate_insights", "icon": "Lightbulb"}
            ]
        }

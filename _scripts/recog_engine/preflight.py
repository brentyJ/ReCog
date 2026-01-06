"""
ReCog Engine - Preflight Session Manager v0.1

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Orchestrates the preflight context system for large imports:
- Creates preflight sessions for batch processing
- Runs Tier 0 scans on content
- Collects entity questions
- Estimates processing costs
- Manages the review workflow
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .tier0 import preprocess_text, summarise_for_prompt
from .entity_registry import EntityRegistry


# Cost estimation (approximate cents per 1K tokens)
COST_PER_1K_INPUT = 0.015   # gpt-4o-mini input
COST_PER_1K_OUTPUT = 0.060  # gpt-4o-mini output
OVERHEAD_MULTIPLIER = 1.5   # Account for prompts, retries


# =============================================================================
# PREFLIGHT SESSION MANAGER
# =============================================================================

class PreflightManager:
    """
    Manages preflight sessions for batch content processing.
    
    A preflight session allows users to:
    1. Preview what will be processed
    2. See estimated costs before committing
    3. Filter out unwanted content
    4. Identify unknown entities
    5. Confirm before expensive LLM processing
    """
    
    def __init__(self, db_path: Path, entity_registry: EntityRegistry = None):
        """
        Initialize preflight manager.
        
        Args:
            db_path: Path to SQLite database
            entity_registry: Optional EntityRegistry instance (creates one if not provided)
        """
        self.db_path = Path(db_path)
        self.entity_registry = entity_registry or EntityRegistry(db_path)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    def create_session(
        self,
        session_type: str,
        source_files: List[str] = None,
        case_id: str = None,
    ) -> int:
        """
        Create a new preflight session.
        
        Args:
            session_type: 'single_file', 'batch', 'chatgpt_import', etc.
            source_files: List of file paths being processed
            case_id: Optional case UUID to link documents for context injection
            
        Returns:
            session_id
        """
        now = datetime.utcnow().isoformat() + "Z"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO preflight_sessions (
                    session_type, status, source_files_json, source_count,
                    case_id, created_at, updated_at
                ) VALUES (?, 'pending', ?, ?, ?, ?, ?)
            """, (
                session_type,
                json.dumps(source_files or []),
                len(source_files or []),
                case_id,
                now, now
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def get_session(self, session_id: int) -> Optional[Dict]:
        """Get a preflight session by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, session_type, status, source_files_json, source_count,
                       total_word_count, total_entities_found, unknown_entities_count,
                       estimated_tokens, estimated_cost_cents, filters_json,
                       items_after_filter, entity_questions_json, entity_answers_json,
                       case_id, started_at, completed_at, operations_created,
                       created_at, updated_at
                FROM preflight_sessions
                WHERE id = ?
            """, (session_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'session_type': row['session_type'],
                    'status': row['status'],
                    'source_files': json.loads(row['source_files_json']) if row['source_files_json'] else [],
                    'source_count': row['source_count'],
                    'total_word_count': row['total_word_count'],
                    'total_entities_found': row['total_entities_found'],
                    'unknown_entities_count': row['unknown_entities_count'],
                    'estimated_tokens': row['estimated_tokens'],
                    'estimated_cost_cents': row['estimated_cost_cents'],
                    'filters': json.loads(row['filters_json']) if row['filters_json'] else {},
                    'items_after_filter': row['items_after_filter'],
                    'entity_questions': json.loads(row['entity_questions_json']) if row['entity_questions_json'] else [],
                    'entity_answers': json.loads(row['entity_answers_json']) if row['entity_answers_json'] else {},
                    'case_id': row['case_id'],
                    'started_at': row['started_at'],
                    'completed_at': row['completed_at'],
                    'operations_created': row['operations_created'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                }
            return None
        finally:
            conn.close()
    
    def update_session(self, session_id: int, **kwargs) -> bool:
        """Update preflight session fields."""
        now = datetime.utcnow().isoformat() + "Z"
        
        # Map complex types to JSON
        json_fields = ['filters', 'entity_questions', 'entity_answers', 'source_files']
        
        updates = []
        values = []
        
        for key, value in kwargs.items():
            db_key = key
            if key in json_fields:
                db_key = f"{key}_json" if not key.endswith('_json') else key
                value = json.dumps(value)
            updates.append(f"{db_key} = ?")
            values.append(value)
        
        updates.append("updated_at = ?")
        values.append(now)
        values.append(session_id)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"""
                UPDATE preflight_sessions
                SET {', '.join(updates)}
                WHERE id = ?
            """, values)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    # =========================================================================
    # ITEM MANAGEMENT
    # =========================================================================
    
    def add_item(
        self,
        session_id: int,
        source_type: str,
        content: str,
        source_id: str = None,
        title: str = None,
    ) -> int:
        """
        Add an item to a preflight session and run Tier 0 scan.
        
        Args:
            session_id: Preflight session ID
            source_type: Type of content
            content: Raw text content
            source_id: Optional unique ID
            title: Optional display title
            
        Returns:
            item_id
        """
        now = datetime.utcnow().isoformat() + "Z"
        
        # Run Tier 0 scan
        pre_annotation = {}
        entities_found = {}
        word_count = 0
        
        if content:
            pre_annotation = preprocess_text(content)
            word_count = pre_annotation.get('word_count', 0)
            entities_found = pre_annotation.get('entities', {})
            
            # Register entities
            self.entity_registry.register_from_tier0(
                entities_found,
                source_type=source_type,
                source_id=source_id,
            )
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO preflight_items (
                    preflight_session_id, source_type, source_id, title,
                    word_count, pre_annotation_json, entities_found_json,
                    content, included, processed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
            """, (
                session_id, source_type, source_id, title,
                word_count, json.dumps(pre_annotation), json.dumps(entities_found),
                content, now
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def get_items(
        self,
        session_id: int,
        included_only: bool = False,
    ) -> List[Dict]:
        """Get all items in a preflight session."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            conditions = ["preflight_session_id = ?"]
            values = [session_id]
            
            if included_only:
                conditions.append("included = 1")
            
            cursor.execute(f"""
                SELECT id, source_type, source_id, title, word_count, message_count,
                       date_range_start, date_range_end, pre_annotation_json,
                       entities_found_json, included, exclusion_reason, processed
                FROM preflight_items
                WHERE {' AND '.join(conditions)}
                ORDER BY id
            """, values)
            
            return [{
                'id': row['id'],
                'source_type': row['source_type'],
                'source_id': row['source_id'],
                'title': row['title'],
                'word_count': row['word_count'],
                'message_count': row['message_count'],
                'date_range_start': row['date_range_start'],
                'date_range_end': row['date_range_end'],
                'pre_annotation': json.loads(row['pre_annotation_json']) if row['pre_annotation_json'] else {},
                'entities_found': json.loads(row['entities_found_json']) if row['entities_found_json'] else {},
                'included': bool(row['included']),
                'exclusion_reason': row['exclusion_reason'],
                'processed': bool(row['processed']),
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def exclude_item(self, item_id: int, reason: str = 'manual') -> bool:
        """Exclude an item from processing."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE preflight_items
                SET included = 0, exclusion_reason = ?
                WHERE id = ?
            """, (reason, item_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def include_item(self, item_id: int) -> bool:
        """Re-include an excluded item."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE preflight_items
                SET included = 1, exclusion_reason = NULL
                WHERE id = ?
            """, (item_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    # =========================================================================
    # SCANNING & ANALYSIS
    # =========================================================================
    
    def scan_session(self, session_id: int) -> Dict:
        """
        Analyse a preflight session after all items are added.
        
        Returns summary with:
        - Total word count
        - Entity counts
        - Unknown entities needing review
        - Cost estimate
        - Questions for user
        """
        items = self.get_items(session_id, included_only=True)
        
        total_words = sum(item.get('word_count', 0) for item in items)
        
        # Aggregate entities
        all_phones = []
        all_emails = []
        all_people = []
        
        for item in items:
            entities = item.get('entities_found', {})
            all_phones.extend(entities.get('phone_numbers', []))
            all_emails.extend(entities.get('email_addresses', []))
            all_people.extend(entities.get('people', []))
        
        # Dedupe
        unique_phones = list({p.get('normalised', p.get('raw', '')): p for p in all_phones}.values())
        unique_emails = list({e.get('normalised', e.get('raw', '')): e for e in all_emails}.values())
        unique_people = list(set(all_people))
        
        total_entities = len(unique_phones) + len(unique_emails) + len(unique_people)
        
        # Get unknown entities from registry
        unknown = self.entity_registry.get_unknown_entities(limit=100)
        unknown_count = len(unknown)
        
        # Estimate tokens and cost
        # Rough: 1 word ≈ 1.3 tokens, plus prompt overhead
        estimated_tokens = int(total_words * 1.3 * OVERHEAD_MULTIPLIER)
        estimated_cost_cents = int(
            (estimated_tokens / 1000) * (COST_PER_1K_INPUT + COST_PER_1K_OUTPUT)
        )
        
        # Build questions for unknown entities
        questions = []
        for entity in unknown[:20]:  # Cap at 20 questions
            if entity.get('entity_type') == 'phone':
                questions.append({
                    'entity_id': entity['id'],
                    'type': 'phone',
                    'value': entity['raw_value'],
                    'question': f"Who is {entity['raw_value']}?",
                    'options': ['Skip', 'Enter name...'],
                })
            elif entity.get('entity_type') == 'email':
                questions.append({
                    'entity_id': entity['id'],
                    'type': 'email',
                    'value': entity['raw_value'],
                    'question': f"Who is {entity['raw_value']}?",
                    'options': ['Skip', 'Enter name...'],
                })
        
        # Update session
        self.update_session(
            session_id,
            status='scanned',
            total_word_count=total_words,
            total_entities_found=total_entities,
            unknown_entities_count=unknown_count,
            estimated_tokens=estimated_tokens,
            estimated_cost_cents=estimated_cost_cents,
            items_after_filter=len(items),
            entity_questions=questions,
        )
        
        return {
            'session_id': session_id,
            'status': 'scanned',
            'item_count': len(items),
            'total_words': total_words,
            'total_entities': total_entities,
            'unknown_entities': unknown_count,
            'estimated_tokens': estimated_tokens,
            'estimated_cost_cents': estimated_cost_cents,
            'estimated_cost_dollars': estimated_cost_cents / 100,
            'questions': questions,
            'entities': {
                'phones': len(unique_phones),
                'emails': len(unique_emails),
                'people': len(unique_people),
            },
        }
    
    def get_summary(self, session_id: int) -> Dict:
        """Get a summary of a preflight session for display."""
        session = self.get_session(session_id)
        if not session:
            return {'error': 'Session not found'}
        
        items = self.get_items(session_id)
        included = [i for i in items if i['included']]
        
        return {
            'session_id': session_id,
            'session_type': session['session_type'],
            'status': session['status'],
            'source_count': session['source_count'],
            'case_id': session.get('case_id'),
            'items': {
                'total': len(items),
                'included': len(included),
                'excluded': len(items) - len(included),
            },
            'total_words': session['total_word_count'],
            'total_entities': session['total_entities_found'],
            'unknown_entities': session['unknown_entities_count'],
            'estimated_tokens': session['estimated_tokens'],
            'estimated_cost_cents': session['estimated_cost_cents'],
            'estimated_cost_dollars': (session['estimated_cost_cents'] or 0) / 100,
            'questions_pending': len(session.get('entity_questions', [])),
            'created_at': session['created_at'],
        }
    
    # =========================================================================
    # FILTERING
    # =========================================================================
    
    def apply_filters(
        self,
        session_id: int,
        min_words: int = None,
        min_messages: int = None,
        date_after: str = None,
        date_before: str = None,
        keywords: List[str] = None,
    ) -> Dict:
        """
        Apply filters to preflight items.
        Items not matching filters are excluded.
        
        Returns:
            Summary of filtering results
        """
        items = self.get_items(session_id)
        
        excluded_count = 0
        filters_applied = {}
        
        for item in items:
            exclude = False
            reason = None
            
            # Word count filter
            if min_words and item.get('word_count', 0) < min_words:
                exclude = True
                reason = f'words < {min_words}'
                filters_applied['min_words'] = min_words
            
            # Message count filter
            if min_messages and item.get('message_count', 0) < min_messages:
                exclude = True
                reason = f'messages < {min_messages}'
                filters_applied['min_messages'] = min_messages
            
            # Date filters
            if date_after and item.get('date_range_end'):
                if item['date_range_end'] < date_after:
                    exclude = True
                    reason = f'before {date_after}'
                    filters_applied['date_after'] = date_after
            
            if date_before and item.get('date_range_start'):
                if item['date_range_start'] > date_before:
                    exclude = True
                    reason = f'after {date_before}'
                    filters_applied['date_before'] = date_before
            
            # Keyword filter (include only if ANY keyword matches)
            if keywords:
                pre_annotation = item.get('pre_annotation', {})
                title = (item.get('title') or '').lower()
                # Check if any keyword appears in title or emotion keywords
                emotion_kws = pre_annotation.get('emotion_signals', {}).get('keywords_found', [])
                all_text = title + ' ' + ' '.join(emotion_kws)
                
                if not any(kw.lower() in all_text for kw in keywords):
                    exclude = True
                    reason = 'no keyword match'
                    filters_applied['keywords'] = keywords
            
            if exclude and item['included']:
                self.exclude_item(item['id'], reason)
                excluded_count += 1
        
        # Update session with filters
        self.update_session(session_id, filters=filters_applied)
        
        # Rescan to update counts
        return self.scan_session(session_id)
    
    # =========================================================================
    # CONFIRMATION
    # =========================================================================
    
    def confirm_session(self, session_id: int) -> Dict:
        """
        Confirm a preflight session and prepare for processing.
        
        This marks the session as ready for LLM processing.
        The actual processing is handled by the extraction system.
        
        Returns:
            dict with confirmation status and item count
        """
        session = self.get_session(session_id)
        
        if not session:
            return {'success': False, 'error': 'Session not found'}
        
        if session['status'] not in ('scanned', 'reviewing'):
            return {'success': False, 'error': f'Session not ready: {session["status"]}'}
        
        items = self.get_items(session_id, included_only=True)
        
        if not items:
            return {'success': False, 'error': 'No items to process'}
        
        now = datetime.utcnow().isoformat() + 'Z'
        
        # Update session status
        self.update_session(
            session_id,
            status='confirmed',
            started_at=now,
        )
        
        return {
            'success': True,
            'session_id': session_id,
            'items_to_process': len(items),
            'estimated_tokens': session['estimated_tokens'],
            'estimated_cost_cents': session['estimated_cost_cents'],
            'status': 'confirmed',
        }
    
    def complete_session(self, session_id: int, operations_created: int = 0) -> bool:
        """Mark a session as complete after processing."""
        now = datetime.utcnow().isoformat() + 'Z'
        return self.update_session(
            session_id,
            status='complete',
            completed_at=now,
            operations_created=operations_created,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_default_manager: Optional[PreflightManager] = None


def init_preflight(db_path: Path, entity_registry: EntityRegistry = None) -> PreflightManager:
    """Initialize the default preflight manager."""
    global _default_manager
    _default_manager = PreflightManager(db_path, entity_registry)
    return _default_manager


def get_preflight() -> PreflightManager:
    """Get the default preflight manager."""
    if _default_manager is None:
        raise RuntimeError("Preflight manager not initialized. Call init_preflight() first.")
    return _default_manager


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Class
    'PreflightManager',
    # Cost constants
    'COST_PER_1K_INPUT',
    'COST_PER_1K_OUTPUT',
    'OVERHEAD_MULTIPLIER',
    # Module-level access
    'init_preflight',
    'get_preflight',
]

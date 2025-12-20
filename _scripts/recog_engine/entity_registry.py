"""
ReCog Engine - Entity Registry v0.1

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Manages known entities (people, phones, emails) with user-provided context.
Supports anonymisation for privacy-sensitive LLM processing.
"""

import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


# =============================================================================
# NORMALISATION UTILITIES
# =============================================================================

def normalise_phone(raw: str) -> str:
    """
    Normalise phone number for matching.
    Strips formatting, keeps leading + for international.
    """
    # Remove all non-digit chars except leading +
    normalised = re.sub(r'[^\d+]', '', raw)
    # Ensure + is only at start
    if '+' in normalised[1:]:
        normalised = normalised[0] + normalised[1:].replace('+', '')
    return normalised


def normalise_email(raw: str) -> str:
    """Normalise email for matching (lowercase, trimmed)."""
    return raw.lower().strip()


def normalise_name(raw: str) -> str:
    """Normalise person name for matching."""
    return raw.strip().title()


# =============================================================================
# ENTITY REGISTRY CLASS
# =============================================================================

class EntityRegistry:
    """
    Manages entity storage and retrieval.
    
    Entities are people, phone numbers, emails, or organisations
    that appear in processed content. Users can provide context
    (display names, relationships) and control anonymisation.
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize registry with database path.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================
    
    def get_entity(self, entity_type: str, normalised_value: str) -> Optional[Dict]:
        """Get an entity by type and normalised value."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, entity_type, raw_value, normalised_value, display_name,
                       relationship, notes, anonymise_in_prompts, placeholder_name,
                       first_seen_at, last_seen_at, occurrence_count, source_types,
                       confirmed, merged_into_id, created_at, updated_at
                FROM entity_registry
                WHERE entity_type = ? AND normalised_value = ? AND merged_into_id IS NULL
            """, (entity_type, normalised_value))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
        finally:
            conn.close()
    
    def get_entity_by_id(self, entity_id: int) -> Optional[Dict]:
        """Get an entity by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, entity_type, raw_value, normalised_value, display_name,
                       relationship, notes, anonymise_in_prompts, placeholder_name,
                       first_seen_at, last_seen_at, occurrence_count, source_types,
                       confirmed, merged_into_id, created_at, updated_at
                FROM entity_registry
                WHERE id = ?
            """, (entity_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
        finally:
            conn.close()
    
    def _row_to_dict(self, row) -> Dict:
        """Convert database row to dictionary."""
        return {
            'id': row['id'],
            'entity_type': row['entity_type'],
            'raw_value': row['raw_value'],
            'normalised_value': row['normalised_value'],
            'display_name': row['display_name'],
            'relationship': row['relationship'],
            'notes': row['notes'],
            'anonymise_in_prompts': bool(row['anonymise_in_prompts']),
            'placeholder_name': row['placeholder_name'],
            'first_seen_at': row['first_seen_at'],
            'last_seen_at': row['last_seen_at'],
            'occurrence_count': row['occurrence_count'],
            'source_types': json.loads(row['source_types']) if row['source_types'] else [],
            'confirmed': bool(row['confirmed']),
            'merged_into_id': row['merged_into_id'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        }
    
    def register_entity(
        self,
        entity_type: str,
        raw_value: str,
        normalised_value: str = None,
        display_name: str = None,
        relationship: str = None,
        source_type: str = None,
    ) -> Tuple[int, bool]:
        """
        Register an entity. Creates new or updates existing.
        
        Args:
            entity_type: 'phone', 'email', 'person', 'organisation'
            raw_value: Original extracted value
            normalised_value: Normalised form (auto-generated if None)
            display_name: Human-friendly name
            relationship: Relationship to user
            source_type: Type of source where found
            
        Returns:
            Tuple of (entity_id, is_new)
        """
        now = datetime.utcnow().isoformat() + "Z"
        
        # Normalise if not provided
        if normalised_value is None:
            if entity_type == 'phone':
                normalised_value = normalise_phone(raw_value)
            elif entity_type == 'email':
                normalised_value = normalise_email(raw_value)
            else:
                normalised_value = raw_value.strip()
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Check if exists
            cursor.execute("""
                SELECT id, occurrence_count, source_types 
                FROM entity_registry 
                WHERE entity_type = ? AND normalised_value = ? AND merged_into_id IS NULL
            """, (entity_type, normalised_value))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                entity_id = existing['id']
                occurrence_count = existing['occurrence_count'] + 1
                source_types = json.loads(existing['source_types']) if existing['source_types'] else []
                
                if source_type and source_type not in source_types:
                    source_types.append(source_type)
                
                cursor.execute("""
                    UPDATE entity_registry
                    SET last_seen_at = ?, occurrence_count = ?, source_types = ?, updated_at = ?
                    WHERE id = ?
                """, (now, occurrence_count, json.dumps(source_types), now, entity_id))
                
                conn.commit()
                return (entity_id, False)
            else:
                # Create new
                source_types = [source_type] if source_type else []
                
                cursor.execute("""
                    INSERT INTO entity_registry (
                        entity_type, raw_value, normalised_value, display_name, relationship,
                        first_seen_at, last_seen_at, occurrence_count, source_types,
                        confirmed, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 0, ?, ?)
                """, (
                    entity_type, raw_value, normalised_value, display_name, relationship,
                    now, now, json.dumps(source_types), now, now
                ))
                
                conn.commit()
                return (cursor.lastrowid, True)
        finally:
            conn.close()
    
    def update_entity(
        self,
        entity_id: int,
        display_name: str = None,
        relationship: str = None,
        notes: str = None,
        anonymise_in_prompts: bool = None,
        placeholder_name: str = None,
        confirmed: bool = None,
    ) -> bool:
        """
        Update entity with user-provided context.
        
        Returns:
            True if entity was updated
        """
        now = datetime.utcnow().isoformat() + "Z"
        
        updates = []
        values = []
        
        if display_name is not None:
            updates.append("display_name = ?")
            values.append(display_name)
        if relationship is not None:
            updates.append("relationship = ?")
            values.append(relationship)
        if notes is not None:
            updates.append("notes = ?")
            values.append(notes)
        if anonymise_in_prompts is not None:
            updates.append("anonymise_in_prompts = ?")
            values.append(1 if anonymise_in_prompts else 0)
        if placeholder_name is not None:
            updates.append("placeholder_name = ?")
            values.append(placeholder_name)
        if confirmed is not None:
            updates.append("confirmed = ?")
            values.append(1 if confirmed else 0)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        values.append(now)
        values.append(entity_id)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"""
                UPDATE entity_registry
                SET {', '.join(updates)}
                WHERE id = ?
            """, values)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def list_entities(
        self,
        entity_type: str = None,
        confirmed_only: bool = False,
        unconfirmed_only: bool = False,
        limit: int = 100,
    ) -> List[Dict]:
        """List entities with optional filtering."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            conditions = ["merged_into_id IS NULL"]
            values = []
            
            if entity_type:
                conditions.append("entity_type = ?")
                values.append(entity_type)
            if confirmed_only:
                conditions.append("confirmed = 1")
            if unconfirmed_only:
                conditions.append("confirmed = 0")
            
            values.append(limit)
            
            cursor.execute(f"""
                SELECT id, entity_type, raw_value, normalised_value, display_name,
                       relationship, occurrence_count, confirmed
                FROM entity_registry
                WHERE {' AND '.join(conditions)}
                ORDER BY occurrence_count DESC, last_seen_at DESC
                LIMIT ?
            """, values)
            
            return [{
                'id': row['id'],
                'entity_type': row['entity_type'],
                'raw_value': row['raw_value'],
                'normalised_value': row['normalised_value'],
                'display_name': row['display_name'],
                'relationship': row['relationship'],
                'occurrence_count': row['occurrence_count'],
                'confirmed': bool(row['confirmed']),
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_unknown_entities(self, limit: int = 50) -> List[Dict]:
        """Get entities that need user identification."""
        return self.list_entities(unconfirmed_only=True, limit=limit)
    
    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================
    
    def register_from_tier0(
        self,
        tier0_entities: Dict,
        source_type: str,
        source_id: str = None,
    ) -> Dict[str, List[Tuple[int, bool]]]:
        """
        Register all entities from Tier 0 extraction.
        
        Args:
            tier0_entities: The 'entities' dict from preprocess_text()
            source_type: Type of source (e.g., 'document', 'chat')
            source_id: Optional ID of source
            
        Returns:
            Dict mapping entity_type to list of (entity_id, is_new) tuples
        """
        results = {
            'phone': [],
            'email': [],
            'person': [],
        }
        
        # Phone numbers
        for phone in tier0_entities.get('phone_numbers', []):
            entity_id, is_new = self.register_entity(
                entity_type='phone',
                raw_value=phone.get('raw', ''),
                normalised_value=phone.get('normalised'),
                source_type=source_type,
            )
            results['phone'].append((entity_id, is_new))
        
        # Email addresses
        for email in tier0_entities.get('email_addresses', []):
            entity_id, is_new = self.register_entity(
                entity_type='email',
                raw_value=email.get('raw', ''),
                normalised_value=email.get('normalised'),
                source_type=source_type,
            )
            results['email'].append((entity_id, is_new))
        
        # People (from name detection)
        for person in tier0_entities.get('people', []):
            entity_id, is_new = self.register_entity(
                entity_type='person',
                raw_value=person,
                source_type=source_type,
            )
            results['person'].append((entity_id, is_new))
        
        return results
    
    # =========================================================================
    # PROMPT RESOLUTION
    # =========================================================================
    
    def resolve_for_prompt(self, tier0_entities: Dict) -> Dict:
        """
        Resolve entities against registry for LLM prompt enrichment.
        
        For known entities:
        - If anonymise_in_prompts=True: use placeholder_name
        - Else: use display_name or raw_value
        
        For unknown entities:
        - Flag for user review
        - Use raw value with [UNKNOWN] marker
        
        Returns:
            dict with: resolved, unknown, prompt_context
        """
        resolved = []
        unknown = []
        context_parts = []
        
        # Process phone numbers
        for phone in tier0_entities.get('phone_numbers', []):
            normalised = phone.get('normalised', normalise_phone(phone.get('raw', '')))
            entity = self.get_entity('phone', normalised)
            
            if entity and entity.get('confirmed'):
                display = entity.get('placeholder_name') if entity.get('anonymise_in_prompts') else entity.get('display_name', normalised)
                resolved.append({
                    'type': 'phone',
                    'raw': phone.get('raw'),
                    'display': display,
                    'relationship': entity.get('relationship'),
                    'entity_id': entity.get('id'),
                })
                if display and entity.get('relationship'):
                    context_parts.append(f"{display} ({entity.get('relationship')})")
            else:
                unknown.append({
                    'type': 'phone',
                    'raw': phone.get('raw'),
                    'normalised': normalised,
                    'context': phone.get('context', ''),
                    'entity_id': entity.get('id') if entity else None,
                })
        
        # Process email addresses
        for email in tier0_entities.get('email_addresses', []):
            normalised = email.get('normalised', normalise_email(email.get('raw', '')))
            entity = self.get_entity('email', normalised)
            
            if entity and entity.get('confirmed'):
                display = entity.get('placeholder_name') if entity.get('anonymise_in_prompts') else entity.get('display_name', normalised)
                resolved.append({
                    'type': 'email',
                    'raw': email.get('raw'),
                    'display': display,
                    'relationship': entity.get('relationship'),
                    'entity_id': entity.get('id'),
                })
                if display and entity.get('relationship'):
                    context_parts.append(f"{display} ({entity.get('relationship')})")
            else:
                unknown.append({
                    'type': 'email',
                    'raw': email.get('raw'),
                    'normalised': normalised,
                    'context': email.get('context', ''),
                    'entity_id': entity.get('id') if entity else None,
                })
        
        # Build prompt context
        prompt_context = ""
        if context_parts:
            prompt_context = "Known entities in this content:\n" + "\n".join(f"- {p}" for p in context_parts)
        if unknown:
            prompt_context += f"\n\nNote: {len(unknown)} unidentified contact(s) present."
        
        return {
            'resolved': resolved,
            'unknown': unknown,
            'prompt_context': prompt_context.strip(),
        }
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> Dict:
        """Get statistics about the entity registry."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            stats = {}
            
            # Total counts by type
            cursor.execute("""
                SELECT entity_type, COUNT(*), SUM(CASE WHEN confirmed = 1 THEN 1 ELSE 0 END)
                FROM entity_registry
                WHERE merged_into_id IS NULL
                GROUP BY entity_type
            """)
            for row in cursor.fetchall():
                stats[row[0]] = {
                    'total': row[1],
                    'confirmed': row[2],
                    'unconfirmed': row[1] - row[2],
                }
            
            # Overall
            cursor.execute("""
                SELECT COUNT(*), SUM(CASE WHEN confirmed = 1 THEN 1 ELSE 0 END)
                FROM entity_registry
                WHERE merged_into_id IS NULL
            """)
            row = cursor.fetchone()
            stats['total'] = {
                'total': row[0] or 0,
                'confirmed': row[1] or 0,
                'unconfirmed': (row[0] or 0) - (row[1] or 0),
            }
            
            return stats
        finally:
            conn.close()


# =============================================================================
# CONVENIENCE FUNCTIONS (for module-level access)
# =============================================================================

_default_registry: Optional[EntityRegistry] = None


def init_registry(db_path: Path) -> EntityRegistry:
    """Initialize the default registry."""
    global _default_registry
    _default_registry = EntityRegistry(db_path)
    return _default_registry


def get_registry() -> EntityRegistry:
    """Get the default registry (must call init_registry first)."""
    if _default_registry is None:
        raise RuntimeError("Entity registry not initialized. Call init_registry() first.")
    return _default_registry


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Class
    'EntityRegistry',
    # Utilities
    'normalise_phone',
    'normalise_email',
    'normalise_name',
    # Module-level access
    'init_registry',
    'get_registry',
]

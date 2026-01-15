"""
ReCog Engine - Entity Registry v0.2

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Manages known entities (people, phones, emails) with user-provided context.
Supports anonymisation for privacy-sensitive LLM processing.

v0.2 Changes:
- Added LLM-based entity validation to filter false positives
"""

import sqlite3
import json
import re
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Enable/disable LLM validation of entities (costs money per call)
VALIDATE_ENTITIES_WITH_LLM = os.environ.get("RECOG_VALIDATE_ENTITIES_LLM", "false").lower() in ("true", "1", "yes")


# =============================================================================
# LLM ENTITY VALIDATION
# =============================================================================

ENTITY_VALIDATION_PROMPT = """You are validating named entity extraction results.

Given these extracted "person" names, identify which are ACTUALLY person names vs false positives (generic words, organization names, project names, technical terms, etc).

Extracted names: {entity_list}

{context_section}

Return ONLY the valid person names as a JSON array. Be strict - if unsure, exclude it.

Examples of FALSE POSITIVES to filter out:
- "Foundation" (organization type, not a name)
- "Research" (generic word)
- "Protocol" (technical term)
- "Monday" (day, not a name)
- "Seattle" (location, not person)
- "Project" (generic word)
- "Initiative" (generic word)
- "Committee" (organization type)

Examples of VALID person names:
- "Sarah Chen"
- "Dr. Webb"
- "Torres"
- "Marcus Johnson"
- "Dr. Patel"

Respond with ONLY a JSON array of valid names, nothing else. Example: ["Sarah Chen", "Dr. Webb"]
If no valid names, return: []"""


def validate_entities_with_llm(
    entities: List[Dict],
    document_context: str = ""
) -> List[Dict]:
    """
    Use LLM to filter false positive entities.

    Args:
        entities: List of entity dicts with 'name' and optionally 'type', 'confidence'
        document_context: Optional snippet of source text for context

    Returns:
        Filtered list with only valid entities
    """
    if not entities:
        return []

    # Only validate person entities
    person_entities = [e for e in entities if e.get('type', 'person') == 'person']
    other_entities = [e for e in entities if e.get('type', 'person') != 'person']

    if not person_entities:
        return entities

    # Extract names for validation
    names = []
    name_to_entity = {}
    for e in person_entities:
        name = e.get('name', e.get('raw_value', ''))
        if name:
            names.append(name)
            name_to_entity[name.lower()] = e

    if not names:
        return other_entities

    try:
        # Import here to avoid circular imports
        from recog_engine.core.providers.factory import create_provider, get_available_providers

        available = get_available_providers()
        if not available:
            logger.warning("No LLM providers available for entity validation")
            return entities

        # Use cheapest model - prefer OpenAI gpt-4o-mini
        if "openai" in available:
            provider = create_provider("openai", model="gpt-4o-mini")
        else:
            provider = create_provider("anthropic", model="claude-3-haiku-20240307")

        # Build prompt
        context_section = ""
        if document_context:
            # Truncate context if too long
            ctx = document_context[:500] + "..." if len(document_context) > 500 else document_context
            context_section = f"Document context (for reference):\n\"{ctx}\""

        prompt = ENTITY_VALIDATION_PROMPT.format(
            entity_list=json.dumps(names),
            context_section=context_section
        )

        response = provider.generate(
            prompt=prompt,
            system_prompt="You are a precise named entity validator. Return only valid JSON arrays.",
            temperature=0.0,
            max_tokens=500
        )

        if not response.success:
            logger.error(f"LLM validation failed: {response.error}")
            return entities

        # Parse response
        content = response.content.strip()

        # Try to extract JSON array from response
        # Handle cases where LLM adds extra text
        if '[' in content:
            start = content.index('[')
            end = content.rindex(']') + 1
            content = content[start:end]

        try:
            valid_names = json.loads(content)
            if not isinstance(valid_names, list):
                logger.warning(f"LLM returned non-list: {content}")
                return entities
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}, content: {content}")
            return entities

        # Filter to only valid entities
        valid_names_lower = {n.lower() for n in valid_names}
        validated_persons = [
            e for e in person_entities
            if (e.get('name', e.get('raw_value', '')).lower() in valid_names_lower)
        ]

        # Log what was filtered
        removed = len(person_entities) - len(validated_persons)
        if removed > 0:
            logger.info(f"LLM validation removed {removed} false positive entities from {len(person_entities)}")

        return other_entities + validated_persons

    except Exception as e:
        logger.error(f"Entity validation error: {e}", exc_info=True)
        return entities


def validate_entity_names_batch(
    names: List[str],
    document_context: str = ""
) -> List[str]:
    """
    Validate a list of names using LLM.

    Simpler interface for batch validation of existing entities.

    Args:
        names: List of name strings to validate
        document_context: Optional context

    Returns:
        List of valid names
    """
    if not names:
        return []

    # Convert to entity format
    entities = [{"name": n, "type": "person"} for n in names]

    # Validate
    validated = validate_entities_with_llm(entities, document_context)

    # Extract names back
    return [e.get('name', e.get('raw_value', '')) for e in validated]


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
        now = datetime.now(timezone.utc).isoformat() + "Z"
        
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
        now = datetime.now(timezone.utc).isoformat() + "Z"
        
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
        document_context: str = "",
        validate_with_llm: bool = None,
    ) -> Dict[str, List[Tuple[int, bool]]]:
        """
        Register all entities from Tier 0 extraction.

        Args:
            tier0_entities: The 'entities' dict from preprocess_text()
            source_type: Type of source (e.g., 'document', 'chat')
            source_id: Optional ID of source
            document_context: Optional text snippet for LLM validation context
            validate_with_llm: Override VALIDATE_ENTITIES_WITH_LLM setting

        Returns:
            Dict mapping entity_type to list of (entity_id, is_new) tuples
        """
        results = {
            'phone': [],
            'email': [],
            'person': [],
            'validated': False,
            'validation_removed': 0,
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
        # Handle both old format (list of strings) and new format (list of dicts with 'name' and 'confidence')
        people = tier0_entities.get('people', [])

        # Prepare person entities for potential LLM validation
        person_entities = []
        for person in people:
            if isinstance(person, dict):
                name = person.get('name', '')
                confidence = person.get('confidence', 'medium')
            else:
                name = person
                confidence = 'medium'

            if name and name.strip():
                person_entities.append({
                    'name': name.strip(),
                    'type': 'person',
                    'confidence': confidence
                })

        # LLM Validation (if enabled)
        should_validate = validate_with_llm if validate_with_llm is not None else VALIDATE_ENTITIES_WITH_LLM

        if should_validate and person_entities:
            original_count = len(person_entities)
            person_entities = validate_entities_with_llm(person_entities, document_context)
            results['validated'] = True
            results['validation_removed'] = original_count - len(person_entities)
            logger.info(f"LLM validation: {original_count} -> {len(person_entities)} person entities")

        # Register validated (or unvalidated) person entities
        for person in person_entities:
            name = person.get('name', '')
            if not name:
                continue

            entity_id, is_new = self.register_entity(
                entity_type='person',
                raw_value=name,
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

    # =========================================================================
    # LLM VALIDATION
    # =========================================================================

    def suggest_entity_validation(self, batch_size: int = 50) -> Dict:
        """
        Get LLM suggestions for which entities are false positives.

        Does NOT remove anything - just returns suggestions for user review.

        Args:
            batch_size: Number of entities to validate in one batch

        Returns:
            Dict with suggested_invalid and suggested_valid lists
        """
        # Get unconfirmed person entities
        entities = self.list_entities(
            entity_type='person',
            unconfirmed_only=True,
            limit=batch_size
        )

        if not entities:
            return {
                'total': 0,
                'suggested_invalid': [],
                'suggested_valid': [],
                'message': 'No unconfirmed person entities to validate'
            }

        # Extract names
        names = [e['raw_value'] for e in entities]

        # Validate with LLM
        valid_names = validate_entity_names_batch(names)
        valid_names_lower = {n.lower() for n in valid_names}

        # Categorize
        suggested_invalid = []
        suggested_valid = []

        for entity in entities:
            entity_info = {
                'id': entity['id'],
                'name': entity['raw_value'],
                'occurrence_count': entity.get('occurrence_count', 1)
            }
            if entity['raw_value'].lower() in valid_names_lower:
                suggested_valid.append(entity_info)
            else:
                suggested_invalid.append(entity_info)

        return {
            'total': len(entities),
            'suggested_invalid': suggested_invalid,
            'suggested_valid': suggested_valid,
            'message': f'Analyzed {len(entities)} entities: {len(suggested_invalid)} likely false positives, {len(suggested_valid)} likely valid'
        }

    def remove_entities_by_ids(self, entity_ids: List[int], reason: str = "user_confirmed_invalid") -> Dict:
        """
        Remove specific entities and add to blacklist.

        Args:
            entity_ids: List of entity IDs to remove
            reason: Reason for removal

        Returns:
            Dict with removal results
        """
        if not entity_ids:
            return {'removed': 0, 'removed_names': []}

        conn = self.get_connection()
        removed_names = []

        try:
            for entity_id in entity_ids:
                # Get entity info first
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT raw_value, entity_type FROM entity_registry WHERE id = ?",
                    (entity_id,)
                )
                row = cursor.fetchone()
                if not row:
                    continue

                raw_value = row['raw_value']
                entity_type = row['entity_type']

                # Delete from registry
                conn.execute(
                    "DELETE FROM entity_registry WHERE id = ?",
                    (entity_id,)
                )

                # Add to blacklist
                now = datetime.now(timezone.utc).isoformat() + "Z"
                conn.execute("""
                    INSERT INTO entity_blacklist (normalised_value, raw_value, entity_type, rejection_reason, rejected_by, created_at, updated_at, rejection_count)
                    VALUES (?, ?, ?, ?, 'user', ?, ?, 1)
                    ON CONFLICT(entity_type, normalised_value) DO UPDATE SET
                        rejection_count = rejection_count + 1,
                        updated_at = excluded.updated_at
                """, (raw_value.lower(), raw_value, entity_type, reason, now, now))

                removed_names.append(raw_value)

            conn.commit()
        finally:
            conn.close()

        return {
            'removed': len(removed_names),
            'removed_names': removed_names
        }

    def validate_unconfirmed_persons(self, batch_size: int = 50) -> Dict:
        """
        Validate all unconfirmed person entities using LLM.

        Removes false positives from the registry and adds them to blacklist.
        NOTE: For interactive validation, use suggest_entity_validation() instead.

        Args:
            batch_size: Number of entities to validate in one batch

        Returns:
            Dict with validation results
        """
        # Get suggestions first
        suggestions = self.suggest_entity_validation(batch_size)

        if not suggestions['suggested_invalid']:
            return {
                'validated': suggestions['total'],
                'removed': 0,
                'kept': suggestions['total'],
                'removed_names': [],
                'message': 'No false positives detected'
            }

        # Remove the suggested invalid entities
        entity_ids = [e['id'] for e in suggestions['suggested_invalid']]
        result = self.remove_entities_by_ids(entity_ids, "LLM validation - false positive")

        return {
            'validated': suggestions['total'],
            'removed': result['removed'],
            'kept': suggestions['total'] - result['removed'],
            'removed_names': result['removed_names'],
            'message': f'Validated {suggestions["total"]} entities, removed {result["removed"]} false positives'
        }


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
    # LLM Validation
    'validate_entities_with_llm',
    'validate_entity_names_batch',
    'VALIDATE_ENTITIES_WITH_LLM',
    # Module-level access
    'init_registry',
    'get_registry',
]

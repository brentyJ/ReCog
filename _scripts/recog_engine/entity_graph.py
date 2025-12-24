"""
ReCog Entity Graph - Relationship-Aware Entity Management

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Extends EntityRegistry with:
- Relationship tracking between entities (manages, works_with, etc.)
- Sentiment tracking per entity over time
- Co-occurrence detection (entities appearing together)
- Graph queries (network, timeline, connections)

This enables relational pattern detection in the Synth Engine.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum

from .entity_registry import EntityRegistry, normalise_name

logger = logging.getLogger(__name__)


# =============================================================================
# RELATIONSHIP TYPES
# =============================================================================

class RelationshipType(Enum):
    """Types of relationships between entities."""
    # Professional
    MANAGES = "manages"              # A manages B
    MANAGED_BY = "managed_by"        # A is managed by B (inverse)
    WORKS_WITH = "works_with"        # Colleagues
    REPORTS_TO = "reports_to"        # Hierarchical
    EMPLOYED_BY = "employed_by"      # Person → Organisation
    EMPLOYS = "employs"              # Organisation → Person
    
    # Personal
    FAMILY_OF = "family_of"          # Family relationship
    FRIEND_OF = "friend_of"          # Friendship
    PARTNER_OF = "partner_of"        # Romantic partner
    
    # Contextual
    MENTIONED_WITH = "mentioned_with"  # Co-occurrence without explicit relationship
    ASSOCIATED_WITH = "associated_with"  # General association
    CONTACTED_VIA = "contacted_via"    # Person → Phone/Email
    
    # Temporal
    SUCCEEDED_BY = "succeeded_by"     # Role succession
    PRECEDED_BY = "preceded_by"       # Inverse
    
    @classmethod
    def get_inverse(cls, rel_type: str) -> Optional[str]:
        """Get the inverse relationship type."""
        inverses = {
            "manages": "managed_by",
            "managed_by": "manages",
            "reports_to": "manages",
            "employed_by": "employs",
            "employs": "employed_by",
            "succeeded_by": "preceded_by",
            "preceded_by": "succeeded_by",
        }
        return inverses.get(rel_type)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EntityRelationship:
    """A relationship between two entities."""
    id: int
    source_entity_id: int
    target_entity_id: int
    relationship_type: str
    strength: float = 0.5        # 0-1, how strong/certain
    bidirectional: bool = False  # True for symmetric relationships
    context: Optional[str] = None  # How we know this
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    occurrence_count: int = 1
    source_ids_json: str = "[]"  # JSON array of insight/document IDs
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['source_ids'] = json.loads(self.source_ids_json)
        del d['source_ids_json']
        return d


@dataclass
class EntitySentiment:
    """Sentiment record for an entity from a specific source."""
    id: int
    entity_id: int
    sentiment_score: float  # -1 to 1
    sentiment_label: str    # negative, neutral, positive, mixed
    source_type: str        # 'insight', 'document', 'preflight_item'
    source_id: str
    excerpt: Optional[str] = None
    recorded_at: Optional[str] = None


@dataclass 
class CoOccurrence:
    """Record of entities appearing together."""
    entity_a_id: int
    entity_b_id: int
    count: int
    source_ids: List[str] = field(default_factory=list)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


@dataclass
class EntityNetwork:
    """Network view centered on an entity."""
    center_entity: Dict[str, Any]
    relationships: List[Dict[str, Any]]
    connected_entities: List[Dict[str, Any]]
    co_occurrences: List[Dict[str, Any]]
    sentiment_summary: Dict[str, Any]


# =============================================================================
# ENTITY GRAPH CLASS
# =============================================================================

class EntityGraph(EntityRegistry):
    """
    Entity management with relationship graph capabilities.
    
    Extends EntityRegistry with:
    - Relationship tracking
    - Sentiment history
    - Co-occurrence detection
    - Graph queries
    """
    
    def __init__(self, db_path: Path):
        super().__init__(db_path)
    
    # =========================================================================
    # RELATIONSHIP MANAGEMENT
    # =========================================================================
    
    def add_relationship(
        self,
        source_entity_id: int,
        target_entity_id: int,
        relationship_type: str,
        strength: float = 0.5,
        bidirectional: bool = False,
        context: str = None,
        source_id: str = None,
    ) -> Tuple[int, bool]:
        """
        Add or update a relationship between entities.
        
        Args:
            source_entity_id: The "from" entity
            target_entity_id: The "to" entity
            relationship_type: Type of relationship (see RelationshipType)
            strength: Confidence in the relationship (0-1)
            bidirectional: If True, relationship works both ways
            context: How we know about this relationship
            source_id: ID of insight/document that established this
            
        Returns:
            Tuple of (relationship_id, is_new)
        """
        now = datetime.utcnow().isoformat() + "Z"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if relationship exists
            cursor.execute("""
                SELECT id, occurrence_count, source_ids_json, strength
                FROM entity_relationships
                WHERE source_entity_id = ? AND target_entity_id = ? 
                AND relationship_type = ?
            """, (source_entity_id, target_entity_id, relationship_type))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                rel_id = existing['id']
                count = existing['occurrence_count'] + 1
                sources = json.loads(existing['source_ids_json']) if existing['source_ids_json'] else []
                
                if source_id and source_id not in sources:
                    sources.append(source_id)
                
                # Strengthen relationship with each occurrence (capped at 1.0)
                new_strength = min(1.0, existing['strength'] + 0.1)
                
                cursor.execute("""
                    UPDATE entity_relationships
                    SET occurrence_count = ?, source_ids_json = ?, 
                        last_seen_at = ?, updated_at = ?, strength = ?
                    WHERE id = ?
                """, (count, json.dumps(sources), now, now, new_strength, rel_id))
                
                conn.commit()
                return (rel_id, False)
            else:
                # Create new
                sources = [source_id] if source_id else []
                
                cursor.execute("""
                    INSERT INTO entity_relationships (
                        source_entity_id, target_entity_id, relationship_type,
                        strength, bidirectional, context, source_ids_json,
                        first_seen_at, last_seen_at, occurrence_count,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (
                    source_entity_id, target_entity_id, relationship_type,
                    strength, 1 if bidirectional else 0, context, json.dumps(sources),
                    now, now, now, now
                ))
                
                rel_id = cursor.lastrowid
                
                # If bidirectional, also create inverse
                if bidirectional:
                    cursor.execute("""
                        INSERT INTO entity_relationships (
                            source_entity_id, target_entity_id, relationship_type,
                            strength, bidirectional, context, source_ids_json,
                            first_seen_at, last_seen_at, occurrence_count,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """, (
                        target_entity_id, source_entity_id, relationship_type,
                        strength, 1, context, json.dumps(sources),
                        now, now, now, now
                    ))
                
                conn.commit()
                return (rel_id, True)
                
        finally:
            conn.close()
    
    def get_relationships(
        self,
        entity_id: int,
        relationship_type: str = None,
        direction: str = "both",  # 'outgoing', 'incoming', 'both'
        min_strength: float = 0.0,
    ) -> List[EntityRelationship]:
        """
        Get relationships for an entity.
        
        Args:
            entity_id: The entity to query
            relationship_type: Filter by type (optional)
            direction: 'outgoing' (entity is source), 'incoming' (entity is target), 'both'
            min_strength: Minimum relationship strength
            
        Returns:
            List of EntityRelationship objects
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            conditions = ["strength >= ?"]
            params = [min_strength]
            
            if direction == "outgoing":
                conditions.append("source_entity_id = ?")
                params.append(entity_id)
            elif direction == "incoming":
                conditions.append("target_entity_id = ?")
                params.append(entity_id)
            else:  # both
                conditions.append("(source_entity_id = ? OR target_entity_id = ?)")
                params.extend([entity_id, entity_id])
            
            if relationship_type:
                conditions.append("relationship_type = ?")
                params.append(relationship_type)
            
            cursor.execute(f"""
                SELECT id, source_entity_id, target_entity_id, relationship_type,
                       strength, bidirectional, context, source_ids_json,
                       first_seen_at, last_seen_at, occurrence_count,
                       created_at, updated_at
                FROM entity_relationships
                WHERE {' AND '.join(conditions)}
                ORDER BY strength DESC, occurrence_count DESC
            """, params)
            
            relationships = []
            for row in cursor.fetchall():
                relationships.append(EntityRelationship(
                    id=row['id'],
                    source_entity_id=row['source_entity_id'],
                    target_entity_id=row['target_entity_id'],
                    relationship_type=row['relationship_type'],
                    strength=row['strength'],
                    bidirectional=bool(row['bidirectional']),
                    context=row['context'],
                    source_ids_json=row['source_ids_json'] or "[]",
                    first_seen_at=row['first_seen_at'],
                    last_seen_at=row['last_seen_at'],
                    occurrence_count=row['occurrence_count'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                ))
            
            return relationships
            
        finally:
            conn.close()
    
    def remove_relationship(self, relationship_id: int) -> bool:
        """Remove a relationship by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM entity_relationships WHERE id = ?",
                (relationship_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    # =========================================================================
    # SENTIMENT TRACKING
    # =========================================================================
    
    def record_sentiment(
        self,
        entity_id: int,
        sentiment_score: float,
        source_type: str,
        source_id: str,
        excerpt: str = None,
    ) -> int:
        """
        Record sentiment for an entity from a source.
        
        Args:
            entity_id: The entity
            sentiment_score: -1 (negative) to 1 (positive)
            source_type: 'insight', 'document', etc.
            source_id: ID of the source
            excerpt: Relevant text snippet
            
        Returns:
            Sentiment record ID
        """
        now = datetime.utcnow().isoformat() + "Z"
        
        # Determine label
        if sentiment_score < -0.3:
            label = "negative"
        elif sentiment_score > 0.3:
            label = "positive"
        elif abs(sentiment_score) < 0.1:
            label = "neutral"
        else:
            label = "mixed"
        
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO entity_sentiment (
                    entity_id, sentiment_score, sentiment_label,
                    source_type, source_id, excerpt, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (entity_id, sentiment_score, label, source_type, source_id, excerpt, now))
            
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def get_sentiment_history(
        self,
        entity_id: int,
        limit: int = 50,
    ) -> List[EntitySentiment]:
        """Get sentiment history for an entity."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT id, entity_id, sentiment_score, sentiment_label,
                       source_type, source_id, excerpt, recorded_at
                FROM entity_sentiment
                WHERE entity_id = ?
                ORDER BY recorded_at DESC
                LIMIT ?
            """, (entity_id, limit))
            
            return [EntitySentiment(
                id=row['id'],
                entity_id=row['entity_id'],
                sentiment_score=row['sentiment_score'],
                sentiment_label=row['sentiment_label'],
                source_type=row['source_type'],
                source_id=row['source_id'],
                excerpt=row['excerpt'],
                recorded_at=row['recorded_at'],
            ) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_sentiment_summary(self, entity_id: int) -> Dict[str, Any]:
        """Get aggregated sentiment summary for an entity."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as count,
                    AVG(sentiment_score) as avg_score,
                    MIN(sentiment_score) as min_score,
                    MAX(sentiment_score) as max_score,
                    SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) as positive_count,
                    SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) as negative_count,
                    SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
                    MIN(recorded_at) as first_recorded,
                    MAX(recorded_at) as last_recorded
                FROM entity_sentiment
                WHERE entity_id = ?
            """, (entity_id,))
            
            row = cursor.fetchone()
            
            if not row or row['count'] == 0:
                return {
                    "count": 0,
                    "avg_score": 0,
                    "trend": "unknown",
                }
            
            # Determine overall trend
            avg = row['avg_score'] or 0
            if avg < -0.3:
                trend = "negative"
            elif avg > 0.3:
                trend = "positive"
            else:
                trend = "neutral"
            
            return {
                "count": row['count'],
                "avg_score": round(avg, 3),
                "min_score": round(row['min_score'] or 0, 3),
                "max_score": round(row['max_score'] or 0, 3),
                "positive_count": row['positive_count'] or 0,
                "negative_count": row['negative_count'] or 0,
                "neutral_count": row['neutral_count'] or 0,
                "trend": trend,
                "first_recorded": row['first_recorded'],
                "last_recorded": row['last_recorded'],
            }
        finally:
            conn.close()
    
    # =========================================================================
    # CO-OCCURRENCE TRACKING
    # =========================================================================
    
    def record_co_occurrence(
        self,
        entity_ids: List[int],
        source_type: str,
        source_id: str,
    ) -> int:
        """
        Record that multiple entities appeared together.
        
        Creates pairwise co-occurrence records for all entities in the list.
        
        Args:
            entity_ids: List of entity IDs that appeared together
            source_type: Type of source
            source_id: ID of source
            
        Returns:
            Number of co-occurrence pairs recorded
        """
        if len(entity_ids) < 2:
            return 0
        
        now = datetime.utcnow().isoformat() + "Z"
        recorded = 0
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Create pairs (order by ID to ensure consistency)
            for i, entity_a in enumerate(entity_ids):
                for entity_b in entity_ids[i+1:]:
                    # Always store smaller ID first
                    if entity_a > entity_b:
                        entity_a, entity_b = entity_b, entity_a
                    
                    # Check if exists
                    cursor.execute("""
                        SELECT id, count, source_ids_json
                        FROM entity_co_occurrences
                        WHERE entity_a_id = ? AND entity_b_id = ?
                    """, (entity_a, entity_b))
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update
                        count = existing['count'] + 1
                        sources = json.loads(existing['source_ids_json']) if existing['source_ids_json'] else []
                        source_ref = f"{source_type}:{source_id}"
                        if source_ref not in sources:
                            sources.append(source_ref)
                        
                        cursor.execute("""
                            UPDATE entity_co_occurrences
                            SET count = ?, source_ids_json = ?, last_seen_at = ?
                            WHERE id = ?
                        """, (count, json.dumps(sources), now, existing['id']))
                    else:
                        # Insert
                        cursor.execute("""
                            INSERT INTO entity_co_occurrences (
                                entity_a_id, entity_b_id, count, source_ids_json,
                                first_seen_at, last_seen_at
                            ) VALUES (?, ?, 1, ?, ?, ?)
                        """, (entity_a, entity_b, json.dumps([f"{source_type}:{source_id}"]), now, now))
                    
                    recorded += 1
            
            conn.commit()
            return recorded
            
        finally:
            conn.close()
    
    def get_co_occurrences(
        self,
        entity_id: int,
        min_count: int = 1,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get entities that frequently appear with the given entity."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT 
                    CASE WHEN entity_a_id = ? THEN entity_b_id ELSE entity_a_id END as other_id,
                    count, source_ids_json, first_seen_at, last_seen_at
                FROM entity_co_occurrences
                WHERE (entity_a_id = ? OR entity_b_id = ?) AND count >= ?
                ORDER BY count DESC
                LIMIT ?
            """, (entity_id, entity_id, entity_id, min_count, limit))
            
            results = []
            for row in cursor.fetchall():
                other_entity = self.get_entity_by_id(row['other_id'])
                results.append({
                    "entity": other_entity,
                    "count": row['count'],
                    "source_ids": json.loads(row['source_ids_json']) if row['source_ids_json'] else [],
                    "first_seen_at": row['first_seen_at'],
                    "last_seen_at": row['last_seen_at'],
                })
            
            return results
        finally:
            conn.close()
    
    # =========================================================================
    # GRAPH QUERIES
    # =========================================================================
    
    def get_network(
        self,
        entity_id: int,
        depth: int = 1,
        min_strength: float = 0.2,
    ) -> EntityNetwork:
        """
        Get the relationship network around an entity.
        
        Args:
            entity_id: Center entity
            depth: How many hops to traverse (1 = direct connections only)
            min_strength: Minimum relationship strength to include
            
        Returns:
            EntityNetwork with center entity, relationships, and connected entities
        """
        # Get center entity
        center = self.get_entity_by_id(entity_id)
        if not center:
            return None
        
        # Get relationships
        relationships = self.get_relationships(entity_id, min_strength=min_strength)
        
        # Get unique connected entity IDs
        connected_ids: Set[int] = set()
        for rel in relationships:
            if rel.source_entity_id != entity_id:
                connected_ids.add(rel.source_entity_id)
            if rel.target_entity_id != entity_id:
                connected_ids.add(rel.target_entity_id)
        
        # Fetch connected entities
        connected_entities = []
        for eid in connected_ids:
            entity = self.get_entity_by_id(eid)
            if entity:
                connected_entities.append(entity)
        
        # Get co-occurrences
        co_occurrences = self.get_co_occurrences(entity_id)
        
        # Get sentiment summary
        sentiment_summary = self.get_sentiment_summary(entity_id)
        
        # If depth > 1, recursively get next layer
        if depth > 1:
            for eid in list(connected_ids):
                sub_rels = self.get_relationships(eid, min_strength=min_strength)
                for rel in sub_rels:
                    if rel not in relationships:
                        relationships.append(rel)
                    if rel.source_entity_id not in connected_ids and rel.source_entity_id != entity_id:
                        connected_ids.add(rel.source_entity_id)
                        entity = self.get_entity_by_id(rel.source_entity_id)
                        if entity:
                            connected_entities.append(entity)
                    if rel.target_entity_id not in connected_ids and rel.target_entity_id != entity_id:
                        connected_ids.add(rel.target_entity_id)
                        entity = self.get_entity_by_id(rel.target_entity_id)
                        if entity:
                            connected_entities.append(entity)
        
        return EntityNetwork(
            center_entity=center,
            relationships=[r.to_dict() for r in relationships],
            connected_entities=connected_entities,
            co_occurrences=co_occurrences,
            sentiment_summary=sentiment_summary,
        )
    
    def get_timeline(
        self,
        entity_id: int,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get a timeline of entity appearances/events.
        
        Combines:
        - Insight sources where entity appears
        - Sentiment records
        - Relationship formations
        
        Returns chronologically sorted list.
        """
        events = []
        
        conn = self.get_connection()
        try:
            # Get insight sources
            cursor = conn.execute("""
                SELECT is_.insight_id, is_.source_type, is_.source_id, is_.linked_at,
                       i.summary
                FROM insight_sources is_
                JOIN insights i ON i.id = is_.insight_id
                WHERE i.summary LIKE '%' || ? || '%'
                ORDER BY is_.linked_at DESC
                LIMIT ?
            """, (entity_id, limit))
            
            # This would need entity name, but we're approximating
            # In practice, we'd track entity → insight links explicitly
            
            # Get sentiment records
            sentiments = self.get_sentiment_history(entity_id, limit=limit)
            for s in sentiments:
                events.append({
                    "type": "sentiment",
                    "timestamp": s.recorded_at,
                    "data": {
                        "score": s.sentiment_score,
                        "label": s.sentiment_label,
                        "source_type": s.source_type,
                        "source_id": s.source_id,
                        "excerpt": s.excerpt,
                    }
                })
            
            # Get relationship formations
            cursor = conn.execute("""
                SELECT id, target_entity_id, relationship_type, first_seen_at, context
                FROM entity_relationships
                WHERE source_entity_id = ?
                ORDER BY first_seen_at DESC
                LIMIT ?
            """, (entity_id, limit))
            
            for row in cursor.fetchall():
                target = self.get_entity_by_id(row['target_entity_id'])
                events.append({
                    "type": "relationship",
                    "timestamp": row['first_seen_at'],
                    "data": {
                        "relationship_type": row['relationship_type'],
                        "target_entity": target.get('display_name') or target.get('raw_value') if target else "Unknown",
                        "context": row['context'],
                    }
                })
            
            # Sort by timestamp
            events.sort(key=lambda x: x.get('timestamp') or '', reverse=True)
            
            return events[:limit]
            
        finally:
            conn.close()
    
    def find_path(
        self,
        source_entity_id: int,
        target_entity_id: int,
        max_depth: int = 4,
    ) -> Optional[List[int]]:
        """
        Find the shortest relationship path between two entities.
        
        Uses BFS to find shortest path.
        
        Returns:
            List of entity IDs forming the path, or None if no path exists
        """
        if source_entity_id == target_entity_id:
            return [source_entity_id]
        
        # BFS
        visited = {source_entity_id}
        queue = [(source_entity_id, [source_entity_id])]
        
        while queue:
            current_id, path = queue.pop(0)
            
            if len(path) > max_depth:
                continue
            
            # Get connections
            relationships = self.get_relationships(current_id)
            
            for rel in relationships:
                next_id = rel.target_entity_id if rel.source_entity_id == current_id else rel.source_entity_id
                
                if next_id == target_entity_id:
                    return path + [next_id]
                
                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, path + [next_id]))
        
        return None  # No path found
    
    # =========================================================================
    # INTEGRATION WITH TIER 0 AND INSIGHTS
    # =========================================================================
    
    def process_insight_entities(
        self,
        insight_id: str,
        summary: str,
        entities_mentioned: List[str],
        emotional_tags: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Process entity mentions from an insight.
        
        - Registers new entities
        - Records co-occurrences
        - Infers sentiment from emotional tags
        - Suggests relationships based on context
        
        Args:
            insight_id: ID of the source insight
            summary: The insight summary text
            entities_mentioned: List of entity names/values mentioned
            emotional_tags: Emotional tags from the insight
            
        Returns:
            Processing results (entities found, relationships suggested, etc.)
        """
        results = {
            "entities_registered": [],
            "co_occurrences_recorded": 0,
            "sentiments_recorded": 0,
        }
        
        # Register/find entities
        entity_ids = []
        for entity_name in entities_mentioned:
            normalised = normalise_name(entity_name)
            
            # Try to find existing
            entity = self.get_entity('person', normalised)
            
            if entity:
                entity_ids.append(entity['id'])
            else:
                # Register new
                eid, is_new = self.register_entity(
                    entity_type='person',
                    raw_value=entity_name,
                    normalised_value=normalised,
                    source_type='insight',
                )
                entity_ids.append(eid)
                if is_new:
                    results["entities_registered"].append(entity_name)
        
        # Record co-occurrences
        if len(entity_ids) >= 2:
            results["co_occurrences_recorded"] = self.record_co_occurrence(
                entity_ids=entity_ids,
                source_type='insight',
                source_id=insight_id,
            )
        
        # Infer sentiment from emotional tags
        if emotional_tags:
            positive_emotions = {'joy', 'hope', 'gratitude', 'love', 'excitement', 'pride', 'relief'}
            negative_emotions = {'sadness', 'anger', 'fear', 'frustration', 'anxiety', 'guilt', 'shame', 'resentment'}
            
            pos_count = sum(1 for e in emotional_tags if e.lower() in positive_emotions)
            neg_count = sum(1 for e in emotional_tags if e.lower() in negative_emotions)
            
            if pos_count + neg_count > 0:
                # Calculate sentiment score
                sentiment_score = (pos_count - neg_count) / (pos_count + neg_count)
                
                # Record for each entity mentioned
                for eid in entity_ids:
                    self.record_sentiment(
                        entity_id=eid,
                        sentiment_score=sentiment_score,
                        source_type='insight',
                        source_id=insight_id,
                        excerpt=summary[:200] if summary else None,
                    )
                    results["sentiments_recorded"] += 1
        
        return results
    
    # =========================================================================
    # GRAPH STATISTICS
    # =========================================================================
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the entity graph."""
        stats = self.get_stats()  # Base entity stats
        
        conn = self.get_connection()
        try:
            # Relationship counts
            cursor = conn.execute("""
                SELECT relationship_type, COUNT(*) as count
                FROM entity_relationships
                GROUP BY relationship_type
            """)
            stats['relationships'] = {row[0]: row[1] for row in cursor.fetchall()}
            stats['total_relationships'] = sum(stats['relationships'].values())
            
            # Co-occurrence stats
            cursor = conn.execute("""
                SELECT COUNT(*), SUM(count), AVG(count)
                FROM entity_co_occurrences
            """)
            row = cursor.fetchone()
            stats['co_occurrences'] = {
                'unique_pairs': row[0] or 0,
                'total_count': row[1] or 0,
                'avg_per_pair': round(row[2] or 0, 2),
            }
            
            # Sentiment stats
            cursor = conn.execute("""
                SELECT sentiment_label, COUNT(*)
                FROM entity_sentiment
                GROUP BY sentiment_label
            """)
            stats['sentiment_counts'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Most connected entities
            cursor = conn.execute("""
                SELECT entity_id, COUNT(*) as rel_count
                FROM (
                    SELECT source_entity_id as entity_id FROM entity_relationships
                    UNION ALL
                    SELECT target_entity_id as entity_id FROM entity_relationships
                )
                GROUP BY entity_id
                ORDER BY rel_count DESC
                LIMIT 10
            """)
            
            most_connected = []
            for row in cursor.fetchall():
                entity = self.get_entity_by_id(row[0])
                if entity:
                    most_connected.append({
                        'entity': entity.get('display_name') or entity.get('raw_value'),
                        'relationship_count': row[1],
                    })
            stats['most_connected'] = most_connected
            
            return stats
            
        finally:
            conn.close()


# =============================================================================
# MODULE-LEVEL CONVENIENCE
# =============================================================================

_entity_graph: Optional[EntityGraph] = None


def init_entity_graph(db_path: Path) -> EntityGraph:
    """Initialize the global EntityGraph instance."""
    global _entity_graph
    _entity_graph = EntityGraph(db_path)
    return _entity_graph


def get_entity_graph() -> Optional[EntityGraph]:
    """Get the global EntityGraph instance."""
    return _entity_graph


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Types
    'RelationshipType',
    'EntityRelationship',
    'EntitySentiment',
    'CoOccurrence',
    'EntityNetwork',
    # Class
    'EntityGraph',
    # Module-level
    'init_entity_graph',
    'get_entity_graph',
]

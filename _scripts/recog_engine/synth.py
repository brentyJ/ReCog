"""
ReCog Synth Engine - Pattern Synthesis from Insights

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

The Synth Engine implements the REDUCE layer of ReCog's analytical pipeline:
- Clusters related insights by theme, time, or entity
- Synthesizes higher-order patterns from insight clusters
- Detects contradictions and emotional arcs
- Generates meta-level understanding from raw observations

This is where "recursive insight" happens - transforming isolated
observations into connected understanding.
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from uuid import uuid4
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# TYPES
# =============================================================================

class ClusterStrategy(Enum):
    """How to cluster insights for synthesis."""
    THEMATIC = "thematic"      # Group by shared themes
    TEMPORAL = "temporal"      # Group by time periods
    ENTITY = "entity"          # Group by mentioned people/places
    EMOTIONAL = "emotional"    # Group by emotional content
    AUTO = "auto"              # Let the engine decide


class PatternType(Enum):
    """Types of patterns the Synth Engine can detect."""
    BEHAVIORAL = "behavioral"      # Actions, habits, tendencies
    EMOTIONAL = "emotional"        # Feeling patterns, mood arcs
    TEMPORAL = "temporal"          # Time-based patterns (weekly, seasonal)
    RELATIONAL = "relational"      # Patterns involving other people
    COGNITIVE = "cognitive"        # Thought patterns, beliefs
    TRANSITIONAL = "transitional"  # Life changes, pivots


@dataclass
class InsightCluster:
    """A group of related insights awaiting synthesis."""
    id: str
    strategy: str
    cluster_key: str  # What groups them (theme name, date range, entity, etc.)
    insight_ids: List[str]
    insight_count: int
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    shared_themes: List[str] = field(default_factory=list)
    shared_entities: List[str] = field(default_factory=list)
    avg_significance: float = 0.5
    status: str = "pending"  # pending, synthesizing, complete, failed
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SynthesizedPattern:
    """A pattern synthesized from an insight cluster."""
    id: str
    name: str
    description: str
    pattern_type: str
    insight_ids: List[str]
    insight_count: int
    
    # Evidence
    supporting_excerpts: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    
    # Scoring
    strength: float = 0.5       # How strong is this pattern (0-1)
    confidence: float = 0.5     # How confident are we (0-1)
    
    # Temporal
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    
    # Related entities
    entities_involved: List[str] = field(default_factory=list)
    
    # Meta
    status: str = "detected"  # detected, confirmed, rejected, superseded
    source_cluster_id: Optional[str] = None
    analysis_model: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SynthResult:
    """Result of a synthesis operation."""
    success: bool
    patterns_created: int = 0
    patterns_merged: int = 0
    clusters_processed: int = 0
    errors: List[str] = field(default_factory=list)
    patterns: List[SynthesizedPattern] = field(default_factory=list)


# =============================================================================
# SYNTH PROMPTS
# =============================================================================

SYNTH_SYSTEM_PROMPT = """You are a pattern synthesis engine. Your role is to identify 
higher-order patterns from a collection of individual observations/insights.

You think like a skilled therapist or biographer - looking for:
- Recurring themes and behaviors
- Emotional arcs and transitions
- Relationship dynamics
- Cause-and-effect chains
- Contradictions that reveal complexity
- Growth, regression, or stagnation patterns

You are rigorous: every pattern must be grounded in the provided insights.
You never fabricate or assume beyond what the evidence supports.
You calibrate confidence based on evidence strength."""

SYNTH_CLUSTER_PROMPT = """Analyze these {count} insights and identify meaningful patterns.

## Insights to Analyze:
{insights_text}

## Cluster Context:
- Grouping strategy: {strategy}
- Cluster key: {cluster_key}
- Date range: {date_range}
- Shared themes: {shared_themes}
- Entities mentioned: {entities}

## Your Task:
Identify 1-3 significant patterns from these insights. For each pattern:
1. Give it a clear, descriptive name
2. Explain what the pattern reveals
3. Rate its strength (how pronounced is it?) and confidence (how certain are you?)
4. Note any contradictions or nuances
5. Identify which insights support it

Respond in this exact JSON format:
```json
{{
  "patterns": [
    {{
      "name": "Pattern name (concise but descriptive)",
      "description": "What this pattern reveals about the person/situation",
      "pattern_type": "behavioral|emotional|temporal|relational|cognitive|transitional",
      "strength": 0.0-1.0,
      "confidence": 0.0-1.0,
      "supporting_insight_indices": [0, 2, 4],
      "supporting_excerpts": ["Key quote 1", "Key quote 2"],
      "contradictions": ["Any conflicting evidence or nuance"],
      "entities_involved": ["Names of people/places central to this pattern"]
    }}
  ],
  "meta_observations": "Any overall observations about this cluster",
  "suggested_follow_ups": ["Questions worth exploring further"]
}}
```

Only output valid JSON. Be rigorous - patterns must be grounded in evidence."""


# =============================================================================
# CLUSTERING FUNCTIONS
# =============================================================================

def cluster_by_theme(
    insights: List[Dict[str, Any]],
    min_cluster_size: int = 3,
) -> List[InsightCluster]:
    """
    Cluster insights by shared themes.
    
    Insights with overlapping themes are grouped together.
    """
    from collections import defaultdict
    
    # Build theme -> insight mapping
    theme_insights: Dict[str, List[str]] = defaultdict(list)
    insight_lookup: Dict[str, Dict] = {i["id"]: i for i in insights}
    
    for insight in insights:
        themes = insight.get("themes") or []
        if isinstance(themes, str):
            try:
                themes = json.loads(themes)
            except:
                themes = [themes]
        
        for theme in themes:
            theme_lower = theme.lower().strip()
            if theme_lower:
                theme_insights[theme_lower].append(insight["id"])
    
    # Create clusters from themes with enough insights
    clusters = []
    processed_ids = set()
    
    # Sort themes by insight count (largest first)
    sorted_themes = sorted(
        theme_insights.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )
    
    for theme, insight_ids in sorted_themes:
        # Filter out already-processed insights
        available_ids = [iid for iid in insight_ids if iid not in processed_ids]
        
        if len(available_ids) >= min_cluster_size:
            # Calculate cluster metadata
            cluster_insights = [insight_lookup[iid] for iid in available_ids]
            
            dates = [i.get("earliest_source_date") or i.get("created_at") for i in cluster_insights]
            dates = [d for d in dates if d]
            
            avg_sig = sum(i.get("significance", 0.5) for i in cluster_insights) / len(cluster_insights)
            
            # Find shared entities
            all_entities = []
            for i in cluster_insights:
                # Could extract from sources or metadata
                pass
            
            cluster = InsightCluster(
                id=f"cluster_{uuid4().hex[:12]}",
                strategy=ClusterStrategy.THEMATIC.value,
                cluster_key=theme,
                insight_ids=available_ids,
                insight_count=len(available_ids),
                date_range_start=min(dates) if dates else None,
                date_range_end=max(dates) if dates else None,
                shared_themes=[theme],
                avg_significance=avg_sig,
            )
            
            clusters.append(cluster)
            processed_ids.update(available_ids)
    
    return clusters


def cluster_by_time(
    insights: List[Dict[str, Any]],
    window_days: int = 30,
    min_cluster_size: int = 3,
) -> List[InsightCluster]:
    """
    Cluster insights by time periods.
    
    Groups insights within the same time window.
    """
    from collections import defaultdict
    
    # Parse dates and bucket by period
    period_insights: Dict[str, List[str]] = defaultdict(list)
    insight_lookup: Dict[str, Dict] = {i["id"]: i for i in insights}
    
    for insight in insights:
        date_str = insight.get("earliest_source_date") or insight.get("created_at")
        if not date_str:
            continue
        
        try:
            # Parse ISO date
            if "T" in date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(date_str)
            
            # Create period key (e.g., "2024-Q1" or "2024-03")
            if window_days >= 90:
                period_key = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
            elif window_days >= 28:
                period_key = f"{dt.year}-{dt.month:02d}"
            else:
                # Week-based
                week = dt.isocalendar()[1]
                period_key = f"{dt.year}-W{week:02d}"
            
            period_insights[period_key].append(insight["id"])
        except (ValueError, TypeError):
            continue
    
    # Create clusters
    clusters = []
    
    for period, insight_ids in sorted(period_insights.items()):
        if len(insight_ids) >= min_cluster_size:
            cluster_insights = [insight_lookup[iid] for iid in insight_ids]
            
            # Collect all themes from this period
            all_themes = []
            for i in cluster_insights:
                themes = i.get("themes") or []
                if isinstance(themes, str):
                    try:
                        themes = json.loads(themes)
                    except:
                        themes = []
                all_themes.extend(themes)
            
            # Find most common themes
            from collections import Counter
            theme_counts = Counter(t.lower().strip() for t in all_themes if t)
            top_themes = [t for t, _ in theme_counts.most_common(5)]
            
            avg_sig = sum(i.get("significance", 0.5) for i in cluster_insights) / len(cluster_insights)
            
            cluster = InsightCluster(
                id=f"cluster_{uuid4().hex[:12]}",
                strategy=ClusterStrategy.TEMPORAL.value,
                cluster_key=period,
                insight_ids=insight_ids,
                insight_count=len(insight_ids),
                date_range_start=period,
                date_range_end=period,
                shared_themes=top_themes,
                avg_significance=avg_sig,
            )
            
            clusters.append(cluster)
    
    return clusters


def cluster_by_entity(
    insights: List[Dict[str, Any]],
    entity_registry: Any,  # EntityRegistry instance
    min_cluster_size: int = 3,
) -> List[InsightCluster]:
    """
    Cluster insights by mentioned entities (people, places).
    
    Groups insights that reference the same person/entity.
    """
    from collections import defaultdict
    
    # This requires entity extraction from insight sources
    # For now, use a simplified approach based on insight content
    
    entity_insights: Dict[str, List[str]] = defaultdict(list)
    insight_lookup: Dict[str, Dict] = {i["id"]: i for i in insights}
    
    # Get confirmed entities from registry
    if entity_registry:
        entities = entity_registry.list_entities(entity_type="person", confirmed_only=True)
        entity_names = {e["display_name"] or e["raw_value"]: e for e in entities}
    else:
        entity_names = {}
    
    for insight in insights:
        summary = insight.get("summary", "").lower()
        
        for name, entity in entity_names.items():
            if name.lower() in summary:
                entity_insights[name].append(insight["id"])
    
    # Create clusters
    clusters = []
    
    for entity_name, insight_ids in entity_insights.items():
        if len(insight_ids) >= min_cluster_size:
            cluster_insights = [insight_lookup[iid] for iid in insight_ids]
            
            dates = [i.get("earliest_source_date") or i.get("created_at") for i in cluster_insights]
            dates = [d for d in dates if d]
            
            avg_sig = sum(i.get("significance", 0.5) for i in cluster_insights) / len(cluster_insights)
            
            cluster = InsightCluster(
                id=f"cluster_{uuid4().hex[:12]}",
                strategy=ClusterStrategy.ENTITY.value,
                cluster_key=entity_name,
                insight_ids=insight_ids,
                insight_count=len(insight_ids),
                date_range_start=min(dates) if dates else None,
                date_range_end=max(dates) if dates else None,
                shared_entities=[entity_name],
                avg_significance=avg_sig,
            )
            
            clusters.append(cluster)
    
    return clusters


def auto_cluster(
    insights: List[Dict[str, Any]],
    entity_registry: Any = None,
    min_cluster_size: int = 3,
) -> List[InsightCluster]:
    """
    Automatically cluster insights using multiple strategies.
    
    Runs all clustering strategies and returns non-overlapping clusters
    prioritizing by cluster quality (size * avg_significance).
    """
    all_clusters = []
    
    # Run each strategy
    all_clusters.extend(cluster_by_theme(insights, min_cluster_size))
    all_clusters.extend(cluster_by_time(insights, window_days=30, min_cluster_size=min_cluster_size))
    
    if entity_registry:
        all_clusters.extend(cluster_by_entity(insights, entity_registry, min_cluster_size))
    
    # Score and deduplicate
    # Score = insight_count * avg_significance
    for cluster in all_clusters:
        cluster._score = cluster.insight_count * cluster.avg_significance
    
    # Sort by score descending
    all_clusters.sort(key=lambda c: c._score, reverse=True)
    
    # Select non-overlapping clusters
    selected = []
    used_insights = set()
    
    for cluster in all_clusters:
        # Check overlap
        overlap = len(set(cluster.insight_ids) & used_insights)
        if overlap < len(cluster.insight_ids) * 0.5:  # Allow up to 50% overlap
            selected.append(cluster)
            used_insights.update(cluster.insight_ids)
    
    return selected


# =============================================================================
# SYNTH ENGINE CLASS
# =============================================================================

class SynthEngine:
    """
    The Synth Engine - REDUCE layer for ReCog.
    
    Transforms isolated insights into connected patterns through:
    1. Clustering related insights
    2. Synthesizing patterns via LLM
    3. Storing and managing patterns
    """
    
    def __init__(
        self,
        db_path: Path,
        insight_store: Any = None,
        entity_registry: Any = None,
    ):
        self.db_path = Path(db_path)
        self.insight_store = insight_store
        self.entity_registry = entity_registry
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    # -------------------------------------------------------------------------
    # CLUSTERING
    # -------------------------------------------------------------------------
    
    def create_clusters(
        self,
        strategy: ClusterStrategy = ClusterStrategy.AUTO,
        min_cluster_size: int = 3,
        insight_status: str = "raw",
    ) -> List[InsightCluster]:
        """
        Create insight clusters ready for synthesis.
        
        Args:
            strategy: How to cluster (thematic, temporal, entity, auto)
            min_cluster_size: Minimum insights per cluster
            insight_status: Only cluster insights with this status
        
        Returns:
            List of InsightCluster objects
        """
        # Fetch insights
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT id, summary, themes_json, emotional_tags_json,
                       significance, confidence, insight_type, status,
                       earliest_source_date, latest_source_date, created_at
                FROM insights
                WHERE status = ?
                ORDER BY created_at DESC
            """, (insight_status,))
            
            insights = []
            for row in cursor.fetchall():
                insights.append({
                    "id": row["id"],
                    "summary": row["summary"],
                    "themes": json.loads(row["themes_json"]) if row["themes_json"] else [],
                    "emotional_tags": json.loads(row["emotional_tags_json"]) if row["emotional_tags_json"] else [],
                    "significance": row["significance"],
                    "confidence": row["confidence"],
                    "insight_type": row["insight_type"],
                    "status": row["status"],
                    "earliest_source_date": row["earliest_source_date"],
                    "created_at": row["created_at"],
                })
        finally:
            conn.close()
        
        if not insights:
            logger.info("No insights found for clustering")
            return []
        
        logger.info(f"Clustering {len(insights)} insights with strategy: {strategy.value}")
        
        # Run clustering
        if strategy == ClusterStrategy.THEMATIC:
            clusters = cluster_by_theme(insights, min_cluster_size)
        elif strategy == ClusterStrategy.TEMPORAL:
            clusters = cluster_by_time(insights, min_cluster_size=min_cluster_size)
        elif strategy == ClusterStrategy.ENTITY:
            clusters = cluster_by_entity(insights, self.entity_registry, min_cluster_size)
        else:  # AUTO
            clusters = auto_cluster(insights, self.entity_registry, min_cluster_size)
        
        logger.info(f"Created {len(clusters)} clusters")
        
        # Save clusters to database
        self._save_clusters(clusters)
        
        return clusters
    
    def _save_clusters(self, clusters: List[InsightCluster]):
        """Save clusters to database."""
        conn = self._get_conn()
        try:
            for cluster in clusters:
                conn.execute("""
                    INSERT OR REPLACE INTO insight_clusters
                    (id, strategy, cluster_key, insight_ids_json, insight_count,
                     date_range_start, date_range_end, shared_themes_json,
                     shared_entities_json, avg_significance, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cluster.id,
                    cluster.strategy,
                    cluster.cluster_key,
                    json.dumps(cluster.insight_ids),
                    cluster.insight_count,
                    cluster.date_range_start,
                    cluster.date_range_end,
                    json.dumps(cluster.shared_themes),
                    json.dumps(cluster.shared_entities),
                    cluster.avg_significance,
                    cluster.status,
                    cluster.created_at,
                ))
            conn.commit()
        finally:
            conn.close()
    
    def get_pending_clusters(self, limit: int = 10) -> List[InsightCluster]:
        """Get clusters awaiting synthesis."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM insight_clusters
                WHERE status = 'pending'
                ORDER BY avg_significance DESC, insight_count DESC
                LIMIT ?
            """, (limit,))
            
            clusters = []
            for row in cursor.fetchall():
                clusters.append(InsightCluster(
                    id=row["id"],
                    strategy=row["strategy"],
                    cluster_key=row["cluster_key"],
                    insight_ids=json.loads(row["insight_ids_json"]),
                    insight_count=row["insight_count"],
                    date_range_start=row["date_range_start"],
                    date_range_end=row["date_range_end"],
                    shared_themes=json.loads(row["shared_themes_json"]) if row["shared_themes_json"] else [],
                    shared_entities=json.loads(row["shared_entities_json"]) if row["shared_entities_json"] else [],
                    avg_significance=row["avg_significance"],
                    status=row["status"],
                    created_at=row["created_at"],
                ))
            
            return clusters
        finally:
            conn.close()
    
    # -------------------------------------------------------------------------
    # SYNTHESIS
    # -------------------------------------------------------------------------
    
    def build_synth_prompt(self, cluster: InsightCluster) -> str:
        """Build the synthesis prompt for a cluster."""
        # Fetch full insight data
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" * len(cluster.insight_ids))
            cursor = conn.execute(f"""
                SELECT id, summary, themes_json, emotional_tags_json,
                       significance, excerpt, earliest_source_date
                FROM insights
                WHERE id IN ({placeholders})
            """, cluster.insight_ids)
            
            insights_text = []
            for i, row in enumerate(cursor.fetchall()):
                themes = json.loads(row["themes_json"]) if row["themes_json"] else []
                emotions = json.loads(row["emotional_tags_json"]) if row["emotional_tags_json"] else []
                
                insight_block = f"""
### Insight {i} (significance: {row['significance']:.2f})
**Summary:** {row['summary']}
**Themes:** {', '.join(themes) if themes else 'none'}
**Emotions:** {', '.join(emotions) if emotions else 'none'}
**Date:** {row['earliest_source_date'] or 'unknown'}
**Excerpt:** {row['excerpt'] or 'N/A'}
"""
                insights_text.append(insight_block)
        finally:
            conn.close()
        
        # Build date range string
        if cluster.date_range_start and cluster.date_range_end:
            if cluster.date_range_start == cluster.date_range_end:
                date_range = cluster.date_range_start
            else:
                date_range = f"{cluster.date_range_start} to {cluster.date_range_end}"
        else:
            date_range = "unknown"
        
        return SYNTH_CLUSTER_PROMPT.format(
            count=cluster.insight_count,
            insights_text="\n".join(insights_text),
            strategy=cluster.strategy,
            cluster_key=cluster.cluster_key,
            date_range=date_range,
            shared_themes=", ".join(cluster.shared_themes) if cluster.shared_themes else "none",
            entities=", ".join(cluster.shared_entities) if cluster.shared_entities else "none",
        )
    
    def parse_synth_response(
        self,
        response_text: str,
        cluster: InsightCluster,
        model_name: str = None,
    ) -> List[SynthesizedPattern]:
        """Parse LLM response into SynthesizedPattern objects."""
        # Extract JSON from response
        try:
            # Handle markdown code blocks
            if "```json" in response_text:
                start = response_text.index("```json") + 7
                end = response_text.index("```", start)
                json_str = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.index("```") + 3
                end = response_text.index("```", start)
                json_str = response_text[start:end].strip()
            else:
                json_str = response_text.strip()
            
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse synth response: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            return []
        
        patterns = []
        
        for p in data.get("patterns", []):
            # Map insight indices to actual IDs
            supporting_indices = p.get("supporting_insight_indices", [])
            supporting_ids = [
                cluster.insight_ids[i]
                for i in supporting_indices
                if i < len(cluster.insight_ids)
            ]
            
            pattern = SynthesizedPattern(
                id=f"pattern_{uuid4().hex[:12]}",
                name=p.get("name", "Unnamed Pattern"),
                description=p.get("description", ""),
                pattern_type=p.get("pattern_type", "behavioral"),
                insight_ids=supporting_ids or cluster.insight_ids,
                insight_count=len(supporting_ids) if supporting_ids else cluster.insight_count,
                supporting_excerpts=p.get("supporting_excerpts", []),
                contradictions=p.get("contradictions", []),
                strength=float(p.get("strength", 0.5)),
                confidence=float(p.get("confidence", 0.5)),
                date_range_start=cluster.date_range_start,
                date_range_end=cluster.date_range_end,
                entities_involved=p.get("entities_involved", []),
                source_cluster_id=cluster.id,
                analysis_model=model_name,
            )
            
            patterns.append(pattern)
        
        return patterns
    
    def synthesize_cluster(
        self,
        cluster: InsightCluster,
        provider: Any,  # LLM provider
    ) -> List[SynthesizedPattern]:
        """
        Run synthesis on a single cluster.
        
        Args:
            cluster: The InsightCluster to synthesize
            provider: LLM provider instance
        
        Returns:
            List of SynthesizedPattern objects
        """
        # Build prompt
        prompt = self.build_synth_prompt(cluster)
        
        # Call LLM
        try:
            response = provider.generate(
                prompt=prompt,
                system_prompt=SYNTH_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=2000,
            )
            
            if not response.success:
                logger.error(f"LLM error during synthesis: {response.error}")
                return []
            
            # Parse response
            patterns = self.parse_synth_response(
                response.content,
                cluster,
                model_name=response.model,
            )
            
            return patterns
            
        except Exception as e:
            logger.exception(f"Synthesis failed for cluster {cluster.id}")
            return []
    
    # -------------------------------------------------------------------------
    # PATTERN STORAGE
    # -------------------------------------------------------------------------
    
    def save_pattern(self, pattern: SynthesizedPattern) -> bool:
        """Save a synthesized pattern to the database."""
        conn = self._get_conn()
        try:
            now = datetime.utcnow().isoformat() + "Z"
            
            conn.execute("""
                INSERT OR REPLACE INTO patterns
                (id, name, description, pattern_type, insight_ids_json, insight_count,
                 strength, confidence, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern.id,
                pattern.name,
                pattern.description,
                pattern.pattern_type,
                json.dumps(pattern.insight_ids),
                pattern.insight_count,
                pattern.strength,
                pattern.confidence,
                pattern.status,
                pattern.created_at,
                now,
            ))
            
            # Also save extended data to pattern_details (if table exists)
            # For now, store in the patterns table metadata
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save pattern: {e}")
            return False
        finally:
            conn.close()
    
    def save_patterns_batch(self, patterns: List[SynthesizedPattern]) -> Dict[str, Any]:
        """Save multiple patterns."""
        saved = 0
        failed = 0
        
        for pattern in patterns:
            if self.save_pattern(pattern):
                saved += 1
            else:
                failed += 1
        
        return {"saved": saved, "failed": failed}
    
    def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Get a pattern by ID."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM patterns WHERE id = ?",
                (pattern_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "pattern_type": row["pattern_type"],
                "insight_ids": json.loads(row["insight_ids_json"]) if row["insight_ids_json"] else [],
                "insight_count": row["insight_count"],
                "strength": row["strength"],
                "confidence": row["confidence"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        finally:
            conn.close()
    
    def list_patterns(
        self,
        pattern_type: Optional[str] = None,
        status: Optional[str] = None,
        min_strength: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List patterns with filters."""
        conn = self._get_conn()
        try:
            conditions = []
            params = []
            
            if pattern_type:
                conditions.append("pattern_type = ?")
                params.append(pattern_type)
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            if min_strength is not None:
                conditions.append("strength >= ?")
                params.append(min_strength)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM patterns WHERE {where_clause}"
            total = conn.execute(count_query, params).fetchone()[0]
            
            # Get patterns
            query = f"""
                SELECT * FROM patterns
                WHERE {where_clause}
                ORDER BY strength DESC, confidence DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            cursor = conn.execute(query, params)
            
            patterns = []
            for row in cursor.fetchall():
                patterns.append({
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "pattern_type": row["pattern_type"],
                    "insight_count": row["insight_count"],
                    "strength": row["strength"],
                    "confidence": row["confidence"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                })
            
            return {
                "patterns": patterns,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Synth Engine statistics."""
        conn = self._get_conn()
        try:
            stats = {}
            
            # Pattern counts by status
            for row in conn.execute(
                "SELECT status, COUNT(*) as count FROM patterns GROUP BY status"
            ).fetchall():
                stats[f"patterns_{row['status']}"] = row["count"]
            
            # Pattern counts by type
            for row in conn.execute(
                "SELECT pattern_type, COUNT(*) as count FROM patterns GROUP BY pattern_type"
            ).fetchall():
                stats[f"type_{row['pattern_type']}"] = row["count"]
            
            # Cluster counts
            for row in conn.execute(
                "SELECT status, COUNT(*) as count FROM insight_clusters GROUP BY status"
            ).fetchall():
                stats[f"clusters_{row['status']}"] = row["count"]
            
            # Averages
            avg_row = conn.execute(
                "SELECT AVG(strength) as avg_strength, AVG(confidence) as avg_confidence FROM patterns"
            ).fetchone()
            
            stats["avg_pattern_strength"] = round(avg_row["avg_strength"] or 0, 3)
            stats["avg_pattern_confidence"] = round(avg_row["avg_confidence"] or 0, 3)
            
            return stats
        finally:
            conn.close()
    
    # -------------------------------------------------------------------------
    # FULL SYNTHESIS RUN
    # -------------------------------------------------------------------------
    
    def run_synthesis(
        self,
        provider: Any,
        strategy: ClusterStrategy = ClusterStrategy.AUTO,
        min_cluster_size: int = 3,
        max_clusters: int = 10,
    ) -> SynthResult:
        """
        Run a full synthesis cycle.
        
        1. Create clusters from unprocessed insights
        2. Synthesize patterns from each cluster
        3. Save patterns to database
        4. Update cluster status
        
        Args:
            provider: LLM provider instance
            strategy: Clustering strategy
            min_cluster_size: Minimum insights per cluster
            max_clusters: Maximum clusters to process in this run
        
        Returns:
            SynthResult with summary of what was created
        """
        result = SynthResult(success=True)
        
        # Step 1: Create clusters
        clusters = self.create_clusters(
            strategy=strategy,
            min_cluster_size=min_cluster_size,
            insight_status="raw",
        )
        
        if not clusters:
            logger.info("No clusters created - not enough insights or already processed")
            return result
        
        # Limit clusters
        clusters = clusters[:max_clusters]
        
        # Step 2: Synthesize each cluster
        all_patterns = []
        
        for cluster in clusters:
            logger.info(f"Synthesizing cluster: {cluster.cluster_key} ({cluster.insight_count} insights)")
            
            # Update cluster status
            self._update_cluster_status(cluster.id, "synthesizing")
            
            try:
                patterns = self.synthesize_cluster(cluster, provider)
                
                if patterns:
                    all_patterns.extend(patterns)
                    self._update_cluster_status(cluster.id, "complete")
                    result.clusters_processed += 1
                else:
                    self._update_cluster_status(cluster.id, "failed")
                    result.errors.append(f"No patterns from cluster {cluster.id}")
                    
            except Exception as e:
                self._update_cluster_status(cluster.id, "failed")
                result.errors.append(f"Cluster {cluster.id}: {str(e)}")
        
        # Step 3: Save patterns
        if all_patterns:
            save_result = self.save_patterns_batch(all_patterns)
            result.patterns_created = save_result["saved"]
            result.patterns = all_patterns
        
        logger.info(f"Synthesis complete: {result.patterns_created} patterns from {result.clusters_processed} clusters")
        
        return result
    
    def _update_cluster_status(self, cluster_id: str, status: str):
        """Update a cluster's status."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE insight_clusters SET status = ? WHERE id = ?",
                (status, cluster_id)
            )
            conn.commit()
        finally:
            conn.close()


# =============================================================================
# MODULE-LEVEL CONVENIENCE
# =============================================================================

_engine: Optional[SynthEngine] = None


def init_synth_engine(db_path: Path, insight_store=None, entity_registry=None) -> SynthEngine:
    """Initialize the global Synth Engine instance."""
    global _engine
    _engine = SynthEngine(db_path, insight_store, entity_registry)
    return _engine


def get_synth_engine() -> Optional[SynthEngine]:
    """Get the global Synth Engine instance."""
    return _engine

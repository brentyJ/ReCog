"""
ReCog Core - Correlator v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Tier 2: Pattern detection across multiple insights.
Groups insights by theme, finds recurring patterns, contradictions,
and evolution over time.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime
from collections import defaultdict

from .types import Insight, Pattern, PatternType
from .config import RecogConfig
from .llm import LLMProvider, LLMResponse


logger = logging.getLogger(__name__)


# =============================================================================
# CORRELATION PROMPTS
# =============================================================================

PATTERN_DETECTION_PROMPT = '''You are analysing a cluster of related insights to detect patterns.

{context_section}
## Cluster Information
- Theme cluster: {cluster_themes}
- Insight count: {insight_count}

## Insights in Cluster
{insights_formatted}

## Task
Analyse these insights and determine if they form a meaningful pattern.

Pattern types:
- **recurring**: Same observation appears across multiple sources/times
- **contradiction**: Insights that conflict with each other (may indicate evolution or error)
- **evolution**: A theme or belief that changes over time
- **cluster**: Related insights without clear temporal or causal relationship

For each pattern found (0-3), provide:
1. **summary**: 1-2 sentences describing the pattern
2. **pattern_type**: One of: recurring, contradiction, evolution, cluster
3. **insight_ids**: List of insight IDs that form this pattern
4. **strength**: 0.0-1.0 how strong/clear the pattern is

## Output Format
Return valid JSON only. No markdown, no explanation.

{{
  "patterns": [
    {{
      "summary": "...",
      "pattern_type": "recurring|contradiction|evolution|cluster",
      "insight_ids": ["id1", "id2"],
      "strength": 0.0
    }}
  ],
  "meta": {{
    "cluster_coherence": "high|medium|low",
    "notes": "..."
  }}
}}

If no meaningful pattern exists, return:
{{
  "patterns": [],
  "meta": {{
    "cluster_coherence": "low",
    "notes": "Insights are thematically related but don't form a clear pattern."
  }}
}}'''


CROSS_PATTERN_PROMPT = '''You are looking for connections between an insight and existing patterns.

## Insight
{insight_summary}
Themes: {insight_themes}

## Existing Patterns
{patterns_formatted}

## Task
Does this insight connect to any existing pattern? If so, which one(s) and how?

Return JSON only:
{{
  "connections": [
    {{
      "pattern_id": "...",
      "connection_type": "supports|contradicts|extends",
      "confidence": 0.0
    }}
  ]
}}

If no connection, return {{"connections": []}}'''


SYSTEM_PROMPT = "You are a pattern detection system. Return valid JSON only, no markdown."


# =============================================================================
# CORRELATOR CLASS
# =============================================================================

class Correlator:
    """
    Tier 2 pattern correlation.
    
    Takes insights and finds patterns across them - recurring themes,
    contradictions, evolution over time, and thematic clusters.
    
    Usage:
        correlator = Correlator(llm_provider, config)
        patterns, stats = correlator.correlate(insights)
        
        # Or with adapter:
        patterns, stats = correlator.correlate(insights, adapter)
    """
    
    def __init__(self, llm: LLMProvider, config: RecogConfig = None):
        """
        Initialise the correlator.
        
        Args:
            llm: LLM provider for pattern detection
            config: Processing configuration
        """
        self.llm = llm
        self.config = config or RecogConfig()
    
    def correlate(self,
                  insights: List[Insight],
                  adapter = None,
                  existing_patterns: List[Pattern] = None) -> Tuple[List[Pattern], Dict[str, Any]]:
        """
        Find patterns across insights.
        
        Args:
            insights: Insights to correlate
            adapter: Optional RecogAdapter for context and persistence
            existing_patterns: Optional list of existing patterns to extend
            
        Returns:
            Tuple of (patterns found, processing stats)
        """
        if len(insights) < self.config.correlation_min_cluster:
            logger.info(f"Too few insights ({len(insights)}) for correlation")
            return [], {"skipped": True, "reason": "insufficient_insights"}
        
        # Get context from adapter
        context = None
        if adapter and self.config.include_adapter_context:
            context = adapter.get_context()
        
        existing_patterns = existing_patterns or []
        if adapter:
            existing_patterns = adapter.get_patterns()
        
        all_patterns: List[Pattern] = list(existing_patterns)
        stats = {
            "clusters_analysed": 0,
            "patterns_found": 0,
            "patterns_extended": 0,
            "insights_linked": 0,
            "passes": 0,
            "errors": 0,
        }
        
        # Phase 1: Group insights by theme overlap
        clusters = self._cluster_by_themes(insights)
        logger.info(f"Found {len(clusters)} theme clusters")
        
        # Phase 2: Analyse each cluster for patterns
        for cluster_themes, cluster_insights in clusters.items():
            if len(cluster_insights) < self.config.correlation_min_cluster:
                continue
            
            stats["clusters_analysed"] += 1
            
            try:
                new_patterns = self._analyse_cluster(
                    cluster_themes=cluster_themes,
                    insights=cluster_insights,
                    context=context,
                    existing_patterns=all_patterns,
                )
                
                for pattern in new_patterns:
                    logger.debug(f"Processing pattern: {pattern.summary[:60]}... with {len(pattern.insight_ids)} insights")
                    
                    # Check if extends existing pattern
                    extended = False
                    for existing in all_patterns:
                        if self._patterns_overlap(pattern, existing):
                            logger.debug(f"Merging with existing pattern: {existing.summary[:40]}...")
                            self._merge_patterns(existing, pattern)
                            stats["patterns_extended"] += 1
                            extended = True
                            break
                    
                    if not extended:
                        logger.debug(f"Adding new pattern: {pattern.id[:8]}")
                        all_patterns.append(pattern)
                        stats["patterns_found"] += 1
                    
                    stats["insights_linked"] += len(pattern.insight_ids)
                    
                    # Save to adapter
                    if adapter:
                        adapter.save_pattern(pattern)
                        
            except Exception as e:
                logger.error(f"Error analysing cluster {cluster_themes}: {e}")
                stats["errors"] += 1
        
        stats["passes"] += 1
        
        # Phase 3: Check unclustered insights against existing patterns
        clustered_ids = set()
        for cluster_insights in clusters.values():
            clustered_ids.update(i.id for i in cluster_insights)
        
        unclustered = [i for i in insights if i.id not in clustered_ids]
        
        if unclustered and all_patterns:
            linked = self._link_unclustered(unclustered, all_patterns, context)
            stats["insights_linked"] += linked
        
        # Filter out existing patterns from result (return only new/modified)
        existing_ids = {p.id for p in existing_patterns}
        new_patterns = [p for p in all_patterns if p.id not in existing_ids]
        
        return new_patterns, stats
    
    def _cluster_by_themes(self, insights: List[Insight]) -> Dict[str, List[Insight]]:
        """
        Group insights by theme overlap.
        
        Returns dict of frozenset(themes) -> list of insights sharing those themes.
        """
        # Build theme -> insights mapping
        theme_to_insights: Dict[str, List[Insight]] = defaultdict(list)
        for insight in insights:
            for theme in insight.themes:
                theme_to_insights[theme.lower()].append(insight)
        
        # Find clusters where multiple insights share themes
        clusters: Dict[str, List[Insight]] = {}
        processed_insights: Set[str] = set()
        
        # Sort themes by popularity (most shared first)
        sorted_themes = sorted(
            theme_to_insights.keys(),
            key=lambda t: len(theme_to_insights[t]),
            reverse=True
        )
        
        for theme in sorted_themes:
            theme_insights = theme_to_insights[theme]
            
            # Skip if not enough insights
            if len(theme_insights) < self.config.correlation_min_cluster:
                continue
            
            # Find insights not yet in a cluster
            available = [i for i in theme_insights if i.id not in processed_insights]
            
            if len(available) >= self.config.correlation_min_cluster:
                # Find common themes across these insights
                common_themes = set(available[0].themes)
                for insight in available[1:]:
                    common_themes &= set(insight.themes)
                
                if common_themes:
                    cluster_key = ",".join(sorted(t.lower() for t in common_themes))
                else:
                    cluster_key = theme
                
                clusters[cluster_key] = available
                processed_insights.update(i.id for i in available)
        
        return clusters
    
    def _analyse_cluster(self,
                         cluster_themes: str,
                         insights: List[Insight],
                         context: Optional[str],
                         existing_patterns: List[Pattern]) -> List[Pattern]:
        """Analyse a cluster of insights for patterns."""
        # Format insights for prompt
        insights_formatted = self._format_insights_for_prompt(insights)
        
        # Context section
        context_section = ""
        if context:
            context_section = f"## Context\n{context}\n\n"
        
        prompt = PATTERN_DETECTION_PROMPT.format(
            context_section=context_section,
            cluster_themes=cluster_themes,
            insight_count=len(insights),
            insights_formatted=insights_formatted,
        )
        
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=self.config.correlation_temperature,
            max_tokens=self.config.correlation_max_tokens,
        )
        
        if not response.success:
            logger.error(f"LLM error in cluster analysis: {response.error}")
            return []
        
        return self._parse_pattern_response(response.content, insights)
    
    def _format_insights_for_prompt(self, insights: List[Insight]) -> str:
        """Format insights for inclusion in prompt."""
        parts = []
        for i, insight in enumerate(insights, 1):
            parts.append(f"""
### Insight {i} (ID: {insight.id[:8]})
**Summary:** {insight.summary}
**Themes:** {', '.join(insight.themes)}
**Significance:** {insight.significance:.2f}
**Sources:** {len(insight.source_ids)} document(s)
""")
        return "\n".join(parts)
    
    def _parse_pattern_response(self, 
                                response_text: str,
                                cluster_insights: List[Insight]) -> List[Pattern]:
        """Parse LLM response into Pattern objects."""
        # Clean markdown
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines)
        
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from LLM: {text[:200]}... Error: {e}")
            return []
        
        # Map short IDs back to full IDs
        id_map = {i.id[:8]: i.id for i in cluster_insights}
        
        patterns = []
        for item in data.get("patterns", []):
            try:
                # Resolve insight IDs
                insight_ids = []
                for ref in item.get("insight_ids", []):
                    # Handle both full and short IDs
                    if ref in id_map:
                        insight_ids.append(id_map[ref])
                    elif any(ref == i.id for i in cluster_insights):
                        insight_ids.append(ref)
                    else:
                        # Try partial match
                        for insight in cluster_insights:
                            if insight.id.startswith(ref) or ref.startswith(insight.id[:8]):
                                insight_ids.append(insight.id)
                                break
                
                if len(insight_ids) < 2:
                    logger.warning(f"Pattern has too few valid insight IDs: {item}")
                    continue
                
                pattern_type_str = item.get("pattern_type", "cluster")
                try:
                    pattern_type = PatternType(pattern_type_str)
                except ValueError:
                    pattern_type = PatternType.CLUSTER
                
                pattern = Pattern.create(
                    summary=item.get("summary", ""),
                    pattern_type=pattern_type,
                    insight_ids=insight_ids,
                    strength=float(item.get("strength", 0.5)),
                    metadata={
                        "detection_model": self.llm.model,
                    }
                )
                patterns.append(pattern)
                
            except Exception as e:
                logger.warning(f"Failed to parse pattern: {e}")
                continue
        
        return patterns
    
    def _patterns_overlap(self, a: Pattern, b: Pattern) -> bool:
        """Check if two patterns share enough insights to merge."""
        shared = set(a.insight_ids) & set(b.insight_ids)
        total = set(a.insight_ids) | set(b.insight_ids)
        overlap = len(shared) / len(total) if total else 0
        return overlap >= 0.5  # 50% overlap threshold
    
    def _merge_patterns(self, target: Pattern, source: Pattern) -> None:
        """Merge source pattern into target."""
        # Combine insight IDs
        target.insight_ids = list(set(target.insight_ids + source.insight_ids))
        
        # Update strength (boost for corroboration)
        target.strength = min(1.0, (target.strength + source.strength) / 2 + 0.1)
        
        # Keep more specific summary if available
        if len(source.summary) > len(target.summary):
            target.summary = source.summary
    
    def _link_unclustered(self,
                          insights: List[Insight],
                          patterns: List[Pattern],
                          context: Optional[str]) -> int:
        """
        Try to link unclustered insights to existing patterns.
        
        Returns number of insights linked.
        """
        linked = 0
        
        for insight in insights:
            # Simple theme-based matching (no LLM call to save cost)
            insight_themes = set(t.lower() for t in insight.themes)
            
            best_pattern = None
            best_overlap = 0
            
            for pattern in patterns:
                # Get themes from pattern's insights
                pattern_themes: Set[str] = set()
                # We'd need to look up insights, but for efficiency
                # just check summary for theme words
                summary_words = set(pattern.summary.lower().split())
                overlap = len(insight_themes & summary_words)
                
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_pattern = pattern
            
            if best_pattern and best_overlap >= 1:
                if insight.id not in best_pattern.insight_ids:
                    best_pattern.insight_ids.append(insight.id)
                    linked += 1
        
        return linked


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def find_patterns(insights: List[Insight],
                  llm: LLMProvider,
                  config: RecogConfig = None) -> List[Pattern]:
    """
    Convenience function to find patterns in insights.
    
    Args:
        insights: List of insights to analyse
        llm: LLM provider
        config: Optional configuration
        
    Returns:
        List of detected patterns
    """
    correlator = Correlator(llm, config)
    patterns, _ = correlator.correlate(insights)
    return patterns


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "Correlator",
    "find_patterns",
]

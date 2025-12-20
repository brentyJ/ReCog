"""
ReCog Core - Synthesizer v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Tier 3: Deep synthesis from patterns.
Produces high-level conclusions: personality traits, belief systems,
behavioural tendencies, core themes.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .types import Pattern, Synthesis, SynthesisType, Insight
from .config import RecogConfig
from .llm import LLMProvider, LLMResponse


logger = logging.getLogger(__name__)


# =============================================================================
# SYNTHESIS PROMPTS
# =============================================================================

SYNTHESIS_PROMPT = '''You are synthesising patterns into high-level conclusions about a person or corpus.

{context_section}
## Patterns to Synthesise
{patterns_formatted}

## Supporting Insights
{insights_formatted}

## Task
Based on these patterns, generate 1-3 high-level syntheses. A synthesis is a significant conclusion about:

Synthesis types:
- **trait**: A personality characteristic (e.g., "tendency toward perfectionism")
- **belief**: A core belief or value (e.g., "believes preparation prevents failure")
- **tendency**: A behavioural pattern (e.g., "avoids conflict through over-accommodation")
- **theme**: A recurring life theme (e.g., "ongoing tension between independence and connection")

For each synthesis:
1. **summary**: 2-4 sentences describing the synthesis
2. **synthesis_type**: One of: trait, belief, tendency, theme
3. **pattern_ids**: Patterns that support this synthesis
4. **significance**: 0.0-1.0 how central this is to the corpus/person
5. **confidence**: 0.0-1.0 how certain the synthesis is

Quality thresholds:
- Only produce syntheses with significance >= {significance_threshold}
- Require at least {min_patterns} supporting patterns
- Avoid speculation beyond what patterns clearly support

## Output Format
Return valid JSON only. No markdown.

{{
  "syntheses": [
    {{
      "summary": "...",
      "synthesis_type": "trait|belief|tendency|theme",
      "pattern_ids": ["id1", "id2"],
      "significance": 0.0,
      "confidence": 0.0
    }}
  ],
  "meta": {{
    "corpus_coherence": "high|medium|low",
    "notes": "..."
  }}
}}

If no significant synthesis is supported, return:
{{
  "syntheses": [],
  "meta": {{
    "corpus_coherence": "low",
    "notes": "Patterns don't yet support high-level synthesis."
  }}
}}'''


SYSTEM_PROMPT = "You are a synthesis engine producing high-level conclusions. Return valid JSON only."


# =============================================================================
# SYNTHESIZER CLASS
# =============================================================================

class Synthesizer:
    """
    Tier 3 pattern synthesis.
    
    Takes patterns (from Tier 2) and produces high-level syntheses:
    personality traits, core beliefs, behavioural tendencies, life themes.
    
    Usage:
        synthesizer = Synthesizer(llm_provider, config)
        syntheses, stats = synthesizer.synthesise(patterns, insights)
    """
    
    def __init__(self, llm: LLMProvider, config: RecogConfig = None):
        """
        Initialise the synthesizer.
        
        Args:
            llm: LLM provider for synthesis
            config: Processing configuration
        """
        self.llm = llm
        self.config = config or RecogConfig()
    
    def synthesise(self,
                   patterns: List[Pattern],
                   insights: List[Insight] = None,
                   adapter = None,
                   existing_syntheses: List[Synthesis] = None) -> Tuple[List[Synthesis], Dict[str, Any]]:
        """
        Generate syntheses from patterns.
        
        Args:
            patterns: Patterns to synthesise (from Tier 2)
            insights: Original insights (for context)
            adapter: Optional RecogAdapter for persistence
            existing_syntheses: Optional existing syntheses to extend
            
        Returns:
            Tuple of (syntheses, processing stats)
        """
        if len(patterns) < self.config.synthesis_min_patterns:
            logger.info(f"Too few patterns ({len(patterns)}) for full synthesis, generating emerging themes")
            # Generate emerging themes instead of skipping entirely
            return self._generate_emerging_themes(patterns, insights, adapter), {
                "mode": "emerging",
                "reason": "limited_patterns"
            }
        
        # Get context
        context = None
        if adapter and self.config.include_adapter_context:
            context = adapter.get_context()
        
        existing_syntheses = existing_syntheses or []
        if adapter:
            existing_syntheses = adapter.get_syntheses()
        
        insights = insights or []
        
        stats = {
            "patterns_processed": len(patterns),
            "syntheses_created": 0,
            "syntheses_refined": 0,
            "errors": 0,
        }
        
        # Generate new syntheses
        new_syntheses = self._generate_syntheses(patterns, insights, context)
        
        # Merge with existing
        all_syntheses = list(existing_syntheses)
        
        for synthesis in new_syntheses:
            # Check if refines existing
            refined = False
            for existing in all_syntheses:
                if self._syntheses_related(synthesis, existing):
                    self._merge_syntheses(existing, synthesis)
                    stats["syntheses_refined"] += 1
                    refined = True
                    break
            
            if not refined:
                all_syntheses.append(synthesis)
                stats["syntheses_created"] += 1
        
        # Save to adapter
        if adapter:
            for synthesis in new_syntheses:
                adapter.save_synthesis(synthesis)
        
        # Return only new/modified
        existing_ids = {s.id for s in existing_syntheses}
        result = [s for s in all_syntheses if s.id not in existing_ids]
        
        return result, stats
    
    def _generate_syntheses(self,
                            patterns: List[Pattern],
                            insights: List[Insight],
                            context: Optional[str]) -> List[Synthesis]:
        """Generate syntheses from patterns."""
        # Format patterns
        patterns_formatted = self._format_patterns(patterns)
        
        # Format supporting insights (limited to most significant)
        insight_map = {i.id: i for i in insights}
        relevant_insights = []
        for pattern in patterns:
            for insight_id in pattern.insight_ids:
                if insight_id in insight_map:
                    relevant_insights.append(insight_map[insight_id])
        
        # Dedupe and sort by significance
        seen_ids = set()
        unique_insights = []
        for insight in relevant_insights:
            if insight.id not in seen_ids:
                seen_ids.add(insight.id)
                unique_insights.append(insight)
        unique_insights.sort(key=lambda i: i.significance, reverse=True)
        insights_formatted = self._format_insights(unique_insights[:10])
        
        # Context section
        context_section = ""
        if context:
            context_section = f"## Context\n{context}\n\n"
        
        prompt = SYNTHESIS_PROMPT.format(
            context_section=context_section,
            patterns_formatted=patterns_formatted,
            insights_formatted=insights_formatted,
            significance_threshold=self.config.synthesis_significance_threshold,
            min_patterns=self.config.synthesis_min_patterns,
        )
        
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=self.config.synthesis_temperature,
            max_tokens=self.config.synthesis_max_tokens,
        )
        
        if not response.success:
            logger.error(f"LLM error in synthesis: {response.error}")
            return []
        
        return self._parse_synthesis_response(response.content, patterns)
    
    def _format_patterns(self, patterns: List[Pattern]) -> str:
        """Format patterns for prompt."""
        parts = []
        for i, pattern in enumerate(patterns, 1):
            parts.append(f"""
### Pattern {i} (ID: {pattern.id[:8]})
**Type:** {pattern.pattern_type.value}
**Summary:** {pattern.summary}
**Strength:** {pattern.strength:.2f}
**Supporting insights:** {len(pattern.insight_ids)}
""")
        return "\n".join(parts)
    
    def _format_insights(self, insights: List[Insight]) -> str:
        """Format insights for prompt."""
        if not insights:
            return "No supporting insights available."
        
        parts = []
        for insight in insights:
            parts.append(f"- {insight.summary} (themes: {', '.join(insight.themes[:3])})")
        return "\n".join(parts)
    
    def _parse_synthesis_response(self,
                                   response_text: str,
                                   patterns: List[Pattern]) -> List[Synthesis]:
        """Parse LLM response into Synthesis objects."""
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
        
        # Map short IDs to full IDs
        id_map = {p.id[:8]: p.id for p in patterns}
        
        syntheses = []
        for item in data.get("syntheses", []):
            try:
                # Resolve pattern IDs
                pattern_ids = []
                for ref in item.get("pattern_ids", []):
                    if ref in id_map:
                        pattern_ids.append(id_map[ref])
                    elif any(ref == p.id for p in patterns):
                        pattern_ids.append(ref)
                
                if len(pattern_ids) < self.config.synthesis_min_patterns:
                    logger.warning(f"Synthesis has too few pattern refs: {item}")
                    continue
                
                synthesis_type_str = item.get("synthesis_type", "theme")
                try:
                    synthesis_type = SynthesisType(synthesis_type_str)
                except ValueError:
                    synthesis_type = SynthesisType.THEME
                
                significance = float(item.get("significance", 0.5))
                if significance < self.config.synthesis_significance_threshold:
                    logger.debug(f"Synthesis below threshold: {significance}")
                    continue
                
                synthesis = Synthesis.create(
                    summary=item.get("summary", ""),
                    synthesis_type=synthesis_type,
                    pattern_ids=pattern_ids,
                    significance=significance,
                    confidence=float(item.get("confidence", 0.5)),
                    metadata={
                        "synthesis_model": self.llm.model,
                    }
                )
                syntheses.append(synthesis)
                
            except Exception as e:
                logger.warning(f"Failed to parse synthesis: {e}")
                continue
        
        return syntheses
    
    def _syntheses_related(self, a: Synthesis, b: Synthesis) -> bool:
        """Check if two syntheses are related enough to merge."""
        # Same type and shared patterns
        if a.synthesis_type != b.synthesis_type:
            return False
        
        shared = set(a.pattern_ids) & set(b.pattern_ids)
        return len(shared) >= 1
    
    def _merge_syntheses(self, target: Synthesis, source: Synthesis) -> None:
        """Merge source synthesis into target."""
        # Combine pattern IDs
        target.pattern_ids = list(set(target.pattern_ids + source.pattern_ids))
        
        # Boost significance and confidence (corroboration)
        target.significance = min(1.0, (target.significance + source.significance) / 2 + 0.05)
        target.confidence = min(1.0, (target.confidence + source.confidence) / 2 + 0.05)
        
        # Keep longer/more detailed summary
        if len(source.summary) > len(target.summary):
            target.summary = source.summary
    
    def _generate_emerging_themes(self,
                                   patterns: List[Pattern],
                                   insights: List[Insight],
                                   adapter = None) -> List[Synthesis]:
        """
        Generate emerging themes when there aren't enough patterns for full synthesis.
        
        This provides users with SOMETHING useful even when data is limited.
        Lower confidence to indicate these are preliminary observations.
        """
        syntheses = []
        
        # If we have patterns, create emerging themes from them
        for pattern in patterns:
            synthesis = Synthesis.create(
                summary=f"Emerging observation: {pattern.summary}",
                synthesis_type=SynthesisType.THEME,
                pattern_ids=[pattern.id],
                significance=pattern.strength * 0.7,  # Reduced significance
                confidence=0.4,  # Low confidence - this is preliminary
                metadata={
                    "emerging": True,
                    "pattern_type": pattern.pattern_type.value,
                    "source": "limited_synthesis",
                }
            )
            syntheses.append(synthesis)
            
            if adapter:
                adapter.save_synthesis(synthesis)
        
        # If we have insights but no patterns, surface top insights as emerging themes
        if not patterns and insights:
            top_insights = sorted(insights, key=lambda i: i.significance, reverse=True)[:3]
            for insight in top_insights:
                synthesis = Synthesis.create(
                    summary=f"Early signal: {insight.summary}",
                    synthesis_type=SynthesisType.THEME,
                    pattern_ids=[],
                    significance=insight.significance * 0.5,
                    confidence=0.3,
                    metadata={
                        "emerging": True,
                        "source": "top_insight",
                        "themes": insight.themes[:3],
                    }
                )
                syntheses.append(synthesis)
                
                if adapter:
                    adapter.save_synthesis(synthesis)
        
        logger.info(f"Generated {len(syntheses)} emerging themes from limited data")
        return syntheses


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def synthesise_patterns(patterns: List[Pattern],
                        llm: LLMProvider,
                        insights: List[Insight] = None,
                        config: RecogConfig = None) -> List[Synthesis]:
    """
    Convenience function to synthesise patterns.
    
    Args:
        patterns: Patterns to synthesise
        llm: LLM provider
        insights: Optional supporting insights
        config: Optional configuration
        
    Returns:
        List of syntheses
    """
    synthesizer = Synthesizer(llm, config)
    syntheses, _ = synthesizer.synthesise(patterns, insights)
    return syntheses


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "Synthesizer",
    "synthesise_patterns",
]

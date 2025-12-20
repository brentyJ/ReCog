"""
ReCog Core - Extractor v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Tier 1: Insight extraction from documents using LLM.
Takes documents (with Tier 0 signals) and produces Insights.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .types import Document, Insight
from .signal import SignalProcessor
from .config import RecogConfig
from .llm import LLMProvider, LLMResponse


logger = logging.getLogger(__name__)


# =============================================================================
# EXTRACTION PROMPT
# =============================================================================

EXTRACTION_PROMPT = '''You are analysing text to extract meaningful insights.

{context_section}
## Document Information
- Source type: {source_type}
- Source reference: {source_ref}
- Word count: {word_count}

## Pre-Analysis Signals
{signals_summary}

{themes_section}
## Content
{content}

## Task
Extract 0-{max_insights} insights from this content. An insight is a discrete observation worth preserving — a pattern, realisation, tendency, belief, or significant observation.

NOT every piece of content yields insights. Mundane, logistical, or surface-level content should yield 0 insights.

For each insight, provide:
1. **summary**: 1-3 sentences capturing the insight (distillation, not a quote)
2. **themes**: 2-5 categorical tags (lowercase, hyphenated)
3. **significance**: 0.0-1.0 importance score based on:
   - Depth of observation (weight: 0.4)
   - Potential for pattern connection (weight: 0.3)
   - Clarity and specificity (weight: 0.3)
4. **confidence**: 0.0-1.0 how certain you are this is a valid insight
5. **excerpt**: The most relevant 1-2 sentences from the source (direct quote)

## Output Format
Return valid JSON only. No markdown, no explanation, no backticks.

{{
  "insights": [
    {{
      "summary": "...",
      "themes": ["...", "..."],
      "significance": 0.0,
      "confidence": 0.0,
      "excerpt": "..."
    }}
  ],
  "meta": {{
    "content_quality": "high|medium|low|empty",
    "notes": "..."
  }}
}}

If no insights are extractable, return:
{{
  "insights": [],
  "meta": {{
    "content_quality": "low",
    "notes": "Content is logistical/surface-level, no insights detected."
  }}
}}'''

SYSTEM_PROMPT = "You are an insight extraction system. Return valid JSON only, no markdown formatting."


# =============================================================================
# EXTRACTOR CLASS
# =============================================================================

class Extractor:
    """
    Tier 1 insight extraction.
    
    Takes documents (with Tier 0 signals populated) and uses an LLM
    to extract meaningful insights.
    
    Usage:
        extractor = Extractor(llm_provider, config)
        insights = extractor.extract(document)
        
        # Or batch:
        all_insights = extractor.extract_batch(documents, adapter)
    """
    
    def __init__(self, llm: LLMProvider, config: RecogConfig = None):
        """
        Initialise the extractor.
        
        Args:
            llm: LLM provider for generation
            config: Processing configuration (uses defaults if not provided)
        """
        self.llm = llm
        self.config = config or RecogConfig()
        self.signal_processor = SignalProcessor()
    
    def extract(self, 
                document: Document,
                context: Optional[str] = None,
                existing_themes: Optional[List[str]] = None,
                existing_insights: Optional[List[Insight]] = None) -> List[Insight]:
        """
        Extract insights from a single document.
        
        Args:
            document: Document to process (signals should be populated)
            context: Optional domain context to include in prompt
            existing_themes: Optional list of known themes for consistency
            existing_insights: Optional list to check for duplicates
            
        Returns:
            List of extracted Insight objects
        """
        # Ensure signals are populated
        if document.signals is None and self.config.signal_enabled:
            self.signal_processor.process(document)
        
        # Check minimum content
        word_count = document.signals.get("word_count", 0) if document.signals else len(document.content.split())
        if word_count < self.config.min_content_words:
            logger.debug(f"Document {document.id[:8]} too short ({word_count} words), skipping")
            return []
        
        # Build prompt
        prompt = self._build_prompt(document, context, existing_themes)
        
        # Call LLM
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=self.config.extraction_temperature,
            max_tokens=self.config.extraction_max_tokens,
        )
        
        if not response.success:
            logger.error(f"LLM error for document {document.id[:8]}: {response.error}")
            return []
        
        # Parse response
        insights = self._parse_response(response.content, document)
        
        # Filter by thresholds
        insights = self._filter_insights(insights)
        
        # Deduplicate against existing
        if existing_insights:
            insights = self._deduplicate(insights, existing_insights)
        
        logger.info(f"Extracted {len(insights)} insights from document {document.id[:8]}")
        return insights
    
    def extract_batch(self,
                      documents: List[Document],
                      adapter = None) -> Tuple[List[Insight], Dict[str, Any]]:
        """
        Extract insights from multiple documents.
        
        Args:
            documents: Documents to process
            adapter: Optional RecogAdapter for context and persistence
            
        Returns:
            Tuple of (all insights, processing stats)
        """
        # Get context from adapter
        context = None
        existing_themes = []
        if adapter:
            if self.config.include_adapter_context:
                context = adapter.get_context()
            if self.config.include_existing_themes:
                existing_themes = adapter.get_existing_themes()
        
        all_insights: List[Insight] = []
        stats = {
            "documents_processed": 0,
            "documents_skipped": 0,
            "insights_extracted": 0,
            "insights_merged": 0,
            "errors": 0,
        }
        
        for doc in documents:
            try:
                insights = self.extract(
                    document=doc,
                    context=context,
                    existing_themes=existing_themes,
                    existing_insights=all_insights,
                )
                
                # Track stats
                stats["documents_processed"] += 1
                
                for insight in insights:
                    # Check if merged with existing
                    merged = False
                    for existing in all_insights:
                        if self._is_similar(insight, existing):
                            existing.merge_with(insight)
                            stats["insights_merged"] += 1
                            merged = True
                            break
                    
                    if not merged:
                        all_insights.append(insight)
                        stats["insights_extracted"] += 1
                        
                        # Update themes for consistency
                        existing_themes.extend(insight.themes)
                
                # Save to adapter if provided
                if adapter:
                    for insight in insights:
                        adapter.save_insight(insight)
                        
            except Exception as e:
                logger.error(f"Error processing document {doc.id[:8]}: {e}")
                stats["errors"] += 1
        
        return all_insights, stats
    
    def _build_prompt(self,
                      document: Document,
                      context: Optional[str],
                      existing_themes: Optional[List[str]]) -> str:
        """Build the extraction prompt."""
        # Truncate content if needed
        content = document.content
        if len(content) > self.config.max_content_chars:
            content = content[:self.config.max_content_chars] + "\n\n[... content truncated ...]"
        
        # Context section
        context_section = ""
        if context:
            context_section = f"## Context\n{context}\n\n"
        
        # Themes section
        themes_section = ""
        if existing_themes:
            themes_list = ", ".join(sorted(set(existing_themes))[:20])
            themes_section = f"## Known Themes (use when applicable)\n{themes_list}\n\n"
        
        # Signals summary
        signals_summary = "No signals available."
        if document.signals:
            signals_summary = self.signal_processor.summarise_for_prompt(document.signals)
        
        # Word count
        word_count = document.signals.get("word_count", len(content.split())) if document.signals else len(content.split())
        
        return EXTRACTION_PROMPT.format(
            context_section=context_section,
            source_type=document.source_type,
            source_ref=document.source_ref,
            word_count=word_count,
            signals_summary=signals_summary,
            themes_section=themes_section,
            content=content,
            max_insights=self.config.max_insights_per_document,
        )
    
    def _parse_response(self, response_text: str, document: Document) -> List[Insight]:
        """Parse LLM response into Insight objects."""
        # Clean up markdown if present
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
        
        insights = []
        for item in data.get("insights", []):
            try:
                insight = Insight.create(
                    summary=item.get("summary", ""),
                    themes=item.get("themes", []),
                    significance=float(item.get("significance", 0.5)),
                    confidence=float(item.get("confidence", 0.5)),
                    source_ids=[document.id],
                    excerpts=[item.get("excerpt", "")] if item.get("excerpt") else [],
                    metadata={
                        "source_type": document.source_type,
                        "source_ref": document.source_ref,
                        "extraction_model": self.llm.model,
                    }
                )
                insights.append(insight)
            except Exception as e:
                logger.warning(f"Failed to parse insight: {e}")
                continue
        
        return insights
    
    def _filter_insights(self, insights: List[Insight]) -> List[Insight]:
        """Filter insights by quality thresholds."""
        filtered = []
        for insight in insights:
            if insight.confidence < self.config.min_confidence:
                logger.debug(f"Insight rejected: confidence {insight.confidence:.2f} < {self.config.min_confidence}")
                continue
            if insight.significance < self.config.min_significance:
                logger.debug(f"Insight rejected: significance {insight.significance:.2f} < {self.config.min_significance}")
                continue
            if not insight.summary.strip():
                logger.debug("Insight rejected: empty summary")
                continue
            filtered.append(insight)
        return filtered
    
    def _deduplicate(self, 
                     new_insights: List[Insight],
                     existing_insights: List[Insight]) -> List[Insight]:
        """Remove or merge duplicates."""
        unique = []
        for new in new_insights:
            is_duplicate = False
            for existing in existing_insights:
                if self._is_similar(new, existing):
                    # Merge into existing
                    existing.merge_with(new)
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(new)
        return unique
    
    def _is_similar(self, a: Insight, b: Insight) -> bool:
        """Check if two insights are similar enough to merge."""
        # Theme overlap (Jaccard similarity)
        themes_a = set(t.lower() for t in a.themes)
        themes_b = set(t.lower() for t in b.themes)
        
        if themes_a and themes_b:
            intersection = len(themes_a & themes_b)
            union = len(themes_a | themes_b)
            theme_similarity = intersection / union if union > 0 else 0
        else:
            theme_similarity = 0
        
        # Word overlap in summary
        words_a = set(a.summary.lower().split())
        words_b = set(b.summary.lower().split())
        
        if words_a and words_b:
            intersection = len(words_a & words_b)
            union = len(words_a | words_b)
            word_similarity = intersection / union if union > 0 else 0
        else:
            word_similarity = 0
        
        # Combined score (theme-weighted)
        score = (theme_similarity * 0.6) + (word_similarity * 0.4)
        
        return score >= self.config.similarity_threshold


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def extract_from_text(text: str,
                      llm: LLMProvider,
                      source_type: str = "text",
                      source_ref: str = "inline",
                      config: RecogConfig = None) -> List[Insight]:
    """
    Convenience function to extract insights from raw text.
    
    Args:
        text: Raw text to analyse
        llm: LLM provider
        source_type: Type of source
        source_ref: Source reference
        config: Optional configuration
        
    Returns:
        List of extracted insights
    """
    # Create document
    doc = Document.create(
        content=text,
        source_type=source_type,
        source_ref=source_ref,
    )
    
    # Process signals
    processor = SignalProcessor()
    processor.process(doc)
    
    # Extract
    extractor = Extractor(llm, config)
    return extractor.extract(doc)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "Extractor",
    "extract_from_text",
    "EXTRACTION_PROMPT",
]

"""
ReCog Engine - Insight Extraction Processor v0.1

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

LLM-based insight extraction from processed content.
Handles extraction prompts, similarity detection, and deduplication.

This is Tier 1 processing - requires LLM API calls.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from uuid import uuid4

from .tier0 import preprocess_text, summarise_for_prompt

logger = logging.getLogger(__name__)


# =============================================================================
# EXTRACTION PROMPT TEMPLATE
# =============================================================================

INSIGHT_EXTRACTION_PROMPT = """You are analysing content to extract meaningful insights for a text analysis system.

## Context
Source type: {source_type}
Description: {source_description}
Word count: {word_count}

## Speaker Attribution (if applicable)
{speaker_attribution}

## Pre-Annotation Signals
{pre_annotation_summary}

## Additional Context
{additional_context}

## Content to Analyse
{content}

## Your Task
Extract 0-5 insights from this content. An insight is a distilled observation worth preserving — a pattern, realisation, relationship, key fact, or important observation.

NOT every piece of content yields insights. Mundane content, logistics, or surface-level material should yield 0 insights.

{attribution_warning}

For each insight, provide:
1. **summary**: 1-3 sentences capturing the insight (not a quote — a distillation)
2. **themes**: 2-5 theme tags (lowercase, hyphenated)
3. **emotional_tags**: 0-3 emotional tags from: anger, fear, sadness, shame, disgust, joy, pride, love, gratitude, hope, confusion, loneliness, nostalgia, ambivalence
4. **patterns**: 0-3 behavioural/cognitive patterns identified
5. **significance**: 0.0-1.0 score based on:
   - Emotional intensity (weight: 0.3)
   - Theme recurrence potential (weight: 0.3)
   - Insight depth (weight: 0.4)
6. **confidence**: 0.0-1.0 how certain you are this is a valid insight
7. **excerpt**: The most relevant 1-2 sentences as supporting evidence
8. **insight_type**: What kind of insight? One of: observation, pattern, relationship, fact, opinion, question, realisation

## Output Format
Return valid JSON only. No markdown, no explanation, no backticks.

{{
  "insights": [
    {{
      "summary": "...",
      "themes": ["...", "..."],
      "emotional_tags": ["..."],
      "patterns": ["..."],
      "significance": 0.0,
      "confidence": 0.0,
      "excerpt": "...",
      "insight_type": "..."
    }}
  ],
  "meta": {{
    "content_quality": "high|medium|low|empty",
    "suggested_reprocess": false,
    "notes": "..."
  }}
}}

If no insights are extractable, return:
{{
  "insights": [],
  "meta": {{
    "content_quality": "low",
    "suggested_reprocess": false,
    "notes": "Content is logistical/surface-level, no insights detected."
  }}
}}
"""

# Speaker attribution templates
SPEAKER_ATTRIBUTION_CHAT = """The content contains messages from multiple speakers:
- <USER_MESSAGE> tags contain what the primary user said
- <ASSISTANT_MESSAGE> tags contain what an AI assistant said

Focus on extracting insights from the USER's perspective unless otherwise specified."""

SPEAKER_ATTRIBUTION_NONE = "Single speaker or undifferentiated content."

ATTRIBUTION_WARNING_CHAT = """**IMPORTANT:** Only extract insights based on the USER's content (inside <USER_MESSAGE> tags). 
Do not attribute the assistant's words or ideas to the user."""

ATTRIBUTION_WARNING_NONE = ""


# =============================================================================
# DATA TYPES
# =============================================================================

@dataclass
class ExtractedInsight:
    """An insight extracted from content."""
    id: str
    summary: str
    themes: List[str]
    emotional_tags: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    significance: float = 0.5
    confidence: float = 0.5
    excerpt: str = ""
    insight_type: str = "observation"
    source_type: str = ""
    source_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "summary": self.summary,
            "themes": self.themes,
            "emotional_tags": self.emotional_tags,
            "patterns": self.patterns,
            "significance": self.significance,
            "confidence": self.confidence,
            "excerpt": self.excerpt,
            "insight_type": self.insight_type,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ExtractedInsight":
        return cls(
            id=data.get("id", str(uuid4())),
            summary=data.get("summary", ""),
            themes=data.get("themes", []),
            emotional_tags=data.get("emotional_tags", []),
            patterns=data.get("patterns", []),
            significance=data.get("significance", 0.5),
            confidence=data.get("confidence", 0.5),
            excerpt=data.get("excerpt", ""),
            insight_type=data.get("insight_type", "observation"),
            source_type=data.get("source_type", ""),
            source_id=data.get("source_id", ""),
            created_at=data.get("created_at", datetime.utcnow().isoformat() + "Z"),
        )


@dataclass
class ExtractionResult:
    """Result of insight extraction."""
    success: bool
    insights: List[ExtractedInsight] = field(default_factory=list)
    content_quality: str = "low"
    suggested_reprocess: bool = False
    notes: str = ""
    error: str = ""
    tokens_used: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "insights": [i.to_dict() for i in self.insights],
            "content_quality": self.content_quality,
            "suggested_reprocess": self.suggested_reprocess,
            "notes": self.notes,
            "error": self.error,
            "tokens_used": self.tokens_used,
        }


# =============================================================================
# SIMILARITY DETECTION
# =============================================================================

SIMILARITY_THRESHOLD = 0.7


def calculate_similarity(
    candidate_summary: str,
    candidate_themes: List[str],
    existing_summary: str,
    existing_themes: List[str],
) -> float:
    """
    Calculate similarity between two insights using Jaccard + keyword overlap.
    
    Args:
        candidate_summary: Summary of new insight
        candidate_themes: Themes of new insight
        existing_summary: Summary of existing insight
        existing_themes: Themes of existing insight
        
    Returns:
        Similarity score 0.0 - 1.0
    """
    candidate_themes_set = set(t.lower() for t in candidate_themes)
    existing_themes_set = set(t.lower() for t in existing_themes)
    
    # Jaccard similarity on themes
    if candidate_themes_set or existing_themes_set:
        theme_intersection = len(candidate_themes_set & existing_themes_set)
        theme_union = len(candidate_themes_set | existing_themes_set)
        jaccard = theme_intersection / theme_union if theme_union > 0 else 0.0
    else:
        jaccard = 0.0
    
    # Keyword overlap in summary
    candidate_words = set(candidate_summary.lower().split())
    existing_words = set(existing_summary.lower().split())
    
    if candidate_words or existing_words:
        word_intersection = len(candidate_words & existing_words)
        word_union = len(candidate_words | existing_words)
        word_overlap = word_intersection / word_union if word_union > 0 else 0.0
    else:
        word_overlap = 0.0
    
    # Combined score (themes weighted higher)
    score = (jaccard * 0.6) + (word_overlap * 0.4)
    
    return score


def find_similar_insight(
    candidate: ExtractedInsight,
    existing_insights: List[ExtractedInsight],
    threshold: float = SIMILARITY_THRESHOLD,
) -> Optional[Tuple[ExtractedInsight, float]]:
    """
    Find an existing insight similar to the candidate.
    
    Args:
        candidate: New insight to check
        existing_insights: List of existing insights to compare against
        threshold: Minimum similarity score to consider a match
        
    Returns:
        Tuple of (matching_insight, score) if found, None otherwise
    """
    best_match = None
    best_score = 0.0
    
    for existing in existing_insights:
        score = calculate_similarity(
            candidate.summary,
            candidate.themes,
            existing.summary,
            existing.themes,
        )
        
        if score > best_score:
            best_score = score
            best_match = existing
    
    if best_score >= threshold:
        logger.debug(f"Found similar insight with score {best_score:.2f}")
        return (best_match, best_score)
    
    return None


def merge_insights(original: ExtractedInsight, new_data: ExtractedInsight) -> ExtractedInsight:
    """
    Merge a new insight into an existing one.
    
    Updates the original with combined themes, patterns, and adjusted significance.
    
    Args:
        original: The existing insight to update
        new_data: New insight data to merge
        
    Returns:
        Updated insight
    """
    # Merge themes
    merged_themes = list(set(original.themes + new_data.themes))
    
    # Merge emotional tags
    merged_emotions = list(set(original.emotional_tags + new_data.emotional_tags))
    
    # Merge patterns
    merged_patterns = list(set(original.patterns + new_data.patterns))
    
    # Average significance with slight boost for reinforcement
    new_significance = min(1.0, (original.significance + new_data.significance) / 2 + 0.05)
    
    # Update confidence (higher if reinforced)
    new_confidence = min(1.0, (original.confidence + new_data.confidence) / 2 + 0.1)
    
    return ExtractedInsight(
        id=original.id,
        summary=original.summary,  # Keep original summary
        themes=merged_themes,
        emotional_tags=merged_emotions,
        patterns=merged_patterns,
        significance=new_significance,
        confidence=new_confidence,
        excerpt=original.excerpt or new_data.excerpt,
        insight_type=original.insight_type,
        source_type=original.source_type,
        source_id=original.source_id,
        created_at=original.created_at,
    )


# =============================================================================
# SURFACING LOGIC
# =============================================================================

SURFACING_SIGNIFICANCE_THRESHOLD = 0.4
SURFACING_LOW_SIG_THRESHOLD = 0.3
SURFACING_PASS_THRESHOLD = 2
SURFACING_SOURCE_THRESHOLD = 3


def should_surface(insight: ExtractedInsight, pass_count: int = 1, source_count: int = 1) -> bool:
    """
    Determine if an insight should be surfaced (promoted for visibility).
    
    Surfacing criteria:
    - significance >= 0.4 on first pass (immediate surface for high-quality)
    - OR (significance >= 0.3 AND pass_count >= 2)
    - OR source_count >= 3
    
    Args:
        insight: The insight to evaluate
        pass_count: Number of analysis passes
        source_count: Number of sources that contributed
        
    Returns:
        True if should be surfaced
    """
    # High significance: immediate surface
    if insight.significance >= SURFACING_SIGNIFICANCE_THRESHOLD:
        return True
    
    # Medium significance with reinforcement
    if insight.significance >= SURFACING_LOW_SIG_THRESHOLD and pass_count >= SURFACING_PASS_THRESHOLD:
        return True
    
    # Multiple sources: surface regardless of significance
    if source_count >= SURFACING_SOURCE_THRESHOLD:
        return True
    
    return False


# =============================================================================
# CONTENT PREPARATION
# =============================================================================

def prepare_chat_content(messages: List[Dict[str, str]], user_role: str = "user") -> str:
    """
    Prepare chat messages with speaker attribution tags.
    
    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."}
        user_role: The role name for user messages (default "user")
        
    Returns:
        Formatted string with XML-style speaker tags
    """
    parts = []
    
    for msg in messages:
        role = msg.get("role", "").lower()
        content = msg.get("content", "")
        
        if role == user_role or role == "human":
            parts.append(f"<USER_MESSAGE>\n{content}\n</USER_MESSAGE>")
        else:
            parts.append(f"<ASSISTANT_MESSAGE>\n{content}\n</ASSISTANT_MESSAGE>")
    
    return "\n\n".join(parts)


def prepare_document_content(text: str, max_chars: int = 8000) -> str:
    """
    Prepare document content, truncating if necessary.
    
    Args:
        text: Raw document text
        max_chars: Maximum character limit
        
    Returns:
        Prepared content string
    """
    if len(text) <= max_chars:
        return text
    
    return text[:max_chars] + "\n\n[... content truncated ...]"


# =============================================================================
# PROMPT BUILDER
# =============================================================================

# Case context template for prompt injection
CASE_CONTEXT_TEMPLATE = """## Case Context
You are extracting insights for a specific investigation case.

**Case Title:** {title}
**Investigation Context:** {context}
**Focus Areas:** {focus_areas}

Prioritise insights that:
1. Are directly relevant to the case context and focus areas
2. Have explicit supporting evidence from the text (cite excerpts)
3. Are factual observations, not speculation or assumptions
4. Could advance understanding of the investigation

Do NOT:
- Infer causation without explicit evidence
- Speculate beyond what the text supports
- Include tangential observations unrelated to the case
"""


def build_extraction_prompt(
    content: str,
    source_type: str,
    source_description: str = "",
    pre_annotation: Optional[Dict] = None,
    is_chat: bool = False,
    additional_context: str = "",
    case_context: Optional[Dict] = None,
) -> str:
    """
    Build the complete extraction prompt for LLM.
    
    Args:
        content: The content to analyse
        source_type: Type of source (document, chat, transcript, etc.)
        source_description: Description or ID of source
        pre_annotation: Optional Tier 0 pre-annotation results
        is_chat: Whether content has speaker attribution
        additional_context: Any extra context to include
        case_context: Optional case context dict with title, context, focus_areas
        
    Returns:
        Complete prompt string
    """
    # Calculate word count
    word_count = len(content.split())
    
    # Pre-annotation summary
    if pre_annotation:
        pre_summary = summarise_for_prompt(pre_annotation)
    else:
        pre_summary = "No pre-annotation available."
    
    # Speaker attribution
    if is_chat:
        speaker_attribution = SPEAKER_ATTRIBUTION_CHAT
        attribution_warning = ATTRIBUTION_WARNING_CHAT
    else:
        speaker_attribution = SPEAKER_ATTRIBUTION_NONE
        attribution_warning = ATTRIBUTION_WARNING_NONE
    
    # Build combined additional context (entity + case)
    context_parts = []
    
    # Add case context if provided
    if case_context:
        focus_areas_str = ", ".join(case_context.get("focus_areas", [])) or "Not specified"
        case_section = CASE_CONTEXT_TEMPLATE.format(
            title=case_context.get("title", "Untitled Case"),
            context=case_context.get("context", "No context provided"),
            focus_areas=focus_areas_str,
        )
        context_parts.append(case_section)
    
    # Add entity context if provided
    if additional_context:
        context_parts.append(additional_context)
    
    combined_context = "\n\n".join(context_parts) if context_parts else "None"
    
    # Truncate content if needed
    content = prepare_document_content(content)
    
    return INSIGHT_EXTRACTION_PROMPT.format(
        source_type=source_type,
        source_description=source_description or "Not specified",
        word_count=word_count,
        speaker_attribution=speaker_attribution,
        pre_annotation_summary=pre_summary,
        additional_context=combined_context,
        content=content,
        attribution_warning=attribution_warning,
    )


# =============================================================================
# LLM RESPONSE PARSING
# =============================================================================

def parse_extraction_response(
    response_text: str,
    source_type: str = "",
    source_id: str = "",
) -> ExtractionResult:
    """
    Parse LLM extraction response into structured result.
    
    Args:
        response_text: Raw LLM response
        source_type: Source type to attach to insights
        source_id: Source ID to attach to insights
        
    Returns:
        ExtractionResult with parsed insights
    """
    # Clean response - remove markdown code blocks if present
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        cleaned = "\n".join(lines)
    
    # Parse JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from LLM: {cleaned[:200]}...")
        return ExtractionResult(
            success=False,
            error=f"Invalid JSON response: {e}",
        )
    
    # Extract insights
    insights = []
    for insight_data in data.get("insights", []):
        if not insight_data.get("summary"):
            continue
        
        insight = ExtractedInsight(
            id=str(uuid4()),
            summary=insight_data.get("summary", ""),
            themes=insight_data.get("themes", []),
            emotional_tags=insight_data.get("emotional_tags", []),
            patterns=insight_data.get("patterns", []),
            significance=insight_data.get("significance", 0.5),
            confidence=insight_data.get("confidence", 0.5),
            excerpt=insight_data.get("excerpt", ""),
            insight_type=insight_data.get("insight_type", "observation"),
            source_type=source_type,
            source_id=source_id,
        )
        insights.append(insight)
    
    # Extract meta
    meta = data.get("meta", {})
    
    return ExtractionResult(
        success=True,
        insights=insights,
        content_quality=meta.get("content_quality", "medium"),
        suggested_reprocess=meta.get("suggested_reprocess", False),
        notes=meta.get("notes", ""),
    )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Types
    "ExtractedInsight",
    "ExtractionResult",
    # Prompt
    "INSIGHT_EXTRACTION_PROMPT",
    "build_extraction_prompt",
    "parse_extraction_response",
    # Content preparation
    "prepare_chat_content",
    "prepare_document_content",
    # Similarity
    "calculate_similarity",
    "find_similar_insight",
    "merge_insights",
    "SIMILARITY_THRESHOLD",
    # Surfacing
    "should_surface",
    "SURFACING_SIGNIFICANCE_THRESHOLD",
]

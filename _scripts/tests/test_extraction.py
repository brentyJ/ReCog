"""
ReCog Extraction Tests - Insight Extraction from LLM

Tests the extraction module's prompt building, response parsing,
and insight processing without requiring actual LLM calls.

Run with: pytest tests/test_extraction.py -v
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from recog_engine.extraction import (
    ExtractedInsight,
    build_extraction_prompt,
    parse_extraction_response,
    calculate_similarity,
    find_similar_insight,
    merge_insights,
    should_surface,
    SIMILARITY_THRESHOLD,
)


# =============================================================================
# TEST DATA
# =============================================================================

SAMPLE_TIER0 = {
    "word_count": 150,
    "emotion_signals": {
        "categories": ["anxiety", "hope"],
        "keywords_found": ["worried", "hopeful"],
    },
    "entities": {
        "people": ["Sarah", "Michael"],
        "email_addresses": [],
        "phone_numbers": [],
    },
    "temporal_references": {
        "past": ["last week", "yesterday"],
        "future": ["next month"],
    },
    "flags": {
        "high_emotion": True,
        "self_reflective": True,
    },
}

SAMPLE_TEXT = """
I talked to Sarah yesterday about the promotion. She said Michael 
is also being considered. I'm worried about the competition but 
hopeful that my work will speak for itself. Last week's presentation
went well, and I think that helped. Next month they'll announce
the decision.
"""

VALID_LLM_RESPONSE = '''
{
  "insights": [
    {
      "summary": "Subject is anxious about career competition with Michael for promotion",
      "significance": 0.8,
      "confidence": 0.85,
      "insight_type": "emotional_state",
      "themes": ["career", "competition", "anxiety"],
      "supporting_excerpt": "I'm worried about the competition",
      "temporal_context": "ongoing",
      "entities_mentioned": ["Michael"]
    },
    {
      "summary": "Subject feels positive about recent presentation performance",
      "significance": 0.6,
      "confidence": 0.9,
      "insight_type": "observation",
      "themes": ["work", "confidence", "achievement"],
      "supporting_excerpt": "Last week's presentation went well",
      "temporal_context": "past",
      "entities_mentioned": []
    }
  ],
  "meta": {
    "extraction_quality": "high",
    "text_coherence": "good"
  }
}
'''

MALFORMED_LLM_RESPONSES = [
    # Not JSON
    "Here are some insights I found...",
    # Missing insights key
    '{"data": []}',
    # Invalid JSON
    '{"insights": [}',
    # Empty insights
    '{"insights": []}',
]


# =============================================================================
# PROMPT BUILDING TESTS
# =============================================================================

def test_build_extraction_prompt_includes_context():
    """Prompt should include tier0 context."""
    prompt = build_extraction_prompt(SAMPLE_TEXT, SAMPLE_TIER0)
    
    assert "Sarah" in prompt, "Should include detected entities"
    assert "Michael" in prompt, "Should include detected entities"
    assert "anxiety" in prompt or "worried" in prompt, "Should include emotion context"
    assert "high_emotion" in prompt, "Should include flags"


def test_build_extraction_prompt_includes_text():
    """Prompt should include the source text."""
    prompt = build_extraction_prompt(SAMPLE_TEXT, SAMPLE_TIER0)
    
    assert "promotion" in prompt, "Should include source text"
    assert "presentation" in prompt, "Should include source text"


def test_build_extraction_prompt_structure():
    """Prompt should have expected structure."""
    prompt = build_extraction_prompt(SAMPLE_TEXT, SAMPLE_TIER0)
    
    # Should have role/instruction markers
    assert "insight" in prompt.lower(), "Should mention insights"
    assert "json" in prompt.lower(), "Should request JSON format"


# =============================================================================
# RESPONSE PARSING TESTS
# =============================================================================

def test_parse_valid_response():
    """Should correctly parse valid LLM JSON response."""
    result = parse_extraction_response(VALID_LLM_RESPONSE)
    
    assert result.success, "Should succeed for valid response"
    assert len(result.insights) == 2, "Should extract both insights"
    
    insight1 = result.insights[0]
    assert insight1.summary is not None
    assert 0 <= insight1.significance <= 1
    assert insight1.insight_type == "emotional_state"
    assert "career" in insight1.themes


def test_parse_insight_fields():
    """Parsed insights should have all expected fields."""
    result = parse_extraction_response(VALID_LLM_RESPONSE)
    insight = result.insights[0]
    
    assert isinstance(insight, ExtractedInsight)
    assert insight.summary is not None
    assert insight.significance is not None
    assert insight.confidence is not None
    assert insight.insight_type is not None
    assert isinstance(insight.themes, list)
    assert insight.supporting_excerpt is not None


def test_parse_malformed_responses():
    """Should handle malformed responses gracefully."""
    for bad_response in MALFORMED_LLM_RESPONSES:
        result = parse_extraction_response(bad_response)
        # Should not crash, may return empty insights or error
        assert result is not None, f"Should not crash on: {bad_response[:50]}"


def test_parse_response_with_markdown():
    """Should handle response wrapped in markdown code blocks."""
    wrapped = f"```json\n{VALID_LLM_RESPONSE}\n```"
    result = parse_extraction_response(wrapped)
    
    assert result.success, "Should handle markdown-wrapped JSON"
    assert len(result.insights) == 2


# =============================================================================
# SIMILARITY TESTS
# =============================================================================

def test_calculate_similarity_identical():
    """Identical text should have similarity 1.0."""
    text = "The subject feels anxious about work"
    sim = calculate_similarity(text, text)
    assert sim == 1.0


def test_calculate_similarity_different():
    """Completely different text should have low similarity."""
    text1 = "The subject enjoys hiking in the mountains"
    text2 = "A database query optimization technique"
    sim = calculate_similarity(text1, text2)
    assert sim < 0.3, "Unrelated text should have low similarity"


def test_calculate_similarity_similar():
    """Similar text should have high similarity."""
    text1 = "Subject feels anxious about the upcoming promotion"
    text2 = "The subject is anxious regarding their promotion prospects"
    sim = calculate_similarity(text1, text2)
    assert sim > 0.5, "Similar text should have moderate-high similarity"


def test_find_similar_insight():
    """Should find similar insights in a list."""
    insights = [
        ExtractedInsight(
            summary="Subject enjoys morning walks",
            significance=0.5,
            confidence=0.8,
            insight_type="observation",
        ),
        ExtractedInsight(
            summary="Subject feels anxious about work deadlines",
            significance=0.7,
            confidence=0.9,
            insight_type="emotional_state",
        ),
    ]
    
    new_insight = ExtractedInsight(
        summary="Subject is anxious about upcoming work deadlines",
        significance=0.75,
        confidence=0.85,
        insight_type="emotional_state",
    )
    
    match = find_similar_insight(new_insight, insights, threshold=0.5)
    assert match is not None, "Should find the similar anxiety insight"
    assert "anxious" in match.summary.lower()


# =============================================================================
# MERGE TESTS
# =============================================================================

def test_merge_insights_combines_themes():
    """Merging should combine themes from both insights."""
    insight1 = ExtractedInsight(
        summary="Subject feels stressed",
        significance=0.6,
        confidence=0.8,
        insight_type="emotional_state",
        themes=["stress", "work"],
    )
    
    insight2 = ExtractedInsight(
        summary="Subject is stressed about deadlines",
        significance=0.7,
        confidence=0.85,
        insight_type="emotional_state",
        themes=["deadlines", "pressure"],
    )
    
    merged = merge_insights(insight1, insight2)
    
    assert merged.significance >= 0.65, "Should average/boost significance"
    assert "stress" in merged.themes or "deadlines" in merged.themes


def test_merge_insights_updates_confidence():
    """Merging should increase confidence (corroborated)."""
    insight1 = ExtractedInsight(
        summary="Subject values family time",
        significance=0.5,
        confidence=0.7,
        insight_type="observation",
    )
    
    insight2 = ExtractedInsight(
        summary="Subject prioritizes family activities",
        significance=0.5,
        confidence=0.7,
        insight_type="observation",
    )
    
    merged = merge_insights(insight1, insight2)
    
    # Corroborated insights should have higher confidence
    assert merged.confidence >= insight1.confidence


# =============================================================================
# SURFACING TESTS
# =============================================================================

def test_should_surface_high_significance():
    """High significance insights should surface."""
    insight = ExtractedInsight(
        summary="Major life decision detected",
        significance=0.9,
        confidence=0.8,
        insight_type="decision",
    )
    
    assert should_surface(insight), "High significance should surface"


def test_should_surface_low_significance():
    """Low significance insights should not surface."""
    insight = ExtractedInsight(
        summary="Subject mentioned the weather",
        significance=0.2,
        confidence=0.9,
        insight_type="observation",
    )
    
    assert not should_surface(insight), "Low significance should not surface"


# =============================================================================
# STANDALONE RUNNER
# =============================================================================

if __name__ == "__main__":
    import traceback
    
    print("=" * 60)
    print("EXTRACTION TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Prompt includes context", test_build_extraction_prompt_includes_context),
        ("Prompt includes text", test_build_extraction_prompt_includes_text),
        ("Prompt structure", test_build_extraction_prompt_structure),
        ("Parse valid response", test_parse_valid_response),
        ("Parse insight fields", test_parse_insight_fields),
        ("Parse malformed responses", test_parse_malformed_responses),
        ("Parse markdown-wrapped", test_parse_response_with_markdown),
        ("Similarity identical", test_calculate_similarity_identical),
        ("Similarity different", test_calculate_similarity_different),
        ("Similarity similar", test_calculate_similarity_similar),
        ("Find similar insight", test_find_similar_insight),
        ("Merge combines themes", test_merge_insights_combines_themes),
        ("Merge updates confidence", test_merge_insights_updates_confidence),
        ("Surface high significance", test_should_surface_high_significance),
        ("Surface low significance", test_should_surface_low_significance),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            test_fn()
            print(f"✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"💥 {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")

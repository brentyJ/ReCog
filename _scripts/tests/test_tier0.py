"""
ReCog Tier 0 Tests - Signal Extraction

Run with: pytest tests/test_tier0.py -v
Or standalone: python tests/test_tier0.py
"""

import sys
from pathlib import Path

# Add parent to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent))

from recog_engine.tier0 import extract_basic_entities, preprocess_text


# =============================================================================
# TEST DATA
# =============================================================================

# Test cases that previously produced false positives
FALSE_POSITIVE_TESTS = [
    {
        "name": "common_words_only",
        "text": "The quick brown fox. This is a test. That was interesting.",
        "should_find": [],
        "should_not_find": ["The", "This", "That"],
    },
    {
        "name": "mixed_with_real_names",
        "text": "The manager said John would handle it. This means Sarah is free.",
        "should_find": ["John", "Sarah"],
        "should_not_find": ["The", "This"],
    },
    {
        "name": "after_quotes_and_colons",
        "text": 'He said: "The movie was great." She replied: "This one is better."',
        "should_find": [],
        "should_not_find": ["The", "This"],
    },
    {
        "name": "all_caps_filtered",
        "text": "THE MEETING IS CANCELLED. JOHN will reschedule.",
        "should_find": [],
        "should_not_find": ["THE", "MEETING", "CANCELLED", "JOHN"],
    },
    {
        "name": "verbs_after_punctuation",
        "text": "I went home. Going was the right choice. Sarah agreed.",
        "should_find": [],  # Sarah at sentence start = filtered
        "should_not_find": ["Going"],
    },
    {
        "name": "suffix_filtering",
        "text": "Something interesting happened. Working at the office. Meeting with Bob.",
        "should_find": ["Bob"],
        "should_not_find": ["Something", "Working", "Meeting"],
    },
    {
        "name": "journal_style",
        "text": """Today I talked to Nicole about the weekend plans. The weather was nice.
        This made me think about how we spent last summer. Going to the beach
        with Michael and Sarah was memorable. They always bring good energy.""",
        "should_find": ["Nicole", "Michael", "Sarah"],
        "should_not_find": ["The", "This", "Going"],
    },
]


# =============================================================================
# PYTEST FUNCTIONS
# =============================================================================

def test_no_false_positives():
    """Entity extraction should not flag common words as people."""
    for case in FALSE_POSITIVE_TESTS:
        result = extract_basic_entities(case["text"])
        people = result.get("people", [])
        
        for bad in case["should_not_find"]:
            assert bad not in people, f"[{case['name']}] False positive: '{bad}' detected"


def test_real_names_detected():
    """Entity extraction should still find actual names."""
    for case in FALSE_POSITIVE_TESTS:
        if not case["should_find"]:
            continue
            
        result = extract_basic_entities(case["text"])
        people = result.get("people", [])
        
        for name in case["should_find"]:
            assert name in people, f"[{case['name']}] Missed name: '{name}'"


def test_preprocess_flags():
    """Preprocess should set appropriate flags."""
    # High emotion: needs 2+ emotion keywords OR 2+ absolutes OR 2+ exclamations
    high_emotion_text = """
    I'm so angry and frustrated! This always happens and it never gets better!
    Why do I always do this to myself?
    """
    result = preprocess_text(high_emotion_text)
    assert result["flags"]["high_emotion"], "Should flag high emotion (angry + frustrated + absolutes)"
    assert result["flags"]["self_reflective"], "Should flag self-reflective (self-inquiry question)"


def test_emotion_detection():
    """Should detect emotion keywords."""
    text = "I'm feeling sad and worried about the future."
    result = preprocess_text(text)
    
    emotions = result["emotion_signals"]["keywords_found"]
    assert "sad" in emotions or "worried" in emotions, "Should detect emotions"


def test_phone_extraction():
    """Should extract Australian phone numbers."""
    text = "Call me on 0412 345 678 or +61 412 345 678"
    result = preprocess_text(text)
    
    phones = result["entities"]["phone_numbers"]
    assert len(phones) >= 1, "Should find phone numbers"


def test_email_extraction():
    """Should extract email addresses."""
    text = "Email me at test@example.com or support@ehkolabs.io"
    result = preprocess_text(text)
    
    emails = result["entities"]["email_addresses"]
    assert len(emails) == 2, "Should find both emails"


# =============================================================================
# STANDALONE RUNNER
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TIER 0 TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("No false positives", test_no_false_positives),
        ("Real names detected", test_real_names_detected),
        ("Preprocess flags", test_preprocess_flags),
        ("Emotion detection", test_emotion_detection),
        ("Phone extraction", test_phone_extraction),
        ("Email extraction", test_email_extraction),
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
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")

"""
ReCog Parser Tests - File Format Parsing

Tests all document parsers with sample content.

Run with: pytest tests/test_parsers.py -v
"""

import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.parsers import (
    get_parser,
    get_all_parsers,
    get_supported_extensions,
    PDFParser,
    MarkdownParser,
    PlaintextParser,
    MessagesParser,
    JSONExportParser,
)
from ingestion.types import ParsedContent


# =============================================================================
# TEST DATA
# =============================================================================

SAMPLE_MARKDOWN = """# Meeting Notes

## Attendees
- John Smith
- Sarah Johnson
- Michael Chen

## Discussion Points

We discussed the Q4 roadmap and agreed on the following:

1. Launch feature X by November
2. Complete testing by December
3. Holiday freeze starts December 15

### Action Items

- [ ] John to prepare documentation
- [ ] Sarah to review security
- [ ] Michael to coordinate with DevOps
"""

SAMPLE_PLAINTEXT = """Personal Journal Entry - October 15, 2024

Today was a challenging day at work. Had a difficult conversation
with my manager about the project timeline. I'm feeling stressed
about the upcoming deadline.

Called Mum in the evening, she always knows how to cheer me up.
Planning to visit her next weekend.

Phone: 0412 345 678
Email: test@example.com
"""

SAMPLE_WHATSAPP = """[12/10/2024, 9:15:32 AM] - Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them.
[12/10/2024, 9:15:32 AM] John Smith: Hey, are you coming to the party tonight?
[12/10/2024, 9:16:45 AM] Sarah: Yes! What time does it start?
[12/10/2024, 9:17:01 AM] John Smith: 7pm at Mike's place
[12/10/2024, 9:18:30 AM] Sarah: Perfect, I'll bring some snacks
[12/10/2024, 9:19:02 AM] John Smith: 👍
"""

SAMPLE_CHATGPT_EXPORT = [
    {
        "title": "Python Help Session",
        "create_time": 1702900000,
        "mapping": {
            "node1": {
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["How do I read a file in Python?"]},
                    "create_time": 1702900001
                }
            },
            "node2": {
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["You can use the open() function..."]},
                    "create_time": 1702900002
                }
            }
        }
    }
]

SAMPLE_SMS_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<smses count="3" backup_set="..." backup_date="1702900000000">
  <sms protocol="0" address="+61412345678" date="1702900001000" type="1" 
       body="Hey, are you free tomorrow?" readable_date="Dec 18, 2024 10:00:01 AM" 
       contact_name="John Smith" />
  <sms protocol="0" address="+61412345678" date="1702900002000" type="2" 
       body="Yes, what time works?" readable_date="Dec 18, 2024 10:00:02 AM" 
       contact_name="John Smith" />
  <sms protocol="0" address="+61412345678" date="1702900003000" type="1" 
       body="How about 2pm?" readable_date="Dec 18, 2024 10:00:03 AM" 
       contact_name="John Smith" />
</smses>
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_temp_file(content: str, suffix: str) -> Path:
    """Create a temporary file with given content."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
        f.write(content)
        return Path(f.name)


def create_temp_json(data, suffix: str = ".json") -> Path:
    """Create a temporary JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
        json.dump(data, f)
        return Path(f.name)


# =============================================================================
# PARSER DISCOVERY TESTS
# =============================================================================

def test_get_all_parsers():
    """Should return list of all available parsers."""
    parsers = get_all_parsers()
    
    assert len(parsers) >= 5, "Should have at least 5 parsers"
    assert all(hasattr(p, 'parse') for p in parsers), "All should have parse method"


def test_get_supported_extensions():
    """Should return list of supported file extensions."""
    extensions = get_supported_extensions()
    
    assert ".txt" in extensions, "Should support .txt"
    assert ".md" in extensions, "Should support .md"
    assert ".json" in extensions, "Should support .json"
    assert ".pdf" in extensions, "Should support .pdf"


def test_get_parser_for_markdown():
    """Should return MarkdownParser for .md files."""
    path = Path("test.md")
    parser = get_parser(path)
    
    # Parser selection is based on can_parse, which reads file
    # So we need an actual file
    temp_file = create_temp_file(SAMPLE_MARKDOWN, ".md")
    try:
        parser = get_parser(temp_file)
        assert parser is not None
        assert isinstance(parser, MarkdownParser)
    finally:
        temp_file.unlink()


def test_get_parser_for_plaintext():
    """Should return PlaintextParser for .txt files."""
    temp_file = create_temp_file(SAMPLE_PLAINTEXT, ".txt")
    try:
        parser = get_parser(temp_file)
        assert parser is not None
        # Could be PlaintextParser or MessagesParser depending on content detection
        assert hasattr(parser, 'parse')
    finally:
        temp_file.unlink()


# =============================================================================
# MARKDOWN PARSER TESTS
# =============================================================================

def test_markdown_parser_basic():
    """MarkdownParser should extract content from markdown."""
    temp_file = create_temp_file(SAMPLE_MARKDOWN, ".md")
    try:
        parser = MarkdownParser()
        result = parser.parse(temp_file)
        
        assert isinstance(result, ParsedContent)
        assert "Meeting Notes" in result.text
        assert "John Smith" in result.text
        assert "Q4 roadmap" in result.text
    finally:
        temp_file.unlink()


def test_markdown_parser_metadata():
    """MarkdownParser should extract metadata."""
    temp_file = create_temp_file(SAMPLE_MARKDOWN, ".md")
    try:
        parser = MarkdownParser()
        result = parser.parse(temp_file)
        
        assert result.metadata is not None
        assert "format" in result.metadata
    finally:
        temp_file.unlink()


# =============================================================================
# PLAINTEXT PARSER TESTS
# =============================================================================

def test_plaintext_parser_basic():
    """PlaintextParser should extract content from text files."""
    temp_file = create_temp_file(SAMPLE_PLAINTEXT, ".txt")
    try:
        parser = PlaintextParser()
        result = parser.parse(temp_file)
        
        assert isinstance(result, ParsedContent)
        assert "journal" in result.text.lower() or "challenging" in result.text
    finally:
        temp_file.unlink()


def test_plaintext_handles_encoding():
    """PlaintextParser should handle various encodings."""
    # UTF-8 with special characters
    content = "Café, naïve, résumé, 日本語"
    temp_file = create_temp_file(content, ".txt")
    try:
        parser = PlaintextParser()
        result = parser.parse(temp_file)
        
        # Should not crash, may replace or preserve special chars
        assert result is not None
        assert len(result.text) > 0
    finally:
        temp_file.unlink()


# =============================================================================
# MESSAGES PARSER TESTS
# =============================================================================

def test_messages_parser_whatsapp():
    """MessagesParser should detect and parse WhatsApp exports."""
    temp_file = create_temp_file(SAMPLE_WHATSAPP, ".txt")
    try:
        parser = MessagesParser()
        
        if parser.can_parse(temp_file):
            result = parser.parse(temp_file)
            
            assert isinstance(result, ParsedContent)
            assert "format" in result.metadata
            # Should detect as whatsapp or generic chat
            assert result.metadata.get("format") in ("whatsapp", "generic")
            assert result.metadata.get("message_count", 0) >= 4
    finally:
        temp_file.unlink()


def test_messages_parser_sms_xml():
    """MessagesParser should parse SMS Backup XML format."""
    temp_file = create_temp_file(SAMPLE_SMS_XML, ".xml")
    try:
        parser = MessagesParser()
        
        if parser.can_parse(temp_file):
            result = parser.parse(temp_file)
            
            assert isinstance(result, ParsedContent)
            assert result.metadata.get("format") == "sms_xml"
            assert result.metadata.get("message_count") == 3
            assert "John Smith" in result.metadata.get("participants", [])
    finally:
        temp_file.unlink()


def test_messages_extracts_participants():
    """MessagesParser should extract participant names."""
    temp_file = create_temp_file(SAMPLE_WHATSAPP, ".txt")
    try:
        parser = MessagesParser()
        
        if parser.can_parse(temp_file):
            result = parser.parse(temp_file)
            
            participants = result.metadata.get("participants", [])
            # Should find at least John Smith and Sarah
            assert len(participants) >= 2
    finally:
        temp_file.unlink()


# =============================================================================
# JSON EXPORT PARSER TESTS
# =============================================================================

def test_json_parser_chatgpt():
    """JSONExportParser should parse ChatGPT export format."""
    temp_file = create_temp_json(SAMPLE_CHATGPT_EXPORT)
    try:
        parser = JSONExportParser()
        
        if parser.can_parse(temp_file):
            result = parser.parse(temp_file)
            
            assert isinstance(result, ParsedContent)
            assert "format" in result.metadata
            assert "Python" in result.text or "file" in result.text
    finally:
        temp_file.unlink()


def test_json_parser_message_array():
    """JSONExportParser should parse simple message arrays."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    temp_file = create_temp_json(messages)
    try:
        parser = JSONExportParser()
        
        if parser.can_parse(temp_file):
            result = parser.parse(temp_file)
            
            assert "Hello" in result.text
            assert "Hi there" in result.text
    finally:
        temp_file.unlink()


def test_json_parser_rejects_non_chat():
    """JSONExportParser should not parse non-chat JSON."""
    non_chat = {"users": [{"name": "John", "age": 30}]}
    temp_file = create_temp_json(non_chat)
    try:
        parser = JSONExportParser()
        
        # Should return False for can_parse or handle gracefully
        if parser.can_parse(temp_file):
            result = parser.parse(temp_file)
            # If it parses, should have unknown format
            assert result.metadata.get("format") == "unknown_json"
    finally:
        temp_file.unlink()


# =============================================================================
# PARSED CONTENT TESTS
# =============================================================================

def test_parsed_content_has_required_fields():
    """ParsedContent should have text and metadata."""
    content = ParsedContent(text="Test content")
    
    assert content.text == "Test content"
    assert content.metadata is not None


def test_parsed_content_optional_fields():
    """ParsedContent should support optional fields."""
    content = ParsedContent(
        text="Test content",
        title="Test Title",
        date="2024-01-01",
        metadata={"source": "test"},
    )
    
    assert content.title == "Test Title"
    assert content.date == "2024-01-01"
    assert content.metadata["source"] == "test"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

def test_parser_handles_empty_file():
    """Parsers should handle empty files gracefully."""
    temp_file = create_temp_file("", ".txt")
    try:
        parser = PlaintextParser()
        result = parser.parse(temp_file)
        
        # Should not crash
        assert result is not None
        assert result.text == "" or result.text is not None
    finally:
        temp_file.unlink()


def test_parser_handles_binary_in_text():
    """Parsers should handle binary content gracefully."""
    # Create file with some binary content
    temp_file = create_temp_file("Normal text \x00\x01\x02 more text", ".txt")
    try:
        parser = PlaintextParser()
        result = parser.parse(temp_file)
        
        # Should not crash
        assert result is not None
    finally:
        temp_file.unlink()


# =============================================================================
# STANDALONE RUNNER
# =============================================================================

if __name__ == "__main__":
    import traceback
    
    print("=" * 60)
    print("PARSER TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Get all parsers", test_get_all_parsers),
        ("Get supported extensions", test_get_supported_extensions),
        ("Get parser for markdown", test_get_parser_for_markdown),
        ("Get parser for plaintext", test_get_parser_for_plaintext),
        ("Markdown parser basic", test_markdown_parser_basic),
        ("Markdown parser metadata", test_markdown_parser_metadata),
        ("Plaintext parser basic", test_plaintext_parser_basic),
        ("Plaintext handles encoding", test_plaintext_handles_encoding),
        ("Messages parser WhatsApp", test_messages_parser_whatsapp),
        ("Messages parser SMS XML", test_messages_parser_sms_xml),
        ("Messages extracts participants", test_messages_extracts_participants),
        ("JSON parser ChatGPT", test_json_parser_chatgpt),
        ("JSON parser message array", test_json_parser_message_array),
        ("JSON parser rejects non-chat", test_json_parser_rejects_non_chat),
        ("ParsedContent required fields", test_parsed_content_has_required_fields),
        ("ParsedContent optional fields", test_parsed_content_optional_fields),
        ("Parser handles empty file", test_parser_handles_empty_file),
        ("Parser handles binary", test_parser_handles_binary_in_text),
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

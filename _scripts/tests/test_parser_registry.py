"""
Tests for the parser registry system.

Tests cover:
- ParseResult dataclass and class methods
- FormatDetector MIME and platform detection
- ParserRegistry registration and routing
- LegacyParserWrapper adapter
- register_parser decorator

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import pytest
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from recog_engine.parsers.base import ParseResult, BaseParser
from recog_engine.parsers.detector import FormatDetector, detect_format, get_detector
from recog_engine.parsers.registry import (
    ParserRegistry,
    LegacyParserWrapper,
    register_parser,
    get_registry,
)


# =============================================================================
# ParseResult Tests
# =============================================================================

class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_create_success_result(self):
        """ParseResult should store success state and data."""
        result = ParseResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.warnings == []
        assert result.metadata == {}

    def test_create_with_format_version(self):
        """ParseResult should store format version."""
        result = ParseResult(
            success=True,
            data={},
            format_version="vCard 3.0"
        )
        assert result.format_version == "vCard 3.0"

    def test_create_with_warnings(self):
        """ParseResult should store warnings list."""
        result = ParseResult(
            success=True,
            data={},
            warnings=["Warning 1", "Warning 2"]
        )
        assert len(result.warnings) == 2
        assert "Warning 1" in result.warnings

    def test_create_with_metadata(self):
        """ParseResult should store metadata dict."""
        result = ParseResult(
            success=True,
            data={},
            metadata={"parse_time_ms": 123}
        )
        assert result.metadata["parse_time_ms"] == 123

    def test_failure_class_method(self):
        """ParseResult.failure() should create failure result."""
        result = ParseResult.failure("Something went wrong")
        assert result.success is False
        assert result.data is None
        assert "Something went wrong" in result.warnings

    def test_failure_with_metadata(self):
        """ParseResult.failure() should accept metadata kwargs."""
        result = ParseResult.failure(
            "File not found",
            file_path="/test/file.txt",
            error_code=404
        )
        assert result.success is False
        assert result.metadata["file_path"] == "/test/file.txt"
        assert result.metadata["error_code"] == 404

    def test_partial_class_method(self):
        """ParseResult.partial() should create partial success."""
        result = ParseResult.partial(
            data={"partial": "data"},
            warnings=["Skipped 5 records"]
        )
        assert result.success is True
        assert result.data == {"partial": "data"}
        assert "Skipped 5 records" in result.warnings

    def test_partial_with_metadata(self):
        """ParseResult.partial() should accept metadata kwargs."""
        result = ParseResult.partial(
            data=[1, 2, 3],
            warnings=["Truncated"],
            original_count=100,
            parsed_count=3
        )
        assert result.metadata["original_count"] == 100
        assert result.metadata["parsed_count"] == 3

    def test_add_warning(self):
        """add_warning() should append to warnings list."""
        result = ParseResult(success=True, data={})
        result.add_warning("New warning")
        assert "New warning" in result.warnings

    def test_add_multiple_warnings(self):
        """add_warning() should accumulate warnings."""
        result = ParseResult(success=True, data={})
        result.add_warning("Warning 1")
        result.add_warning("Warning 2")
        result.add_warning("Warning 3")
        assert len(result.warnings) == 3

    def test_has_warnings_false(self):
        """has_warnings() should return False when no warnings."""
        result = ParseResult(success=True, data={})
        assert result.has_warnings() is False

    def test_has_warnings_true(self):
        """has_warnings() should return True when warnings exist."""
        result = ParseResult(success=True, data={}, warnings=["Warning"])
        assert result.has_warnings() is True

    def test_post_init_none_warnings(self):
        """__post_init__ should handle None warnings."""
        result = ParseResult(success=True, data={}, warnings=None)
        assert result.warnings == []

    def test_post_init_none_metadata(self):
        """__post_init__ should handle None metadata."""
        result = ParseResult(success=True, data={}, metadata=None)
        assert result.metadata == {}


# =============================================================================
# FormatDetector Tests
# =============================================================================

class TestFormatDetector:
    """Tests for FormatDetector."""

    def test_init_lazy_magic(self):
        """FormatDetector should lazy-load python-magic."""
        detector = FormatDetector()
        assert detector._magic is None

    def test_mime_from_extension_zip(self):
        """Should detect ZIP MIME type from extension."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.zip"
            test_file.write_bytes(b"")
            mime = detector._mime_from_extension(test_file)
            assert mime == "application/zip"

    def test_mime_from_extension_csv(self):
        """Should detect CSV MIME type from extension."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "data.csv"
            test_file.write_text("")
            mime = detector._mime_from_extension(test_file)
            assert mime == "text/csv"

    def test_mime_from_extension_json(self):
        """Should detect JSON MIME type from extension."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "config.json"
            test_file.write_text("{}")
            mime = detector._mime_from_extension(test_file)
            assert mime == "application/json"

    def test_mime_from_extension_unknown(self):
        """Should return octet-stream for unknown extensions."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "file.xyz123"
            test_file.write_bytes(b"")
            mime = detector._mime_from_extension(test_file)
            assert mime == "application/octet-stream"

    def test_mime_from_extension_case_insensitive(self):
        """Extension detection should be case-insensitive."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "DATA.CSV"
            test_file.write_text("")
            mime = detector._mime_from_extension(test_file)
            assert mime == "text/csv"

    def test_detect_mime_type_fallback(self):
        """detect_mime_type should fallback to extension when magic unavailable."""
        detector = FormatDetector()
        detector._magic = False  # Simulate unavailable
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.json"
            test_file.write_text("{}")
            mime = detector.detect_mime_type(test_file)
            assert mime == "application/json"

    def test_detect_platform_non_zip(self):
        """detect_platform_export should return None for non-ZIP files."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("not a zip")
            platform = detector.detect_platform_export(test_file)
            assert platform is None

    def test_detect_platform_facebook(self):
        """Should detect Facebook export by messages/inbox/ structure."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "facebook.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("messages/inbox/friend/message_1.json", "{}")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "facebook"

    def test_detect_platform_instagram(self):
        """Should detect Instagram export by instagram_ prefix."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "instagram.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("instagram_media/photos/photo1.jpg", b"")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "instagram"

    def test_detect_platform_twitter(self):
        """Should detect Twitter export by data/tweet.js pattern."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "twitter.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("data/tweet.js", "window.YTD.tweet.part0 = []")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "twitter"

    def test_detect_platform_google_takeout(self):
        """Should detect Google Takeout by Takeout/ directory."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "takeout.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("Takeout/Chrome/History.json", "{}")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "google_takeout"

    def test_detect_platform_notion(self):
        """Should detect Notion export by UUID filename pattern."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "notion.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("Page 12345678901234567890123456789012.md", "# Page")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "notion"

    def test_detect_platform_chatgpt(self):
        """Should detect ChatGPT export by conversations.json."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "chatgpt.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("conversations.json", "[]")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "chatgpt"

    def test_detect_platform_linkedin(self):
        """Should detect LinkedIn export by Connections.csv."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "linkedin.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("Connections.csv", "First Name,Last Name")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "linkedin"

    def test_detect_platform_whatsapp(self):
        """Should detect WhatsApp export by _chat.txt pattern."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "whatsapp.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("WhatsApp_chat.txt", "[01/01/2024] - User: Hello")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "whatsapp"

    def test_detect_platform_spotify(self):
        """Should detect Spotify export by StreamingHistory."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "spotify.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("StreamingHistory0.json", "[]")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "spotify"

    def test_detect_platform_apple_health(self):
        """Should detect Apple Health export."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "health.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("apple_health_export/export.xml", "<HealthData/>")
            platform = detector.detect_platform_export(zip_path)
            assert platform == "apple_health"

    def test_detect_platform_unknown_archive(self):
        """Should return None for unrecognized archive structure."""
        detector = FormatDetector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "random.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("file1.txt", "content")
                zf.writestr("file2.txt", "content")
            platform = detector.detect_platform_export(zip_path)
            assert platform is None

    def test_detect_combined(self):
        """detect() should return both MIME type and platform."""
        detector = FormatDetector()
        detector._magic = False  # Use extension fallback
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "facebook.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("messages/inbox/chat/msg.json", "{}")
            mime, platform = detector.detect(zip_path)
            assert mime == "application/zip"
            assert platform == "facebook"

    def test_is_archive_true(self):
        """is_archive() should return True for archive MIME types."""
        detector = FormatDetector()
        detector._magic = False
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "archive.zip"
            test_file.write_bytes(b"")
            assert detector.is_archive(test_file) is True

    def test_is_archive_false(self):
        """is_archive() should return False for non-archive files."""
        detector = FormatDetector()
        detector._magic = False
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "data.csv"
            test_file.write_text("")
            assert detector.is_archive(test_file) is False

    def test_is_text_true(self):
        """is_text() should return True for text MIME types."""
        detector = FormatDetector()
        detector._magic = False
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "readme.txt"
            test_file.write_text("")
            assert detector.is_text(test_file) is True

    def test_is_text_json(self):
        """is_text() should return True for JSON files."""
        detector = FormatDetector()
        detector._magic = False
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "data.json"
            test_file.write_text("{}")
            assert detector.is_text(test_file) is True

    def test_is_text_false(self):
        """is_text() should return False for binary files."""
        detector = FormatDetector()
        detector._magic = False
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "image.png"
            test_file.write_bytes(b"")
            assert detector.is_text(test_file) is False

    def test_detect_format_convenience_function(self):
        """detect_format() should use global detector."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.csv"
            test_file.write_text("a,b,c")
            mime, platform = detect_format(test_file)
            assert "csv" in mime.lower() or mime == "text/plain"

    def test_get_detector_singleton(self):
        """get_detector() should return global instance."""
        detector1 = get_detector()
        detector2 = get_detector()
        assert detector1 is detector2


# =============================================================================
# Mock Parser for Testing
# =============================================================================

class MockParser(BaseParser):
    """Mock parser for testing registry."""

    def __init__(self, formats=None, extensions=None):
        self._formats = formats or ["text/plain"]
        self._extensions = extensions or [".txt"]
        self.parse_called = False
        self.can_parse_result = True

    @property
    def supported_formats(self):
        return self._formats

    @property
    def supported_extensions(self):
        return self._extensions

    def can_parse(self, file_path, mime_type=None):
        return self.can_parse_result

    def parse(self, file_path, **options):
        self.parse_called = True
        return ParseResult(success=True, data={"parsed": True})

    def detect_version(self, file_path):
        return "MockParser 1.0"


# =============================================================================
# ParserRegistry Tests
# =============================================================================

class TestParserRegistry:
    """Tests for ParserRegistry."""

    def test_init_empty(self):
        """Registry should initialize with empty parser dicts."""
        registry = ParserRegistry()
        assert registry._mime_parsers == {}
        assert registry._platform_parsers == {}
        assert registry._extension_parsers == {}

    def test_register_by_mime_type(self):
        """register() should register parser by MIME type."""
        registry = ParserRegistry()
        registry.register(MockParser)
        assert "text/plain" in registry._mime_parsers

    def test_register_by_extension(self):
        """register() should also register by extension."""
        registry = ParserRegistry()
        registry.register(MockParser)
        assert ".txt" in registry._extension_parsers

    def test_register_platform_parser(self):
        """register() with platform_name should register platform parser."""
        registry = ParserRegistry()
        registry.register(MockParser, platform_name="facebook")
        assert "facebook" in registry._platform_parsers

    def test_register_legacy_parser(self):
        """register_legacy_parser() should wrap and register legacy parser."""
        registry = ParserRegistry()

        # Create mock legacy parser
        legacy = Mock()
        legacy.can_parse = Mock(return_value=True)
        legacy.__class__.__name__ = "LegacyMock"

        registry.register_legacy_parser(
            legacy,
            mime_types=["application/x-legacy"],
            extensions=[".leg"]
        )

        assert "application/x-legacy" in registry._mime_parsers
        assert ".leg" in registry._extension_parsers
        assert registry._is_instance.get("application/x-legacy") is True

    def test_get_parser_by_mime(self):
        """get_parser() should find parser by MIME type."""
        registry = ParserRegistry()
        registry.register(MockParser)

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("hello")

            parser = registry.get_parser(test_file)
            assert parser is not None
            assert isinstance(parser, MockParser)

    def test_get_parser_by_platform(self):
        """get_parser() should prioritize platform-specific parser."""
        registry = ParserRegistry()

        class FacebookParser(MockParser):
            pass

        registry.register(FacebookParser, platform_name="facebook")

        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "fb.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("messages/inbox/chat/msg.json", "{}")

            parser = registry.get_parser(zip_path)
            assert parser is not None
            assert isinstance(parser, FacebookParser)

    def test_get_parser_fallback_to_extension(self):
        """get_parser() should fallback to extension parser."""
        registry = ParserRegistry()
        registry._extension_parsers[".xyz"] = MockParser

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.xyz"
            test_file.write_bytes(b"")

            parser = registry.get_parser(test_file)
            assert parser is not None

    def test_get_parser_none_when_not_found(self):
        """get_parser() should return None when no parser found."""
        registry = ParserRegistry()

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.unknown123"
            test_file.write_bytes(b"")

            parser = registry.get_parser(test_file)
            assert parser is None

    def test_get_parser_respects_can_parse(self):
        """get_parser() should check can_parse() before returning."""
        registry = ParserRegistry()

        class PickyParser(MockParser):
            def can_parse(self, file_path, mime_type=None):
                return False

        registry.register(PickyParser)

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("hello")

            parser = registry.get_parser(test_file)
            assert parser is None

    def test_parse_success(self):
        """parse() should execute parser and return result."""
        registry = ParserRegistry()
        registry.register(MockParser)

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("hello")

            result = registry.parse(test_file)
            assert result.success is True
            assert result.data == {"parsed": True}

    def test_parse_adds_version_to_metadata(self):
        """parse() should add format version to metadata."""
        registry = ParserRegistry()
        registry.register(MockParser)

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("hello")

            result = registry.parse(test_file)
            assert result.metadata.get("format_version") == "MockParser 1.0"

    def test_parse_no_parser_failure(self):
        """parse() should return failure when no parser found."""
        registry = ParserRegistry()

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.xyz999"
            test_file.write_bytes(b"")

            result = registry.parse(test_file)
            assert result.success is False
            assert "No parser available" in result.warnings[0]

    def test_parse_handles_exception(self):
        """parse() should catch exceptions and return failure."""
        registry = ParserRegistry()

        class CrashingParser(MockParser):
            def parse(self, file_path, **options):
                raise ValueError("Parser exploded")

        registry.register(CrashingParser)

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("hello")

            result = registry.parse(test_file)
            assert result.success is False
            assert "Parser exploded" in result.warnings[0]

    def test_list_parsers(self):
        """list_parsers() should return all registered parsers."""
        registry = ParserRegistry()
        registry.register(MockParser)
        registry.register(MockParser, platform_name="test_platform")

        parsers = registry.list_parsers()
        assert "text/plain" in parsers["mime"]
        assert "test_platform" in parsers["platform"]
        assert ".txt" in parsers["extension"]

    def test_get_supported_extensions(self):
        """get_supported_extensions() should return sorted extensions."""
        registry = ParserRegistry()

        class MultiExtParser(MockParser):
            @property
            def supported_extensions(self):
                return [".zzz", ".aaa", ".mmm"]

        registry.register(MultiExtParser)

        extensions = registry.get_supported_extensions()
        assert extensions == [".aaa", ".mmm", ".zzz"]


# =============================================================================
# LegacyParserWrapper Tests
# =============================================================================

class TestLegacyParserWrapper:
    """Tests for LegacyParserWrapper adapter."""

    def test_wrapper_stores_legacy_parser(self):
        """Wrapper should store legacy parser reference."""
        legacy = Mock()
        wrapper = LegacyParserWrapper(legacy, ["text/plain"], [".txt"])
        assert wrapper._legacy is legacy

    def test_wrapper_supported_formats(self):
        """Wrapper should expose MIME types."""
        legacy = Mock()
        wrapper = LegacyParserWrapper(legacy, ["text/plain", "text/csv"], [".txt"])
        assert wrapper.supported_formats == ["text/plain", "text/csv"]

    def test_wrapper_supported_extensions(self):
        """Wrapper should expose extensions."""
        legacy = Mock()
        wrapper = LegacyParserWrapper(legacy, ["text/plain"], [".txt", ".text"])
        assert wrapper.supported_extensions == [".txt", ".text"]

    def test_wrapper_delegates_can_parse(self):
        """Wrapper should delegate can_parse to legacy parser."""
        legacy = Mock()
        legacy.can_parse = Mock(return_value=True)

        wrapper = LegacyParserWrapper(legacy, ["text/plain"], [".txt"])

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("")

            result = wrapper.can_parse(test_file)
            assert result is True
            legacy.can_parse.assert_called_once_with(test_file)

    def test_wrapper_parse_converts_result(self):
        """Wrapper should convert ParsedContent to ParseResult."""
        legacy = Mock()
        legacy.parse = Mock(return_value=Mock(
            text="Parsed text",
            title="Document Title",
            author="Author Name",
            date="2024-01-01",
            metadata={"key": "value"}
        ))

        wrapper = LegacyParserWrapper(legacy, ["text/plain"], [".txt"])

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("content")

            result = wrapper.parse(test_file)
            assert result.success is True
            assert result.data["text"] == "Parsed text"
            assert result.data["title"] == "Document Title"
            assert result.metadata["key"] == "value"

    def test_wrapper_parse_handles_exception(self):
        """Wrapper should return failure on legacy parser exception."""
        legacy = Mock()
        legacy.parse = Mock(side_effect=ValueError("Legacy error"))

        wrapper = LegacyParserWrapper(legacy, ["text/plain"], [".txt"])

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("content")

            result = wrapper.parse(test_file)
            assert result.success is False
            assert "Legacy error" in result.warnings[0]


# =============================================================================
# register_parser Decorator Tests
# =============================================================================

class TestRegisterParserDecorator:
    """Tests for @register_parser decorator."""

    def test_decorator_without_args(self):
        """@register_parser should register parser class."""
        # Note: This modifies the global registry, so we test carefully

        @register_parser
        class TestParser(MockParser):
            @property
            def supported_formats(self):
                return ["application/x-test-decorator"]

            @property
            def supported_extensions(self):
                return [".testdec"]

        registry = get_registry()
        assert "application/x-test-decorator" in registry._mime_parsers

    def test_decorator_with_platform(self):
        """@register_parser(platform='...') should register platform parser."""

        @register_parser(platform="test_platform_dec")
        class TestPlatformParser(MockParser):
            pass

        registry = get_registry()
        assert "test_platform_dec" in registry._platform_parsers

    def test_decorator_returns_class(self):
        """Decorator should return the original class."""

        @register_parser
        class ReturnedParser(MockParser):
            @property
            def supported_formats(self):
                return ["application/x-returned"]

            @property
            def supported_extensions(self):
                return [".ret"]

        assert ReturnedParser.__name__ == "ReturnedParser"
        assert issubclass(ReturnedParser, MockParser)


# =============================================================================
# Integration Tests
# =============================================================================

class TestRegistryIntegration:
    """Integration tests for the full registry system."""

    def test_full_flow_text_file(self):
        """Test full flow: detect → get_parser → parse for text file."""
        registry = ParserRegistry()
        registry.register(MockParser)

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "document.txt"
            test_file.write_text("Hello, world!")

            # Detection
            mime, platform = registry.detector.detect(test_file)
            assert "text" in mime

            # Get parser
            parser = registry.get_parser(test_file)
            assert parser is not None

            # Parse
            result = registry.parse(test_file)
            assert result.success is True

    def test_full_flow_platform_export(self):
        """Test full flow for platform export detection."""
        registry = ParserRegistry()

        class TwitterMockParser(MockParser):
            @property
            def supported_formats(self):
                return ["application/zip"]

        registry.register(TwitterMockParser, platform_name="twitter")

        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "twitter_export.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("data/tweet.js", "window.YTD.tweet.part0 = []")

            # Detection
            mime, platform = registry.detector.detect(zip_path)
            assert mime == "application/zip"
            assert platform == "twitter"

            # Get parser (should get platform-specific)
            parser = registry.get_parser(zip_path)
            assert parser is not None
            assert isinstance(parser, TwitterMockParser)

    def test_multiple_parsers_priority(self):
        """Test that platform parsers have priority over MIME parsers."""
        registry = ParserRegistry()

        class GenericZipParser(MockParser):
            @property
            def supported_formats(self):
                return ["application/zip"]

            @property
            def supported_extensions(self):
                return [".zip"]

        class FacebookSpecificParser(MockParser):
            pass

        registry.register(GenericZipParser)
        registry.register(FacebookSpecificParser, platform_name="facebook")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Facebook export
            fb_zip = Path(tmp_dir) / "fb.zip"
            with zipfile.ZipFile(fb_zip, 'w') as zf:
                zf.writestr("messages/inbox/friend/msg.json", "{}")

            parser = registry.get_parser(fb_zip)
            assert isinstance(parser, FacebookSpecificParser)

            # Generic zip
            generic_zip = Path(tmp_dir) / "random.zip"
            with zipfile.ZipFile(generic_zip, 'w') as zf:
                zf.writestr("file.txt", "content")

            parser = registry.get_parser(generic_zip)
            assert isinstance(parser, GenericZipParser)

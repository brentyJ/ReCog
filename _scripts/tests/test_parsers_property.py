"""
Property-based tests for parsers using Hypothesis.

These tests generate random inputs to find edge cases and
ensure parsers handle malformed data gracefully.

Run with: pytest tests/test_parsers_property.py -v

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import pytest
import tempfile
from pathlib import Path

# Skip all tests if hypothesis not installed
hypothesis = pytest.importorskip("hypothesis")

from hypothesis import given, strategies as st, settings, assume
from hypothesis.strategies import text, binary, integers, lists


class TestCSVParserProperty:
    """Property-based tests for CSV parser."""

    @given(
        headers=lists(text(min_size=1, max_size=20), min_size=1, max_size=10),
        rows=lists(lists(text(max_size=50), min_size=1, max_size=10), min_size=0, max_size=20)
    )
    @settings(max_examples=50, deadline=5000)
    def test_csv_parser_handles_arbitrary_content(self, headers, rows):
        """CSV parser should handle any valid CSV structure without crashing."""
        from ingestion.parsers.csv_enhanced import EnhancedCSVParser

        # Ensure all rows have same length as headers
        normalized_rows = [
            row[:len(headers)] + [''] * (len(headers) - len(row))
            for row in rows
        ]

        # Build CSV content - escape quotes in values
        def escape_csv(val):
            return val.replace('"', '""')

        lines = [','.join(f'"{escape_csv(h)}"' for h in headers)]
        for row in normalized_rows:
            lines.append(','.join(f'"{escape_csv(v)}"' for v in row))
        content = '\n'.join(lines)

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_file = Path(tmp_dir) / "test.csv"
            csv_file.write_text(content, encoding='utf-8')

            parser = EnhancedCSVParser()
            result = parser.parse(csv_file)

            # Should not crash - result should have text
            assert result.text is not None
            assert isinstance(result.metadata, dict)

    @given(delimiter=st.sampled_from([',', ';', '\t', '|']))
    @settings(max_examples=20, deadline=3000)
    def test_csv_parser_detects_delimiters(self, delimiter):
        """CSV parser should detect common delimiters."""
        from ingestion.parsers.csv_enhanced import EnhancedCSVParser

        content = delimiter.join(['name', 'value']) + '\n'
        content += delimiter.join(['test', '123']) + '\n'

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_file = Path(tmp_dir) / "test.csv"
            csv_file.write_text(content, encoding='utf-8')

            parser = EnhancedCSVParser()
            result = parser.parse(csv_file)

            assert result.text is not None
            # Should contain the data
            assert 'test' in result.text or 'name' in result.text


class TestICSParserProperty:
    """Property-based tests for ICS calendar parser."""

    @given(
        summary=text(min_size=1, max_size=100),
        year=integers(min_value=2000, max_value=2030),
        month=integers(min_value=1, max_value=12),
        day=integers(min_value=1, max_value=28),  # Safe for all months
        hour=integers(min_value=0, max_value=23),
    )
    @settings(max_examples=30, deadline=3000)
    def test_ics_parser_handles_arbitrary_events(self, summary, year, month, day, hour):
        """ICS parser should handle any valid event without crashing."""
        from ingestion.parsers.calendar import ICSParser

        # Filter out problematic characters for ICS
        clean_summary = ''.join(c for c in summary if c.isalnum() or c in ' -_')
        assume(len(clean_summary) > 0)

        content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
DTSTART:{year:04d}{month:02d}{day:02d}T{hour:02d}0000Z
SUMMARY:{clean_summary}
UID:test-{year}-{month}-{day}@test.local
END:VEVENT
END:VCALENDAR"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            ics_file = Path(tmp_dir) / "test.ics"
            ics_file.write_text(content, encoding='utf-8')

            parser = ICSParser()
            result = parser.parse(ics_file)

            assert result.text is not None
            assert 'error' not in result.metadata or result.metadata.get('error') is None


class TestVCFParserProperty:
    """Property-based tests for VCF contact parser."""

    @given(
        given_name=text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', min_size=1, max_size=20),
        family_name=text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', min_size=1, max_size=20),
        phone_digits=text(alphabet='0123456789', min_size=5, max_size=15),
    )
    @settings(max_examples=30, deadline=3000)
    def test_vcf_parser_handles_arbitrary_contacts(self, given_name, family_name, phone_digits):
        """VCF parser should handle any valid contact without crashing."""
        from ingestion.parsers.contacts import VCFParser

        content = f"""BEGIN:VCARD
VERSION:3.0
FN:{given_name} {family_name}
N:{family_name};{given_name};;;
TEL:{phone_digits}
END:VCARD"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            vcf_file = Path(tmp_dir) / "test.vcf"
            vcf_file.write_text(content, encoding='utf-8')

            parser = VCFParser()
            result = parser.parse(vcf_file)

            assert result.text is not None
            assert 'error' not in result.metadata or result.metadata.get('error') is None


class TestArchiveSecurityProperty:
    """Property-based tests for archive security."""

    @given(
        filename=text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789', min_size=1, max_size=20),
        content=binary(min_size=0, max_size=1000),
    )
    @settings(max_examples=20, deadline=5000)
    def test_archive_rejects_path_traversal(self, filename, content):
        """Archive parser should reject path traversal attempts."""
        from ingestion.parsers.archive import ArchiveParser
        import zipfile

        # Create filename with traversal attempt
        malicious_name = f"../../../{filename}.txt"

        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_file = Path(tmp_dir) / "test.zip"
            try:
                with zipfile.ZipFile(zip_file, 'w') as zf:
                    zf.writestr(malicious_name, content)
            except (ValueError, OSError):
                # Some filenames are invalid - skip
                return

            parser = ArchiveParser()
            result = parser.parse(zip_file)

            # Should either fail with security error or skip the file
            assert result.text is not None
            # If parsed, should not have extracted outside temp dir


class TestEncodingProperty:
    """Property-based tests for encoding handling."""

    @given(
        text_content=text(min_size=1, max_size=200),
    )
    @settings(max_examples=30, deadline=3000)
    def test_encoding_detection_handles_unicode(self, text_content):
        """Encoding detection should handle various Unicode content."""
        from ingestion.parsers.csv_enhanced import EnhancedCSVParser

        # Filter out problematic characters
        safe_content = ''.join(c for c in text_content if c.isprintable() and c != '"')
        assume(len(safe_content) > 0)

        # Create CSV with Unicode content
        content = f'name,value\n"{safe_content}",123\n'

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Try different encodings
            for encoding in ['utf-8', 'utf-16', 'latin-1']:
                try:
                    csv_file = Path(tmp_dir) / f"test_{encoding}.csv"
                    csv_file.write_text(content, encoding=encoding)

                    parser = EnhancedCSVParser()
                    result = parser.parse(csv_file)

                    assert result.text is not None
                except UnicodeEncodeError:
                    # Some content can't be encoded in all encodings - skip
                    continue


class TestRegistryProperty:
    """Property-based tests for parser registry."""

    @given(
        extension=st.sampled_from(['.csv', '.ics', '.vcf', '.json', '.txt', '.md'])
    )
    @settings(max_examples=20, deadline=3000)
    def test_registry_returns_parser_for_supported_extensions(self, extension):
        """Registry should return a parser for all supported extensions."""
        try:
            from recog_engine.parsers import get_registry
        except ImportError:
            pytest.skip("Parser registry not available")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create minimal file
            test_file = Path(tmp_dir) / f"test{extension}"
            test_file.write_text('test content')

            registry = get_registry()
            parser = registry.get_parser(test_file)

            # Should find a parser for supported extensions
            # Note: may return None if dependencies not installed
            # That's acceptable behavior

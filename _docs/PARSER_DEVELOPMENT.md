# ReCog Parser Development Guide

How to add support for new file formats in ReCog.

---

## Overview

ReCog uses a plugin-style parser architecture. Each file format has a dedicated parser class that:

1. Detects if it can handle a given file
2. Extracts text content and metadata
3. Returns a standardized `ParsedContent` object

```
File → Parser.can_parse() → Parser.parse() → ParsedContent → ReCog Pipeline
```

---

## Quick Start

### 1. Create Parser File

Create `_scripts/ingestion/parsers/myformat.py`:

```python
"""
MyFormat parser for .xyz files.
"""

from pathlib import Path
from typing import List

from .base import BaseParser
from ..types import ParsedContent


class MyFormatParser(BaseParser):
    """Parse .xyz files."""

    def get_extensions(self) -> List[str]:
        return [".xyz"]

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.get_extensions()

    def get_file_type(self) -> str:
        return "myformat"

    def parse(self, path: Path) -> ParsedContent:
        # Read and process the file
        text = path.read_text(encoding="utf-8")

        return ParsedContent(
            text=text,
            title=path.stem,
            metadata={"format": "myformat"}
        )
```

### 2. Register Parser

Edit `_scripts/ingestion/parsers/base.py`:

```python
# Add import
from .myformat import MyFormatParser

# Add to get_parser() parsers list
parsers = [
    PDFParser(),
    # ... existing parsers ...
    MyFormatParser(),  # Add before PlaintextParser
    PlaintextParser(),
]

# Add to get_all_parsers() too
```

### 3. Update Format Definitions (Optional)

Edit `_scripts/ingestion/universal.py` if you want detection guidance:

```python
SUPPORTED_FORMATS = {
    # ... existing ...
    ".xyz": ("MyFormat Document", "myformat"),
}
```

### 4. Test

```bash
cd _scripts
python -c "
from ingestion import detect_file, ingest_file
result = detect_file('test.xyz')
print(f'Supported: {result.supported}')
print(f'Parser: {result.parser_name}')
"
```

---

## Architecture

### Directory Structure

```
_scripts/ingestion/
├── __init__.py          # Public exports
├── types.py             # Data classes (ParsedContent, etc.)
├── universal.py         # File detection and ingestion
├── chunker.py           # Text chunking for large docs
├── service.py           # High-level ingestion service
└── parsers/
    ├── __init__.py
    ├── base.py          # BaseParser ABC + registry
    ├── pdf.py           # PDF parser (pypdf)
    ├── excel.py         # Excel parser (openpyxl)
    ├── csv_parser.py    # CSV parser
    ├── markdown.py      # Markdown parser
    ├── plaintext.py     # Plain text fallback
    ├── messages.py      # Chat/SMS parser
    └── json_export.py   # ChatGPT export parser
```

### BaseParser Interface

Every parser must implement these methods:

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

class BaseParser(ABC):

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Return True if this parser can handle the file."""
        pass

    @abstractmethod
    def parse(self, path: Path) -> ParsedContent:
        """Parse file and return content."""
        pass

    @abstractmethod
    def get_file_type(self) -> str:
        """Return identifier like 'pdf', 'excel', 'email'."""
        pass

    def get_extensions(self) -> List[str]:
        """Return list of extensions like ['.pdf', '.PDF']."""
        return []
```

### ParsedContent Class

The standard return type for all parsers:

```python
@dataclass
class ParsedContent:
    text: str                           # Required: extracted text
    metadata: Dict[str, Any] = {}       # Format-specific metadata
    pages: Optional[List[str]] = None   # For paginated docs (PDFs)

    # Standard metadata fields
    title: Optional[str] = None         # Document title
    author: Optional[str] = None        # Author name
    date: Optional[str] = None          # Document date (ISO format)
    subject: Optional[str] = None       # Subject/description
    recipients: Optional[List[str]] = None  # For emails
```

---

## Complete Example: Email Parser

Here's a full example parsing `.eml` email files:

```python
"""
Email (.eml) parser.

Extracts email headers, body text, and attachments list.
"""

import email
from email.policy import default
from pathlib import Path
from typing import List, Optional

from .base import BaseParser
from ..types import ParsedContent


class EmailParser(BaseParser):
    """Parse email .eml files."""

    def get_extensions(self) -> List[str]:
        return [".eml"]

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".eml":
            return False
        # Optionally verify it's actually an email
        try:
            with open(path, 'rb') as f:
                first_line = f.readline().decode('utf-8', errors='ignore')
                return first_line.startswith(('From:', 'Received:', 'MIME-Version:'))
        except:
            return False

    def get_file_type(self) -> str:
        return "email"

    def parse(self, path: Path) -> ParsedContent:
        with open(path, 'rb') as f:
            msg = email.message_from_binary_file(f, policy=default)

        # Extract headers
        subject = msg.get('Subject', '')
        from_addr = msg.get('From', '')
        to_addr = msg.get('To', '')
        date = msg.get('Date', '')

        # Extract body
        body = self._get_body(msg)

        # Build text representation
        text_parts = [
            f"From: {from_addr}",
            f"To: {to_addr}",
            f"Subject: {subject}",
            f"Date: {date}",
            "",
            body,
        ]

        # Get attachment names
        attachments = []
        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                attachments.append(part.get_filename() or 'unnamed')

        return ParsedContent(
            text="\n".join(text_parts),
            title=subject or path.stem,
            author=from_addr,
            date=self._parse_date(date),
            recipients=self._parse_recipients(to_addr),
            metadata={
                "format": "email",
                "from": from_addr,
                "to": to_addr,
                "subject": subject,
                "attachments": attachments,
                "attachment_count": len(attachments),
            }
        )

    def _get_body(self, msg) -> str:
        """Extract email body, preferring plain text."""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    return part.get_content()
            # Fallback to HTML
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    return self._strip_html(part.get_content())
        else:
            return msg.get_content()
        return ""

    def _strip_html(self, html: str) -> str:
        """Basic HTML tag removal."""
        import re
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse email date to ISO format."""
        from email.utils import parsedate_to_datetime
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.date().isoformat()
        except:
            return None

    def _parse_recipients(self, to_str: str) -> List[str]:
        """Parse To header into list of addresses."""
        from email.utils import getaddresses
        return [addr for name, addr in getaddresses([to_str]) if addr]


__all__ = ["EmailParser"]
```

---

## Parser Priority

Parsers are checked in order. Place specific parsers before generic ones:

```python
parsers = [
    PDFParser(),           # Specific: .pdf only
    ExcelParser(),         # Specific: .xlsx, .xls
    CSVParser(),           # Check before plaintext (both handle .csv)
    JSONExportParser(),    # Check JSON structure before plaintext
    MessagesParser(),      # Check message patterns before plaintext
    PlaintextParser(),     # Generic fallback - handles .txt, .md, etc.
]
```

**Rule**: If your format could be mistaken for plain text, add your parser before `PlaintextParser`.

---

## Handling Dependencies

Use optional imports with graceful fallback:

```python
class MyParser(BaseParser):

    def can_parse(self, path: Path) -> bool:
        # Only claim we can parse if dependency is installed
        try:
            import mylib
            return path.suffix.lower() == ".xyz"
        except ImportError:
            return False

    def parse(self, path: Path) -> ParsedContent:
        try:
            import mylib
        except ImportError:
            return ParsedContent(
                text="[Parsing requires mylib: pip install mylib]",
                title=path.stem,
                metadata={"error": "mylib not installed"}
            )

        # ... actual parsing ...
```

Add dependencies to `requirements.txt`:

```
mylib>=1.0.0  # MyFormat support
```

---

## Testing Your Parser

### Unit Test Template

Create `_scripts/tests/test_myformat.py`:

```python
"""Tests for MyFormat parser."""

import pytest
from pathlib import Path
from ingestion.parsers.myformat import MyFormatParser


class TestMyFormatParser:

    def test_can_parse_correct_extension(self, tmp_path):
        parser = MyFormatParser()
        test_file = tmp_path / "test.xyz"
        test_file.write_text("content")

        assert parser.can_parse(test_file) is True

    def test_cannot_parse_wrong_extension(self, tmp_path):
        parser = MyFormatParser()
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        assert parser.can_parse(test_file) is False

    def test_parse_extracts_text(self, tmp_path):
        parser = MyFormatParser()
        test_file = tmp_path / "test.xyz"
        test_file.write_text("Hello World")

        result = parser.parse(test_file)

        assert "Hello World" in result.text
        assert result.title == "test"

    def test_parse_handles_metadata(self, tmp_path):
        parser = MyFormatParser()
        test_file = tmp_path / "test.xyz"
        test_file.write_text("content")

        result = parser.parse(test_file)

        assert result.metadata.get("format") == "myformat"

    def test_get_extensions(self):
        parser = MyFormatParser()
        assert ".xyz" in parser.get_extensions()

    def test_get_file_type(self):
        parser = MyFormatParser()
        assert parser.get_file_type() == "myformat"
```

### Run Tests

```bash
cd _scripts
pytest tests/test_myformat.py -v
```

### Integration Test

```bash
# Test detection
python -c "
from ingestion import detect_file
result = detect_file('sample.xyz')
print(f'Supported: {result.supported}')
print(f'Type: {result.file_type}')
"

# Test parsing
python -c "
from ingestion import ingest_file
docs = ingest_file('sample.xyz')
print(f'Extracted: {len(docs[0].content)} chars')
"
```

---

## Best Practices

### Text Extraction

1. **Preserve structure**: Keep paragraphs, lists, headings separate
2. **Clean artifacts**: Remove binary garbage, fix encoding issues
3. **Normalize whitespace**: Collapse multiple spaces/newlines

```python
def _clean_text(self, text: str) -> str:
    import re
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Collapse multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)
    # Collapse multiple newlines (keep paragraph breaks)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
```

### Metadata Extraction

Extract anything useful for analysis:

```python
metadata = {
    # Required
    "format": "myformat",

    # Recommended
    "page_count": 10,
    "word_count": len(text.split()),
    "char_count": len(text),

    # Format-specific
    "version": "1.0",
    "encoding": "utf-8",
    "has_images": True,
}
```

### Error Handling

Never crash - return graceful errors:

```python
def parse(self, path: Path) -> ParsedContent:
    try:
        # ... parsing logic ...
    except UnicodeDecodeError as e:
        return ParsedContent(
            text=f"[Encoding error: {e}]",
            title=path.stem,
            metadata={"error": "encoding", "details": str(e)}
        )
    except Exception as e:
        return ParsedContent(
            text=f"[Parse error: {e}]",
            title=path.stem,
            metadata={"error": "parse_failed", "details": str(e)}
        )
```

### Large Files

For large files, consider streaming or chunking:

```python
def parse(self, path: Path) -> ParsedContent:
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB

    if path.stat().st_size > MAX_SIZE:
        # Stream or warn
        return ParsedContent(
            text="[File too large - processing first 10MB]",
            metadata={"truncated": True}
        )

    # Normal processing
    ...
```

---

## Checklist

Before submitting a new parser:

- [ ] Implements all `BaseParser` methods
- [ ] Registered in `base.py` `get_parser()` and `get_all_parsers()`
- [ ] Added to `SUPPORTED_FORMATS` in `universal.py` (if applicable)
- [ ] Dependencies added to `requirements.txt` with version constraints
- [ ] Graceful handling of missing dependencies
- [ ] Error handling for corrupted/invalid files
- [ ] Unit tests covering normal and edge cases
- [ ] Integration test with `detect_file()` and `ingest_file()`
- [ ] Docstring with usage example

---

## Existing Parsers Reference

| Parser | Extensions | Dependencies | Notes |
|--------|------------|--------------|-------|
| `PDFParser` | `.pdf` | `pypdf` | Extracts text and metadata |
| `ExcelParser` | `.xlsx`, `.xls`, `.xlsm` | `openpyxl` | All sheets as text |
| `CSVParser` | `.csv` | (builtin) | Handles various delimiters |
| `MarkdownParser` | `.md`, `.markdown` | (builtin) | Preserves structure |
| `PlaintextParser` | `.txt`, `.text`, others | (builtin) | Fallback parser |
| `MessagesParser` | `.txt`, `.xml` | (builtin) | WhatsApp, SMS exports |
| `JSONExportParser` | `.json` | (builtin) | ChatGPT exports |
| `MboxParser` | `.mbox` | (builtin) | Email archives |

---

## Getting Help

- Check existing parsers in `_scripts/ingestion/parsers/` for patterns
- Open an issue at [github.com/brentyJ/recog/issues](https://github.com/brentyJ/recog/issues)
- Email: brent@ehkolabs.io

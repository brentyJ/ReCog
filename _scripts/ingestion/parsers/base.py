"""
Base parser interface and factory.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List

from ..types import ParsedContent


class BaseParser(ABC):
    """Abstract base for document parsers."""
    
    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Check if this parser can handle the file."""
        pass
    
    @abstractmethod
    def parse(self, path: Path) -> ParsedContent:
        """Parse the file and return content."""
        pass
    
    @abstractmethod
    def get_file_type(self) -> str:
        """Return the file type identifier."""
        pass
    
    def get_extensions(self) -> List[str]:
        """Return list of file extensions this parser handles."""
        return []


def get_parser(path: Path) -> Optional[BaseParser]:
    """
    Get appropriate parser for a file.
    
    Args:
        path: Path to file
    
    Returns:
        Parser instance or None if unsupported
    """
    from .pdf import PDFParser
    from .markdown import MarkdownParser
    from .plaintext import PlaintextParser
    from .messages import MessagesParser
    from .json_export import JSONExportParser
    from .excel import ExcelParser
    
    parsers = [
        PDFParser(),
        MarkdownParser(),
        ExcelParser(),       # Check Excel before plaintext
        JSONExportParser(),  # Check JSON before plaintext
        MessagesParser(),    # Check before plaintext (txt files might be messages)
        PlaintextParser(),
    ]
    
    for parser in parsers:
        if parser.can_parse(path):
            return parser
    
    return None


def get_all_parsers() -> List[BaseParser]:
    """Get list of all available parsers."""
    from .pdf import PDFParser
    from .markdown import MarkdownParser
    from .plaintext import PlaintextParser
    from .messages import MessagesParser
    from .json_export import JSONExportParser
    from .excel import ExcelParser
    
    return [
        PDFParser(),
        MarkdownParser(),
        ExcelParser(),
        JSONExportParser(),
        MessagesParser(),
        PlaintextParser(),
    ]


def get_supported_extensions() -> List[str]:
    """Get all supported file extensions."""
    extensions = set()
    for parser in get_all_parsers():
        extensions.update(parser.get_extensions())
    return sorted(extensions)


__all__ = [
    "BaseParser",
    "get_parser",
    "get_all_parsers",
    "get_supported_extensions",
]

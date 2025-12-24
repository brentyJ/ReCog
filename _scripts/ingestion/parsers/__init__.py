"""
Document parsers for various file formats.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from .base import BaseParser, get_parser, get_all_parsers, get_supported_extensions
from .pdf import PDFParser
from .markdown import MarkdownParser
from .plaintext import PlaintextParser
from .messages import MessagesParser
from .json_export import JSONExportParser
from .excel import ExcelParser

__all__ = [
    "BaseParser",
    "get_parser",
    "get_all_parsers",
    "get_supported_extensions",
    "PDFParser",
    "MarkdownParser",
    "PlaintextParser",
    "MessagesParser",
    "JSONExportParser",
    "ExcelParser",
]

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
from .csv_parser import CSVParser
from .csv_enhanced import EnhancedCSVParser
from .mbox import MboxParser
from .docx import DocxParser
from .email import EmlParser, MsgParser
from .archive import ArchiveParser
from .calendar import ICSParser
from .contacts import VCFParser
from .notion import NotionParser
from .instagram import InstagramHTMLParser

__all__ = [
    "BaseParser",
    "get_parser",
    "get_all_parsers",
    "get_supported_extensions",
    "PDFParser",
    "DocxParser",
    "MarkdownParser",
    "PlaintextParser",
    "MessagesParser",
    "JSONExportParser",
    "ExcelParser",
    "CSVParser",
    "EnhancedCSVParser",
    "MboxParser",
    "EmlParser",
    "MsgParser",
    "ArchiveParser",
    "ICSParser",
    "VCFParser",
    "NotionParser",
    "InstagramHTMLParser",
]

"""
ReCog Ingestion - File Parsing and Chunking

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
"""

from .types import (
    ParsedContent,
    DocumentChunk,
    IngestedDocument,
    FileDetectionResult,
)

from .chunker import Chunker

from .universal import (
    UniversalDetector,
    detect_file,
    ingest_file,
    get_format_info,
)

from .parsers import (
    BaseParser,
    get_parser,
    get_all_parsers,
    get_supported_extensions,
)


__all__ = [
    # Types
    "ParsedContent",
    "DocumentChunk",
    "IngestedDocument",
    "FileDetectionResult",
    # Chunking
    "Chunker",
    # Universal detection
    "UniversalDetector",
    "detect_file",
    "ingest_file",
    "get_format_info",
    # Parsers
    "BaseParser",
    "get_parser",
    "get_all_parsers",
    "get_supported_extensions",
]

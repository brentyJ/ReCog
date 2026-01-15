"""
Parser registry and format detection system.

This module provides a unified interface for parsing various file formats
with automatic format detection, platform export recognition, and graceful
error handling.

Usage:
    from recog_engine.parsers import get_registry, ParseResult

    # Parse a file
    registry = get_registry()
    result = registry.parse(Path("export.zip"))

    if result.success:
        print(result.data)
    else:
        for warning in result.warnings:
            print(f"Warning: {warning}")

    # Check format without parsing
    from recog_engine.parsers import detect_format
    mime_type, platform_type = detect_format(Path("export.zip"))

    # Register a custom parser
    from recog_engine.parsers import register_parser, BaseParser

    @register_parser
    class MyCustomParser(BaseParser):
        ...

    # Or for platform-specific parsers
    @register_parser(platform='my_platform')
    class MyPlatformParser(BaseParser):
        ...

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from .base import BaseParser, ParseResult
from .registry import (
    ParserRegistry,
    get_registry,
    register_parser,
    LegacyParserWrapper,
)
from .detector import (
    FormatDetector,
    detect_format,
    get_detector,
)

__all__ = [
    # Base classes
    "BaseParser",
    "ParseResult",

    # Registry
    "ParserRegistry",
    "get_registry",
    "register_parser",
    "LegacyParserWrapper",

    # Detection
    "FormatDetector",
    "detect_format",
    "get_detector",
]

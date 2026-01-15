"""
Parser registry with automatic registration and format routing.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from typing import Dict, List, Type, Optional, Callable
from pathlib import Path
import logging

from .base import BaseParser, ParseResult
from .detector import FormatDetector

logger = logging.getLogger(__name__)


class ParserRegistry:
    """
    Central registry of all available parsers.

    Handles:
    - Parser registration (by MIME type or platform)
    - Format detection and parser selection
    - Parse execution with error handling

    Usage:
        registry = get_registry()

        # Register a parser
        registry.register(MyParser)

        # Or use decorator
        @register_parser
        class MyParser(BaseParser):
            ...

        # Parse a file
        result = registry.parse(Path("export.zip"))
    """

    def __init__(self):
        # MIME type -> parser class mapping
        self._mime_parsers: Dict[str, Type[BaseParser]] = {}

        # Platform name -> parser class mapping
        self._platform_parsers: Dict[str, Type[BaseParser]] = {}

        # Extension -> parser class mapping (fallback)
        self._extension_parsers: Dict[str, Type[BaseParser]] = {}

        # Format detector
        self.detector = FormatDetector()

    def register(
        self,
        parser_class: Type[BaseParser],
        platform_name: Optional[str] = None
    ) -> None:
        """
        Register a parser class.

        Args:
            parser_class: Parser class to register
            platform_name: If set, register as platform-specific parser
        """
        parser_name = parser_class.__name__

        if platform_name:
            # Register as platform-specific parser
            self._platform_parsers[platform_name] = parser_class
            logger.info(f"Registered platform parser: {parser_name} for {platform_name}")
        else:
            # Register by MIME type
            instance = parser_class()
            for mime_type in instance.supported_formats:
                self._mime_parsers[mime_type] = parser_class
                logger.info(f"Registered MIME parser: {parser_name} for {mime_type}")

            # Also register by extension
            for ext in instance.supported_extensions:
                self._extension_parsers[ext.lower()] = parser_class

    def register_legacy_parser(
        self,
        parser_instance,
        mime_types: List[str],
        extensions: List[str]
    ) -> None:
        """
        Register an existing (legacy) parser instance.

        Wraps parsers from ingestion/parsers/ that don't follow the new interface.

        Args:
            parser_instance: Existing parser instance
            mime_types: MIME types this parser handles
            extensions: Extensions this parser handles
        """
        wrapper = LegacyParserWrapper(parser_instance, mime_types, extensions)
        parser_name = parser_instance.__class__.__name__

        for mime_type in mime_types:
            self._mime_parsers[mime_type] = type(wrapper)
            logger.info(f"Registered legacy parser: {parser_name} for {mime_type}")

        for ext in extensions:
            self._extension_parsers[ext.lower()] = type(wrapper)

    def get_parser(self, file_path: Path) -> Optional[BaseParser]:
        """
        Detect format and return appropriate parser instance.

        Priority:
        1. Platform-specific parsers (for recognized exports)
        2. MIME type parsers (content-based)
        3. Extension parsers (fallback)

        Args:
            file_path: Path to file

        Returns:
            Parser instance or None if no parser found
        """
        mime_type, platform_type = self.detector.detect(file_path)

        logger.info(
            f"Detected: MIME={mime_type}, Platform={platform_type} "
            f"for {file_path.name}"
        )

        # 1. Try platform-specific parser first
        if platform_type and platform_type in self._platform_parsers:
            parser_class = self._platform_parsers[platform_type]
            parser = parser_class()
            if parser.can_parse(file_path, mime_type):
                logger.info(f"Using platform parser: {parser_class.__name__}")
                return parser

        # 2. Try MIME type parser
        if mime_type in self._mime_parsers:
            parser_class = self._mime_parsers[mime_type]
            parser = parser_class()
            if parser.can_parse(file_path, mime_type):
                logger.info(f"Using MIME parser: {parser_class.__name__}")
                return parser

        # 3. Fallback to extension parser
        ext = file_path.suffix.lower()
        if ext in self._extension_parsers:
            parser_class = self._extension_parsers[ext]
            parser = parser_class()
            if parser.can_parse(file_path, mime_type):
                logger.info(f"Using extension parser: {parser_class.__name__}")
                return parser

        logger.warning(f"No parser found for {mime_type} ({file_path.name})")
        return None

    def parse(self, file_path: Path, **options) -> ParseResult:
        """
        Main entry point: detect format, select parser, execute parse.

        Returns ParseResult with graceful degradation on errors.

        Args:
            file_path: Path to file
            **options: Parser-specific options

        Returns:
            ParseResult with data and any warnings
        """
        parser = self.get_parser(file_path)

        if not parser:
            return ParseResult.failure(
                f"No parser available for file type: {file_path.suffix}"
            )

        try:
            result = parser.parse(file_path, **options)

            # Log version if detected
            version = parser.detect_version(file_path)
            if version:
                result.metadata['format_version'] = version
                logger.info(f"Detected format version: {version}")

            return result

        except Exception as e:
            logger.error(
                f"Parser {parser.__class__.__name__} failed: {e}",
                exc_info=True
            )
            return ParseResult.failure(f"Parse failed: {str(e)}")

    def list_parsers(self) -> Dict[str, List[str]]:
        """
        List all registered parsers and their supported formats.

        Returns:
            Dict with 'mime', 'platform', and 'extension' keys
        """
        return {
            'mime': list(self._mime_parsers.keys()),
            'platform': list(self._platform_parsers.keys()),
            'extension': list(self._extension_parsers.keys()),
        }

    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions."""
        return sorted(self._extension_parsers.keys())


class LegacyParserWrapper(BaseParser):
    """
    Wrapper to adapt legacy parsers to the new interface.

    Allows existing ingestion/parsers/ parsers to work with the registry.
    """

    def __init__(self, legacy_parser, mime_types: List[str], extensions: List[str]):
        self._legacy = legacy_parser
        self._mime_types = mime_types
        self._extensions = extensions

    @property
    def supported_formats(self) -> List[str]:
        return self._mime_types

    @property
    def supported_extensions(self) -> List[str]:
        return self._extensions

    def can_parse(self, file_path: Path, mime_type: Optional[str] = None) -> bool:
        return self._legacy.can_parse(file_path)

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            # Call legacy parser
            parsed = self._legacy.parse(file_path)

            # Convert ParsedContent to ParseResult
            return ParseResult(
                success=True,
                data={
                    'text': parsed.text,
                    'title': parsed.title,
                    'author': parsed.author,
                    'date': parsed.date,
                },
                metadata=parsed.metadata
            )
        except Exception as e:
            return ParseResult.failure(str(e))


# Global registry instance
_registry: Optional[ParserRegistry] = None


def get_registry() -> ParserRegistry:
    """Get the global parser registry (lazy initialized)."""
    global _registry
    if _registry is None:
        _registry = ParserRegistry()
        _register_builtin_parsers(_registry)
    return _registry


def register_parser(
    parser_class: Optional[Type[BaseParser]] = None,
    platform: Optional[str] = None
) -> Callable:
    """
    Decorator to auto-register parsers.

    Usage:
        @register_parser
        class MyParser(BaseParser):
            ...

        @register_parser(platform='facebook')
        class FacebookParser(BaseParser):
            ...
    """
    def decorator(cls: Type[BaseParser]) -> Type[BaseParser]:
        get_registry().register(cls, platform_name=platform)
        return cls

    if parser_class is not None:
        # Called without arguments: @register_parser
        return decorator(parser_class)
    else:
        # Called with arguments: @register_parser(platform='...')
        return decorator


def _register_builtin_parsers(registry: ParserRegistry) -> None:
    """Register built-in parsers from ingestion/parsers/."""
    try:
        # Import and wrap existing parsers
        from ingestion.parsers.archive import ArchiveParser
        from ingestion.parsers.calendar import ICSParser
        from ingestion.parsers.contacts import VCFParser
        from ingestion.parsers.csv_enhanced import EnhancedCSVParser
        from ingestion.parsers.pdf import PDFParser
        from ingestion.parsers.markdown import MarkdownParser
        from ingestion.parsers.plaintext import PlaintextParser
        from ingestion.parsers.excel import ExcelParser
        from ingestion.parsers.json_export import JSONExportParser
        from ingestion.parsers.mbox import MboxParser
        from ingestion.parsers.docx import DocxParser
        from ingestion.parsers.email import EmlParser, MsgParser
        from ingestion.parsers.notion import NotionParser

        # Register each parser with its MIME types and extensions
        parser_configs = [
            (ArchiveParser(), ['application/zip', 'application/x-tar'], ['.zip', '.tar', '.tar.gz', '.tgz']),
            (ICSParser(), ['text/calendar'], ['.ics', '.ical']),
            (VCFParser(), ['text/vcard'], ['.vcf']),
            (EnhancedCSVParser(), ['text/csv'], ['.csv']),
            (PDFParser(), ['application/pdf'], ['.pdf']),
            (MarkdownParser(), ['text/markdown'], ['.md', '.markdown']),
            (PlaintextParser(), ['text/plain'], ['.txt', '.text']),
            (ExcelParser(), ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'], ['.xlsx', '.xls', '.xlsm']),
            (JSONExportParser(), ['application/json'], ['.json']),
            (MboxParser(), ['application/mbox'], ['.mbox']),
            (DocxParser(), ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'], ['.docx']),
            (EmlParser(), ['message/rfc822'], ['.eml']),
            (MsgParser(), ['application/vnd.ms-outlook'], ['.msg']),
            (NotionParser(), ['application/x-notion'], []),  # Notion detected by structure
        ]

        for parser, mime_types, extensions in parser_configs:
            registry.register_legacy_parser(parser, mime_types, extensions)

        logger.info(f"Registered {len(parser_configs)} built-in parsers")

    except ImportError as e:
        logger.warning(f"Could not import built-in parsers: {e}")


__all__ = [
    "ParserRegistry",
    "get_registry",
    "register_parser",
    "LegacyParserWrapper",
]

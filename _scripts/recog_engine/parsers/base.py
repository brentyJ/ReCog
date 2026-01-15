"""
Parser base classes and result types.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """
    Standardized parser output with graceful degradation support.

    Attributes:
        success: Whether parsing completed successfully
        data: Structured data (dict, list, DataFrame, etc.)
        format_version: Detected format version (e.g., "vCard 3.0", "ICS 2.0")
        warnings: Non-fatal issues encountered during parsing
        metadata: Additional information about the parse (timing, stats, etc.)
    """
    success: bool
    data: Any  # Structured data (dict, list, DataFrame, etc)
    format_version: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)
        logger.warning(f"Parse warning: {warning}")

    def has_warnings(self) -> bool:
        """Check if any warnings were recorded."""
        return len(self.warnings) > 0

    @classmethod
    def failure(cls, message: str, **metadata) -> "ParseResult":
        """Create a failure result with a single warning."""
        return cls(
            success=False,
            data=None,
            warnings=[message],
            metadata=metadata
        )

    @classmethod
    def partial(cls, data: Any, warnings: List[str], **metadata) -> "ParseResult":
        """Create a partial success result (data with warnings)."""
        return cls(
            success=True,
            data=data,
            warnings=warnings,
            metadata=metadata
        )


class BaseParser(ABC):
    """
    Base interface all parsers must implement.

    Parsers should:
    - Detect if they can handle a file (can_parse)
    - Parse files and return structured data (parse)
    - Handle errors gracefully and return partial results when possible
    - Log format versions for debugging
    """

    @property
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """MIME types this parser handles."""
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """File extensions this parser handles (including dot, e.g. '.zip')."""
        pass

    @abstractmethod
    def can_parse(self, file_path: Path, mime_type: Optional[str] = None) -> bool:
        """
        Check if this parser can handle the file.

        Args:
            file_path: Path to the file
            mime_type: Optional MIME type (if already detected)

        Returns:
            True if this parser can handle the file
        """
        pass

    @abstractmethod
    def parse(self, file_path: Path, **options) -> ParseResult:
        """
        Parse the file and return structured data.

        Should handle errors gracefully and return partial results when possible.
        Use ParseResult.partial() for files that parse with warnings.
        Use ParseResult.failure() for complete failures.

        Args:
            file_path: Path to the file
            **options: Parser-specific options

        Returns:
            ParseResult with data and any warnings
        """
        pass

    def detect_version(self, file_path: Path) -> Optional[str]:
        """
        Optional: Detect format version for logging/debugging.

        Examples: "vCard 3.0", "ICS 2.0", "ZIP 2.0"
        """
        return None

    @property
    def name(self) -> str:
        """Return parser class name."""
        return self.__class__.__name__


__all__ = [
    "ParseResult",
    "BaseParser",
]

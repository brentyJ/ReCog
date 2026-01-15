"""
Content-based and structure-based format detection.

Uses python-magic for MIME type detection and custom logic
for platform export identification.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import zipfile
import re
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FormatDetector:
    """
    Content-based and structure-based format detection.

    Provides two levels of detection:
    1. MIME type detection via python-magic (content-based)
    2. Platform export detection via internal structure analysis

    Usage:
        detector = FormatDetector()
        mime_type, platform_type = detector.detect(Path("export.zip"))
    """

    def __init__(self):
        self._magic = None

    @property
    def magic(self):
        """Lazy-load python-magic."""
        if self._magic is None:
            try:
                import magic
                self._magic = magic.Magic(mime=True)
            except ImportError:
                logger.warning(
                    "python-magic not installed. "
                    "Install with: pip install python-magic"
                )
                self._magic = False  # Mark as unavailable
        return self._magic

    def detect_mime_type(self, file_path: Path) -> str:
        """
        Detect MIME type from file contents.

        Uses python-magic for accurate content-based detection.
        Falls back to extension-based detection if magic is unavailable.

        Args:
            file_path: Path to file

        Returns:
            MIME type string (e.g., "application/zip")
        """
        # Try python-magic first
        if self.magic:
            try:
                return self.magic.from_file(str(file_path))
            except Exception as e:
                logger.error(f"Magic detection failed for {file_path}: {e}")

        # Fallback to extension-based detection
        return self._mime_from_extension(file_path)

    def _mime_from_extension(self, file_path: Path) -> str:
        """Fallback MIME type detection from extension."""
        extension_map = {
            '.zip': 'application/zip',
            '.tar': 'application/x-tar',
            '.gz': 'application/gzip',
            '.tgz': 'application/gzip',
            '.7z': 'application/x-7z-compressed',
            '.rar': 'application/vnd.rar',
            '.pdf': 'application/pdf',
            '.json': 'application/json',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.xml': 'application/xml',
            '.html': 'text/html',
            '.htm': 'text/html',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ics': 'text/calendar',
            '.vcf': 'text/vcard',
            '.eml': 'message/rfc822',
            '.mbox': 'application/mbox',
        }

        suffix = file_path.suffix.lower()
        return extension_map.get(suffix, 'application/octet-stream')

    def detect_platform_export(self, file_path: Path) -> Optional[str]:
        """
        Detect social media/platform export by internal structure.

        Analyzes ZIP archive contents to identify exports from:
        - Facebook (messages/inbox/ structure)
        - Instagram (instagram_ prefix pattern)
        - Twitter (data/tweet.js pattern)
        - Google Takeout (Takeout/ root directory)
        - Notion (UUID pattern in filenames)
        - ChatGPT (conversations.json)
        - WhatsApp (chat export patterns)
        - LinkedIn (Connections.csv, Messages.csv)

        Args:
            file_path: Path to archive file

        Returns:
            Platform name or None if not recognized
        """
        if not zipfile.is_zipfile(file_path):
            return None

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                names = zf.namelist()
                names_lower = [n.lower() for n in names]
                names_set = set(names)

                # Facebook: messages/inbox/ structure
                if any('messages/inbox/' in n for n in names):
                    return 'facebook'

                # Instagram: instagram_ prefix or media/posts pattern
                if any('instagram_' in n.lower() for n in names):
                    return 'instagram'
                if any('media/posts/' in n for n in names):
                    return 'instagram'

                # Twitter: data/tweet.js or data/tweets.js pattern
                if any('data/tweet.js' in n or 'data/tweets.js' in n for n in names):
                    return 'twitter'
                if any(n.endswith('tweet.js') or n.endswith('tweets.js') for n in names):
                    return 'twitter'

                # Google Takeout: Takeout/ root directory
                if any(n.startswith('Takeout/') for n in names):
                    return 'google_takeout'

                # Notion: UUID pattern in filenames (32 hex chars before extension)
                uuid_pattern = re.compile(r'[a-f0-9]{32}\.(md|csv)$')
                if any(uuid_pattern.search(n) for n in names):
                    return 'notion'

                # ChatGPT: conversations.json
                if 'conversations.json' in names_set:
                    return 'chatgpt'

                # LinkedIn: Connections.csv or messages.csv
                if any('connections.csv' in n.lower() for n in names):
                    return 'linkedin'
                if any('messages.csv' in n.lower() and 'linkedin' in n.lower() for n in names):
                    return 'linkedin'

                # WhatsApp: _chat.txt or WhatsApp Chat patterns
                if any('_chat.txt' in n or 'whatsapp chat' in n.lower() for n in names):
                    return 'whatsapp'

                # Spotify: StreamingHistory or endsong files
                if any('streaminghistory' in n.lower() for n in names):
                    return 'spotify'
                if any('endsong' in n.lower() for n in names):
                    return 'spotify'

                # Apple: Health export
                if any('apple_health_export' in n.lower() for n in names):
                    return 'apple_health'
                if any('export.xml' in n and 'health' in n.lower() for n in names):
                    return 'apple_health'

        except Exception as e:
            logger.error(f"Platform detection failed for {file_path}: {e}")

        return None

    def detect(self, file_path: Path) -> Tuple[str, Optional[str]]:
        """
        Full detection: MIME type + platform export type.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (mime_type, platform_type)
            platform_type is None for non-archive or unrecognized archives
        """
        mime_type = self.detect_mime_type(file_path)
        platform_type = None

        # Check for platform exports in archives
        if mime_type in ('application/zip', 'application/x-zip-compressed'):
            platform_type = self.detect_platform_export(file_path)

        logger.debug(
            f"Detected: MIME={mime_type}, Platform={platform_type} "
            f"for {file_path.name}"
        )

        return mime_type, platform_type

    def is_archive(self, file_path: Path) -> bool:
        """Check if file is an archive format."""
        mime_type = self.detect_mime_type(file_path)
        archive_mimes = {
            'application/zip',
            'application/x-zip-compressed',
            'application/x-tar',
            'application/gzip',
            'application/x-7z-compressed',
            'application/vnd.rar',
        }
        return mime_type in archive_mimes

    def is_text(self, file_path: Path) -> bool:
        """Check if file is a text format."""
        mime_type = self.detect_mime_type(file_path)
        return mime_type.startswith('text/') or mime_type == 'application/json'


# Global detector instance
_detector = FormatDetector()


def detect_format(file_path: Path) -> Tuple[str, Optional[str]]:
    """
    Convenience function for format detection.

    Args:
        file_path: Path to file

    Returns:
        Tuple of (mime_type, platform_type)
    """
    return _detector.detect(file_path)


def get_detector() -> FormatDetector:
    """Get the global detector instance."""
    return _detector


__all__ = [
    "FormatDetector",
    "detect_format",
    "get_detector",
]

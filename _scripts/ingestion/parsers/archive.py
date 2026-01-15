"""
Archive parser for ZIP and TAR files.

Handles compressed archives and detects platform exports
(Facebook, Google Takeout, Twitter, Instagram).

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import zipfile
import tarfile
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

from .base import BaseParser
from ..types import ParsedContent


class ArchiveParser(BaseParser):
    """
    Parse ZIP and TAR archives.

    Extracts contents, detects known platform exports,
    and processes contained files with appropriate parsers.
    """

    PARSER_METADATA = {
        "file_type": "Archive (ZIP/TAR)",
        "extensions": [".zip", ".tar", ".tar.gz", ".tgz"],
        "cypher_context": {
            "description": "Compressed archive that may contain platform exports or document collections",
            "requires_user_input": [],
            "extractable": [
                "Facebook/Instagram export analysis",
                "Google Takeout data extraction",
                "Twitter archive insights",
                "Multiple document analysis"
            ],
            "suggestions": [
                "I'll extract and identify the contents automatically",
                "Large archives (>100MB) may take 2-5 minutes to process",
                "If this is a known export (Facebook, Google, Twitter), I'll use specialized parsing"
            ],
            "privacy_warning": "Archives may contain years of personal data across multiple file types"
        }
    }

    # File extensions to skip (media, binary)
    SKIP_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.ico', '.svg',
        '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.wav', '.flac', '.m4a',
        '.exe', '.dll', '.so', '.dylib', '.bin',
        '.pyc', '.pyo', '.class', '.o', '.obj',
        '.db', '.sqlite', '.sqlite3',
    }

    # Maximum extracted size (500MB)
    MAX_EXTRACTED_SIZE = 500 * 1024 * 1024

    def get_extensions(self) -> List[str]:
        return [".zip", ".tar", ".tar.gz", ".tgz"]

    def can_parse(self, path: Path) -> bool:
        """Check if this is a supported archive."""
        suffix = path.suffix.lower()
        name = path.name.lower()

        # Handle .tar.gz
        if name.endswith('.tar.gz'):
            return True

        return suffix in ['.zip', '.tar', '.tgz']

    def get_file_type(self) -> str:
        return "archive"

    def parse(self, path: Path) -> ParsedContent:
        """
        Parse archive contents.

        Extracts to temporary directory, detects format,
        and processes contained files.
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract archive
                extracted_size = self._extract_archive(path, temp_path)

                if extracted_size > self.MAX_EXTRACTED_SIZE:
                    return ParsedContent(
                        text=f"[Archive too large: {extracted_size / 1024 / 1024:.1f}MB extracted (limit: 500MB)]",
                        title=path.stem,
                        metadata={
                            "error": "archive_too_large",
                            "extracted_size": extracted_size,
                            "format": self._detect_archive_type(path),
                        }
                    )

                # Detect platform export format
                export_format = self._detect_export_format(temp_path)

                if export_format:
                    return self._handle_platform_export(temp_path, export_format, path)

                # Generic archive: process all supported files
                return self._process_generic_archive(temp_path, path)

        except zipfile.BadZipFile:
            return ParsedContent(
                text="[Corrupted or invalid ZIP file]",
                title=path.stem,
                metadata={"error": "corrupted_archive", "format": "zip"}
            )
        except tarfile.TarError as e:
            return ParsedContent(
                text=f"[Invalid TAR archive: {e}]",
                title=path.stem,
                metadata={"error": "corrupted_archive", "format": "tar"}
            )
        except RuntimeError as e:
            # Encrypted archive
            if "encrypted" in str(e).lower():
                return ParsedContent(
                    text="[Encrypted archive - cannot extract without password]",
                    title=path.stem,
                    metadata={"error": "encrypted_archive"}
                )
            raise
        except Exception as e:
            return ParsedContent(
                text=f"[Archive extraction failed: {e}]",
                title=path.stem,
                metadata={"error": "extraction_failed", "details": str(e)}
            )

    def _detect_archive_type(self, path: Path) -> str:
        """Detect archive type from path."""
        name = path.name.lower()
        if name.endswith('.tar.gz') or name.endswith('.tgz'):
            return "tar.gz"
        elif path.suffix.lower() == '.tar':
            return "tar"
        else:
            return "zip"

    def _extract_archive(self, path: Path, dest: Path) -> int:
        """
        Extract archive to destination directory.

        Returns:
            Total extracted size in bytes.
        """
        archive_type = self._detect_archive_type(path)
        total_size = 0

        if archive_type == "zip":
            with zipfile.ZipFile(path, 'r') as zf:
                # Check for encrypted files
                for info in zf.infolist():
                    if info.flag_bits & 0x1:  # Encrypted flag
                        raise RuntimeError("Archive contains encrypted files")
                    total_size += info.file_size

                zf.extractall(dest)
        else:
            # TAR or TAR.GZ
            mode = 'r:gz' if archive_type == "tar.gz" else 'r'
            with tarfile.open(path, mode) as tf:
                # Security: prevent path traversal
                for member in tf.getmembers():
                    if member.name.startswith('/') or '..' in member.name:
                        raise RuntimeError(f"Unsafe path in archive: {member.name}")
                    total_size += member.size

                tf.extractall(dest)

        return total_size

    def _detect_export_format(self, directory: Path) -> Optional[str]:
        """
        Detect platform export by signature files/structure.

        Returns:
            'facebook', 'google_takeout', 'twitter', 'instagram', or None
        """
        # Facebook: has posts/your_posts_1.json or messages/inbox/
        if (directory / 'posts' / 'your_posts_1.json').exists():
            return 'facebook'
        if (directory / 'messages' / 'inbox').exists():
            return 'facebook'
        if (directory / 'your_facebook_activity').exists():
            return 'facebook'

        # Google Takeout: has Takeout/ root folder
        if (directory / 'Takeout').exists():
            return 'google_takeout'

        # Twitter: has data/tweets.js or data/tweet.js
        if (directory / 'data' / 'tweets.js').exists():
            return 'twitter'
        if (directory / 'data' / 'tweet.js').exists():
            return 'twitter'

        # Instagram: has media.json or content/posts_1.json
        if (directory / 'media.json').exists():
            return 'instagram'
        if (directory / 'content' / 'posts_1.json').exists():
            return 'instagram'

        # LinkedIn: has Connections.csv or messages.csv
        if (directory / 'Connections.csv').exists():
            return 'linkedin'

        return None

    def _handle_platform_export(self, directory: Path, export_format: str, original_path: Path) -> ParsedContent:
        """
        Handle known platform export formats.

        Future: Route to specialized parsers.
        For now: Return info about detected format and basic file inventory.
        """
        handlers = {
            'facebook': self._parse_facebook_export,
            'google_takeout': self._parse_google_takeout,
            'twitter': self._parse_twitter_export,
            'instagram': self._parse_instagram_export,
            'linkedin': self._parse_linkedin_export,
        }

        handler = handlers.get(export_format, self._process_generic_archive)

        if handler == self._process_generic_archive:
            return handler(directory, original_path)

        return handler(directory, original_path)

    def _parse_facebook_export(self, directory: Path, original_path: Path) -> ParsedContent:
        """
        Parse Facebook export.

        Future: Full Facebook parser implementation.
        For now: Inventory and basic extraction.
        """
        inventory = self._build_inventory(directory)

        # Try to extract some content
        text_parts = [
            "=== Facebook Export Detected ===",
            f"Archive: {original_path.name}",
            "",
            "Contents found:",
        ]

        # Check for messages
        messages_dir = directory / 'messages' / 'inbox'
        if messages_dir.exists():
            message_threads = list(messages_dir.iterdir())
            text_parts.append(f"- {len(message_threads)} message threads")

        # Check for posts
        posts_dir = directory / 'posts'
        if posts_dir.exists():
            posts_files = list(posts_dir.glob('*.json'))
            text_parts.append(f"- {len(posts_files)} posts files")

        # Check for comments
        comments_dir = directory / 'comments'
        if comments_dir.exists():
            text_parts.append("- Comments data present")

        # Check for profile
        if (directory / 'profile_information').exists():
            text_parts.append("- Profile information present")

        text_parts.extend([
            "",
            "Note: Full Facebook parsing coming soon. Currently showing inventory.",
            "",
            f"Total files: {inventory['total_files']}",
            f"Supported files: {inventory['supported_files']}",
        ])

        return ParsedContent(
            text="\n".join(text_parts),
            title=f"Facebook Export - {original_path.stem}",
            metadata={
                "detected_format": "facebook",
                "parser": "ArchiveParser",
                "archive_name": original_path.name,
                "inventory": inventory,
            }
        )

    def _parse_google_takeout(self, directory: Path, original_path: Path) -> ParsedContent:
        """
        Parse Google Takeout export.

        Future: Full Google Takeout parser implementation.
        """
        inventory = self._build_inventory(directory)
        takeout_dir = directory / 'Takeout'

        text_parts = [
            "=== Google Takeout Detected ===",
            f"Archive: {original_path.name}",
            "",
            "Services found:",
        ]

        if takeout_dir.exists():
            services = [d.name for d in takeout_dir.iterdir() if d.is_dir()]
            for service in sorted(services):
                text_parts.append(f"- {service}")

        text_parts.extend([
            "",
            "Note: Full Google Takeout parsing coming soon. Currently showing inventory.",
            "",
            f"Total files: {inventory['total_files']}",
            f"Supported files: {inventory['supported_files']}",
        ])

        return ParsedContent(
            text="\n".join(text_parts),
            title=f"Google Takeout - {original_path.stem}",
            metadata={
                "detected_format": "google_takeout",
                "parser": "ArchiveParser",
                "archive_name": original_path.name,
                "inventory": inventory,
            }
        )

    def _parse_twitter_export(self, directory: Path, original_path: Path) -> ParsedContent:
        """
        Parse Twitter archive.

        Future: Full Twitter parser implementation.
        """
        inventory = self._build_inventory(directory)

        text_parts = [
            "=== Twitter Archive Detected ===",
            f"Archive: {original_path.name}",
            "",
            "Data found:",
        ]

        data_dir = directory / 'data'
        if data_dir.exists():
            js_files = list(data_dir.glob('*.js'))
            for f in sorted(js_files)[:20]:  # Limit to first 20
                text_parts.append(f"- {f.stem}")

        text_parts.extend([
            "",
            "Note: Full Twitter parsing coming soon. Currently showing inventory.",
            "",
            f"Total files: {inventory['total_files']}",
            f"Supported files: {inventory['supported_files']}",
        ])

        return ParsedContent(
            text="\n".join(text_parts),
            title=f"Twitter Archive - {original_path.stem}",
            metadata={
                "detected_format": "twitter",
                "parser": "ArchiveParser",
                "archive_name": original_path.name,
                "inventory": inventory,
            }
        )

    def _parse_instagram_export(self, directory: Path, original_path: Path) -> ParsedContent:
        """Parse Instagram export."""
        inventory = self._build_inventory(directory)

        text_parts = [
            "=== Instagram Export Detected ===",
            f"Archive: {original_path.name}",
            "",
            "Note: Full Instagram parsing coming soon.",
            "",
            f"Total files: {inventory['total_files']}",
            f"Supported files: {inventory['supported_files']}",
        ]

        return ParsedContent(
            text="\n".join(text_parts),
            title=f"Instagram Export - {original_path.stem}",
            metadata={
                "detected_format": "instagram",
                "parser": "ArchiveParser",
                "archive_name": original_path.name,
                "inventory": inventory,
            }
        )

    def _parse_linkedin_export(self, directory: Path, original_path: Path) -> ParsedContent:
        """Parse LinkedIn export."""
        inventory = self._build_inventory(directory)

        text_parts = [
            "=== LinkedIn Export Detected ===",
            f"Archive: {original_path.name}",
            "",
            "Files found:",
        ]

        csv_files = list(directory.glob('*.csv'))
        for f in sorted(csv_files):
            text_parts.append(f"- {f.name}")

        text_parts.extend([
            "",
            "Note: Full LinkedIn parsing coming soon.",
            "",
            f"Total files: {inventory['total_files']}",
            f"Supported files: {inventory['supported_files']}",
        ])

        return ParsedContent(
            text="\n".join(text_parts),
            title=f"LinkedIn Export - {original_path.stem}",
            metadata={
                "detected_format": "linkedin",
                "parser": "ArchiveParser",
                "archive_name": original_path.name,
                "inventory": inventory,
            }
        )

    def _process_generic_archive(self, directory: Path, original_path: Path) -> ParsedContent:
        """
        Process a generic archive without known format.

        Scans for supported files and processes each one.
        """
        from .base import get_parser

        inventory = self._build_inventory(directory)

        # Process supported files
        processed_files = []
        text_sections = []

        for file_path in sorted(directory.rglob('*')):
            if not file_path.is_file():
                continue

            # Skip binary/media files
            if file_path.suffix.lower() in self.SKIP_EXTENSIONS:
                continue

            # Try to get a parser
            parser = get_parser(file_path)
            if parser is None:
                continue

            try:
                result = parser.parse(file_path)

                # Get relative path for display
                rel_path = file_path.relative_to(directory)

                # Add to output
                text_sections.append(f"\n{'='*60}")
                text_sections.append(f"FILE: {rel_path}")
                text_sections.append(f"TYPE: {parser.get_file_type()}")
                text_sections.append('='*60)
                text_sections.append(result.text[:10000])  # Limit per file

                processed_files.append({
                    "path": str(rel_path),
                    "type": parser.get_file_type(),
                    "chars": len(result.text),
                })

            except Exception as e:
                processed_files.append({
                    "path": str(file_path.relative_to(directory)),
                    "type": "error",
                    "error": str(e),
                })

        # Build final output
        header = [
            f"=== Archive Contents: {original_path.name} ===",
            "",
            f"Total files: {inventory['total_files']}",
            f"Processed: {len(processed_files)}",
            f"Skipped (media/binary): {inventory['skipped_files']}",
            "",
        ]

        full_text = "\n".join(header) + "\n".join(text_sections)

        return ParsedContent(
            text=full_text,
            title=f"Archive - {original_path.stem}",
            metadata={
                "format": self._detect_archive_type(original_path),
                "parser": "ArchiveParser",
                "archive_name": original_path.name,
                "inventory": inventory,
                "processed_files": processed_files,
            }
        )

    def _build_inventory(self, directory: Path) -> Dict[str, Any]:
        """Build inventory of archive contents."""
        from .base import get_parser

        total = 0
        supported = 0
        skipped = 0
        by_type: Dict[str, int] = {}

        for file_path in directory.rglob('*'):
            if not file_path.is_file():
                continue

            total += 1
            suffix = file_path.suffix.lower()

            if suffix in self.SKIP_EXTENSIONS:
                skipped += 1
                by_type['media/binary'] = by_type.get('media/binary', 0) + 1
                continue

            parser = get_parser(file_path)
            if parser:
                supported += 1
                file_type = parser.get_file_type()
                by_type[file_type] = by_type.get(file_type, 0) + 1
            else:
                by_type['unknown'] = by_type.get('unknown', 0) + 1

        return {
            "total_files": total,
            "supported_files": supported,
            "skipped_files": skipped,
            "by_type": by_type,
        }


__all__ = ["ArchiveParser"]

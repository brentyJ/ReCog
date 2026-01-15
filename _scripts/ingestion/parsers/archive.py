"""
Archive parser for ZIP and TAR files.

Handles compressed archives and detects platform exports
(Facebook, Google Takeout, Twitter, Instagram).

Security features:
- Zip bomb detection (compression ratio, file count limits)
- Path traversal prevention with resolve()
- Encrypted archive detection

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import json
import re
import zipfile
import tarfile
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

from .base import BaseParser
from ..types import ParsedContent


class ArchiveSecurityError(Exception):
    """Raised when archive contains security risks."""
    pass


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

    # Security limits
    MAX_EXTRACTED_SIZE = 500 * 1024 * 1024  # 500MB
    MAX_COMPRESSION_RATIO = 100  # 100:1 ratio threshold for zip bombs
    MAX_FILE_COUNT = 10000  # Maximum files in archive
    MAX_NESTING_DEPTH = 3  # Maximum nested archive depth

    # Track current nesting depth during recursive parsing
    _current_depth = 0

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

    def parse(self, path: Path, _depth: int = 0) -> ParsedContent:
        """
        Parse archive contents.

        Extracts to temporary directory, detects format,
        and processes contained files.

        Args:
            path: Path to archive
            _depth: Internal depth counter for nested archives
        """
        # Check nesting depth
        if _depth > self.MAX_NESTING_DEPTH:
            return ParsedContent(
                text=f"[Nested archive depth limit exceeded: {_depth} > {self.MAX_NESTING_DEPTH}]",
                title=path.stem,
                metadata={
                    "error": "max_depth_exceeded",
                    "depth": _depth,
                    "max_depth": self.MAX_NESTING_DEPTH,
                }
            )

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract archive with security checks
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
                    return self._handle_platform_export(temp_path, export_format, path, _depth)

                # Generic archive: process all supported files
                return self._process_generic_archive(temp_path, path, _depth)

        except ArchiveSecurityError as e:
            return ParsedContent(
                text=f"[Security risk detected: {e}]",
                title=path.stem,
                metadata={"error": "security_risk", "details": str(e)}
            )
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

    def _check_zip_security(self, zf: zipfile.ZipFile) -> None:
        """
        Check ZIP file for security risks.

        Raises:
            ArchiveSecurityError: If security risk detected
        """
        total_compressed = 0
        total_uncompressed = 0
        file_count = 0

        for info in zf.infolist():
            file_count += 1
            total_compressed += info.compress_size
            total_uncompressed += info.file_size

            # Check for encrypted files
            if info.flag_bits & 0x1:
                raise RuntimeError("Archive contains encrypted files")

        # Check file count limit
        if file_count > self.MAX_FILE_COUNT:
            raise ArchiveSecurityError(
                f"Too many files in archive: {file_count} (limit: {self.MAX_FILE_COUNT})"
            )

        # Check compression ratio (zip bomb detection)
        if total_compressed > 0:
            ratio = total_uncompressed / total_compressed
            if ratio > self.MAX_COMPRESSION_RATIO:
                raise ArchiveSecurityError(
                    f"Suspicious compression ratio: {ratio:.0f}:1 (limit: {self.MAX_COMPRESSION_RATIO}:1)"
                )

    def _safe_extract_path(self, member_name: str, base_dir: Path) -> Path:
        """
        Validate and return safe extraction path.

        Prevents path traversal attacks using resolve().

        Args:
            member_name: Name of archive member
            base_dir: Base extraction directory

        Returns:
            Safe resolved path

        Raises:
            ArchiveSecurityError: If path traversal detected
        """
        # Resolve the target path
        target = (base_dir / member_name).resolve()
        base_resolved = base_dir.resolve()

        # Check if target is within base directory
        try:
            target.relative_to(base_resolved)
        except ValueError:
            raise ArchiveSecurityError(f"Path traversal attempt: {member_name}")

        return target

    def _extract_archive(self, path: Path, dest: Path) -> int:
        """
        Extract archive to destination directory with security checks.

        Returns:
            Total extracted size in bytes.
        """
        archive_type = self._detect_archive_type(path)
        total_size = 0
        dest_resolved = dest.resolve()

        if archive_type == "zip":
            with zipfile.ZipFile(path, 'r') as zf:
                # Security checks
                self._check_zip_security(zf)

                # Calculate total size
                total_size = sum(info.file_size for info in zf.infolist())

                # Extract each file with path validation
                for member in zf.infolist():
                    # Validate path
                    self._safe_extract_path(member.filename, dest_resolved)

                    # Extract
                    zf.extract(member, dest)
        else:
            # TAR or TAR.GZ
            mode = 'r:gz' if archive_type == "tar.gz" else 'r'
            with tarfile.open(path, mode) as tf:
                members = tf.getmembers()

                # Check file count
                if len(members) > self.MAX_FILE_COUNT:
                    raise ArchiveSecurityError(
                        f"Too many files in archive: {len(members)} (limit: {self.MAX_FILE_COUNT})"
                    )

                # Validate each member
                for member in members:
                    # Validate path
                    self._safe_extract_path(member.name, dest_resolved)
                    total_size += member.size

                # Use data_filter for Python 3.12+ or manual extraction
                try:
                    tf.extractall(dest, filter='data')
                except TypeError:
                    # Fallback for older Python
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

    def _handle_platform_export(
        self, directory: Path, export_format: str, original_path: Path, _depth: int = 0
    ) -> ParsedContent:
        """
        Handle known platform export formats.

        Args:
            directory: Extracted archive directory
            export_format: Detected platform format
            original_path: Original archive path
            _depth: Current nesting depth
        """
        handlers = {
            'facebook': self._parse_facebook_export,
            'google_takeout': self._parse_google_takeout,
            'twitter': self._parse_twitter_export,
            'instagram': self._parse_instagram_export,
            'linkedin': self._parse_linkedin_export,
        }

        handler = handlers.get(export_format)

        if handler is None:
            return self._process_generic_archive(directory, original_path, _depth)

        return handler(directory, original_path)

    def _fix_meta_encoding(self, text: str) -> str:
        """
        Fix Facebook/Instagram's incorrectly encoded UTF-8 (mojibake).

        Meta exports JSON with UTF-8 text double-encoded as Latin-1,
        causing "café" to appear as "cafÃ©".
        """
        try:
            return text.encode('latin1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            return text

    def _parse_facebook_export(self, directory: Path, original_path: Path) -> ParsedContent:
        """
        Parse Facebook export with content extraction.

        Handles Meta's mojibake encoding bug.
        """
        inventory = self._build_inventory(directory)

        text_parts = [
            "=== Facebook Export Analysis ===",
            f"Archive: {original_path.name}",
            "",
        ]

        # Extract messages
        messages_dir = directory / 'messages' / 'inbox'
        message_count = 0
        participants = set()

        if messages_dir.exists():
            threads = list(messages_dir.iterdir())
            text_parts.append(f"Message Threads: {len(threads)}")
            text_parts.append("")

            for thread_dir in threads[:10]:  # Sample first 10 threads
                message_files = list(thread_dir.glob('message_*.json'))
                for msg_file in message_files[:1]:  # First file per thread
                    try:
                        with open(msg_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        thread_name = self._fix_meta_encoding(data.get('title', 'Unknown'))
                        thread_participants = data.get('participants', [])

                        for p in thread_participants:
                            name = self._fix_meta_encoding(p.get('name', ''))
                            if name:
                                participants.add(name)

                        messages = data.get('messages', [])
                        message_count += len(messages)

                        text_parts.append(f"--- Thread: {thread_name} ---")
                        text_parts.append(f"Participants: {len(thread_participants)}")
                        text_parts.append(f"Messages: {len(messages)}")

                        # Sample messages
                        for msg in messages[:5]:
                            sender = self._fix_meta_encoding(msg.get('sender_name', 'Unknown'))
                            content = self._fix_meta_encoding(msg.get('content', ''))
                            if content:
                                content = content[:200] + '...' if len(content) > 200 else content
                                text_parts.append(f"  {sender}: {content}")

                        text_parts.append("")

                    except Exception as e:
                        text_parts.append(f"  [Error reading {msg_file.name}: {e}]")

        # Extract posts
        posts_dir = directory / 'posts'
        if posts_dir.exists():
            post_files = list(posts_dir.glob('*.json'))
            text_parts.append(f"Posts Files: {len(post_files)}")

            for post_file in post_files[:3]:
                try:
                    with open(post_file, 'r', encoding='utf-8') as f:
                        posts = json.load(f)

                    if isinstance(posts, list):
                        for post in posts[:3]:
                            if 'data' in post:
                                for item in post['data'][:1]:
                                    if 'post' in item:
                                        content = self._fix_meta_encoding(item['post'])
                                        content = content[:300] + '...' if len(content) > 300 else content
                                        text_parts.append(f"  Post: {content}")
                except Exception:
                    pass

            text_parts.append("")

        text_parts.extend([
            f"Total Messages Found: {message_count}",
            f"Unique Participants: {len(participants)}",
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
                "message_count": message_count,
                "participant_count": len(participants),
                "participants": list(participants)[:50],
                "inventory": inventory,
            }
        )

    def _parse_google_takeout(self, directory: Path, original_path: Path) -> ParsedContent:
        """
        Parse Google Takeout export.
        """
        inventory = self._build_inventory(directory)
        takeout_dir = directory / 'Takeout'

        text_parts = [
            "=== Google Takeout Analysis ===",
            f"Archive: {original_path.name}",
            "",
        ]

        services_data = {}

        if takeout_dir.exists():
            services = [d for d in takeout_dir.iterdir() if d.is_dir()]
            text_parts.append(f"Services: {len(services)}")
            text_parts.append("")

            for service_dir in sorted(services):
                service_name = service_dir.name
                file_count = sum(1 for _ in service_dir.rglob('*') if _.is_file())
                services_data[service_name] = file_count
                text_parts.append(f"- {service_name}: {file_count} files")

        text_parts.extend([
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
                "services": services_data,
                "inventory": inventory,
            }
        )

    def _parse_twitter_js(self, js_path: Path) -> List[Dict]:
        """
        Parse Twitter's JavaScript-wrapped JSON files.

        Twitter archives wrap JSON in: window.YTD.tweet.part0 = [...]
        """
        content = js_path.read_text(encoding='utf-8')

        # Strip JavaScript wrapper
        json_str = re.sub(r'^window\.YTD\.\w+\.part\d+\s*=\s*', '', content)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return []

    def _parse_twitter_export(self, directory: Path, original_path: Path) -> ParsedContent:
        """
        Parse Twitter archive with JS wrapper handling.
        """
        inventory = self._build_inventory(directory)

        text_parts = [
            "=== Twitter Archive Analysis ===",
            f"Archive: {original_path.name}",
            "",
        ]

        data_dir = directory / 'data'
        tweets = []
        tweet_count = 0

        if data_dir.exists():
            # Parse tweets.js or tweet.js
            tweet_files = ['tweets.js', 'tweet.js']
            for tweet_file in tweet_files:
                tweet_path = data_dir / tweet_file
                if tweet_path.exists():
                    try:
                        tweet_data = self._parse_twitter_js(tweet_path)
                        tweet_count = len(tweet_data)
                        tweets = tweet_data

                        text_parts.append(f"Tweets: {tweet_count}")
                        text_parts.append("")

                        # Sample tweets
                        text_parts.append("Sample Tweets:")
                        for item in tweet_data[:10]:
                            tweet = item.get('tweet', item)
                            text = tweet.get('full_text', tweet.get('text', ''))
                            created = tweet.get('created_at', '')
                            if text:
                                text = text[:200] + '...' if len(text) > 200 else text
                                text_parts.append(f"  [{created[:10] if created else 'N/A'}] {text}")

                        break
                    except Exception as e:
                        text_parts.append(f"  [Error parsing tweets: {e}]")

            # List other data files
            text_parts.append("")
            text_parts.append("Other Data Files:")
            js_files = list(data_dir.glob('*.js'))
            for f in sorted(js_files)[:15]:
                if f.name not in tweet_files:
                    text_parts.append(f"  - {f.stem}")

        text_parts.extend([
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
                "tweet_count": tweet_count,
                "inventory": inventory,
            }
        )

    def _parse_instagram_export(self, directory: Path, original_path: Path) -> ParsedContent:
        """
        Parse Instagram export with mojibake fix.
        """
        inventory = self._build_inventory(directory)

        text_parts = [
            "=== Instagram Export Analysis ===",
            f"Archive: {original_path.name}",
            "",
        ]

        # Try to extract content
        content_found = False

        # Check for messages
        messages_dir = directory / 'messages' / 'inbox'
        if messages_dir.exists():
            threads = list(messages_dir.iterdir())
            text_parts.append(f"Message Threads: {len(threads)}")
            content_found = True

        # Check for posts
        posts_json = directory / 'content' / 'posts_1.json'
        if posts_json.exists():
            try:
                with open(posts_json, 'r', encoding='utf-8') as f:
                    posts = json.load(f)
                text_parts.append(f"Posts: {len(posts)}")

                for post in posts[:5]:
                    if 'media' in post:
                        for media in post['media'][:1]:
                            caption = self._fix_meta_encoding(media.get('title', ''))
                            if caption:
                                caption = caption[:200] + '...' if len(caption) > 200 else caption
                                text_parts.append(f"  Post: {caption}")
                content_found = True
            except Exception:
                pass

        if not content_found:
            text_parts.append("Note: Limited content extraction for Instagram exports.")

        text_parts.extend([
            "",
            f"Total files: {inventory['total_files']}",
            f"Supported files: {inventory['supported_files']}",
        ])

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
            "=== LinkedIn Export Analysis ===",
            f"Archive: {original_path.name}",
            "",
            "CSV Files Found:",
        ]

        csv_files = list(directory.glob('*.csv'))
        for f in sorted(csv_files):
            text_parts.append(f"  - {f.name}")

        text_parts.extend([
            "",
            "Note: LinkedIn CSV files processed by EnhancedCSVParser.",
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
                "csv_files": [f.name for f in csv_files],
                "inventory": inventory,
            }
        )

    def _process_generic_archive(self, directory: Path, original_path: Path, _depth: int = 0) -> ParsedContent:
        """
        Process a generic archive without known format.

        Scans for supported files and processes each one.

        Args:
            directory: Extracted archive directory
            original_path: Original archive path
            _depth: Current nesting depth for recursive archive handling
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
                # Pass depth for nested archives
                if isinstance(parser, ArchiveParser):
                    result = parser.parse(file_path, _depth=_depth + 1)
                else:
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


__all__ = ["ArchiveParser", "ArchiveSecurityError"]

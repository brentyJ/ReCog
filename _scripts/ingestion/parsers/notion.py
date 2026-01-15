"""
Notion Export parser.

Parses Notion workspace exports containing markdown pages
and CSV database exports.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import csv
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

from .base import BaseParser
from ..types import ParsedContent


class NotionParser(BaseParser):
    """
    Parse Notion workspace exports.

    Handles directory exports with markdown pages and CSV databases,
    preserving hierarchy and internal links.
    """

    PARSER_METADATA = {
        "file_type": "Notion Export",
        "extensions": [".md"],  # Notion-style markdown with IDs
        "cypher_context": {
            "description": "Notion workspace containing notes, databases, and knowledge base",
            "requires_user_input": [],
            "extractable": [
                "Note content and knowledge organization",
                "Database entries with properties and relations",
                "Page hierarchy and information architecture",
                "Internal links showing concept relationships",
                "Created/modified timestamps",
                "Tags and categorization system",
                "Tasks and project tracking"
            ],
            "suggestions": [
                "Notion exports preserve your knowledge structure",
                "Database properties reveal how you organize information",
                "Internal links show how concepts connect in your mind",
                "Page hierarchy indicates your mental models",
                "Tags and properties are valuable metadata for pattern detection"
            ]
        }
    }

    # Regex to detect Notion page ID suffix (e.g., "Page Name 123abc.md")
    NOTION_ID_PATTERN = re.compile(r'^(.+?)\s+([a-f0-9]{32}|[a-f0-9-]{36})$')

    def get_extensions(self) -> List[str]:
        return [".md"]

    def can_parse(self, path: Path) -> bool:
        """
        Check if this is a Notion export.

        Notion exports have:
        - Markdown files with ID suffixes
        - Export folder named Export-XXXXX
        - Specific structure
        """
        if not path.exists():
            return False

        # If it's a directory, check if it looks like Notion export
        if path.is_dir():
            return self._is_notion_export_dir(path)

        # If it's a file, check if it's Notion-style markdown
        if path.suffix.lower() == '.md':
            return self._is_notion_markdown(path)

        return False

    def _is_notion_export_dir(self, path: Path) -> bool:
        """Check if directory is a Notion export."""
        # Check for Export-XXXXX pattern
        if path.name.startswith('Export-'):
            return True

        # Check for Notion-style files inside
        for child in list(path.iterdir())[:10]:
            if child.suffix == '.md' and self._has_notion_id(child.stem):
                return True

        return False

    def _is_notion_markdown(self, path: Path) -> bool:
        """Check if markdown file is from Notion export."""
        # Check filename for Notion ID pattern
        if self._has_notion_id(path.stem):
            return True

        # Check parent directory
        parent = path.parent
        if parent.name.startswith('Export-'):
            return True

        # Check for sibling Notion files
        siblings = list(parent.glob('*.md'))[:5]
        notion_siblings = sum(1 for s in siblings if self._has_notion_id(s.stem))
        if notion_siblings >= 2:
            return True

        return False

    def _has_notion_id(self, stem: str) -> bool:
        """Check if filename stem has Notion ID suffix."""
        return bool(self.NOTION_ID_PATTERN.match(stem))

    def _extract_page_name(self, stem: str) -> str:
        """Extract page name from Notion filename."""
        match = self.NOTION_ID_PATTERN.match(stem)
        if match:
            return match.group(1)
        return stem

    def get_file_type(self) -> str:
        return "notion"

    def parse(self, path: Path) -> ParsedContent:
        """Parse Notion export."""
        try:
            if path.is_dir():
                return self._parse_export_directory(path)
            else:
                return self._parse_single_page(path)

        except Exception as e:
            return ParsedContent(
                text=f"[Notion parsing error: {e}]",
                title=path.stem,
                metadata={"error": "parse_failed", "details": str(e)}
            )

    def _parse_export_directory(self, path: Path) -> ParsedContent:
        """Parse entire Notion export directory."""
        pages = []
        databases = []
        hierarchy = {}

        # Walk the directory structure
        for item in path.rglob('*'):
            if item.is_file():
                rel_path = item.relative_to(path)

                if item.suffix.lower() == '.md':
                    page_data = self._parse_markdown_file(item)
                    page_data['path'] = str(rel_path)
                    pages.append(page_data)

                    # Track hierarchy
                    self._add_to_hierarchy(hierarchy, rel_path, 'page')

                elif item.suffix.lower() == '.csv':
                    db_data = self._parse_database_file(item)
                    db_data['path'] = str(rel_path)
                    databases.append(db_data)

                    self._add_to_hierarchy(hierarchy, rel_path, 'database')

        # Format output
        text = self._format_export(pages, databases, path)

        return ParsedContent(
            text=text,
            title=f"Notion Export - {path.name}",
            metadata={
                "format": "notion_export",
                "parser": "NotionParser",
                "page_count": len(pages),
                "database_count": len(databases),
                "hierarchy": hierarchy,
            }
        )

    def _parse_single_page(self, path: Path) -> ParsedContent:
        """Parse a single Notion markdown page."""
        page_data = self._parse_markdown_file(path)

        # Check if there's a parent export directory
        export_root = self._find_export_root(path)
        if export_root:
            # Parse full export
            return self._parse_export_directory(export_root)

        # Single page
        lines = [
            f"=== Notion Page: {page_data['title']} ===",
            "",
            page_data['content'],
        ]

        if page_data.get('links'):
            lines.extend(["", "Internal Links:", ])
            for link in page_data['links']:
                lines.append(f"  - {link}")

        return ParsedContent(
            text="\n".join(lines),
            title=f"Notion - {page_data['title']}",
            metadata={
                "format": "notion_page",
                "parser": "NotionParser",
                "internal_links": page_data.get('links', []),
            }
        )

    def _parse_markdown_file(self, path: Path) -> Dict[str, Any]:
        """Parse a Notion markdown file."""
        # Extract page name from filename
        title = self._extract_page_name(path.stem)

        # Read content
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = path.read_text(encoding='latin-1')

        # Extract title from content if available
        lines = content.split('\n')
        for line in lines[:5]:
            if line.startswith('# '):
                title = line[2:].strip()
                break

        # Find internal links [[Page Name]]
        links = re.findall(r'\[\[([^\]]+)\]\]', content)

        # Find heading structure
        headings = []
        for line in lines:
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                heading_text = line.lstrip('#').strip()
                if heading_text:
                    headings.append((level, heading_text))

        return {
            'title': title,
            'content': content[:50000],  # Limit content size
            'links': links,
            'headings': headings,
            'word_count': len(content.split()),
        }

    def _parse_database_file(self, path: Path) -> Dict[str, Any]:
        """Parse a Notion database CSV export."""
        title = self._extract_page_name(path.stem)

        try:
            with open(path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames or []
                rows = list(reader)
        except Exception:
            return {
                'title': title,
                'columns': [],
                'row_count': 0,
                'sample': [],
                'error': 'Failed to parse CSV'
            }

        return {
            'title': title,
            'columns': columns,
            'row_count': len(rows),
            'sample': rows[:5],  # First 5 rows as sample
        }

    def _find_export_root(self, path: Path) -> Optional[Path]:
        """Find the root of a Notion export."""
        current = path.parent

        for _ in range(5):  # Max depth to check
            if current.name.startswith('Export-'):
                return current

            # Check if this looks like export root
            md_files = list(current.glob('*.md'))
            notion_files = sum(1 for f in md_files if self._has_notion_id(f.stem))
            if notion_files >= 3:
                return current

            if current.parent == current:
                break
            current = current.parent

        return None

    def _add_to_hierarchy(self, hierarchy: Dict, rel_path: Path, item_type: str):
        """Add item to hierarchy dict."""
        parts = list(rel_path.parts)
        current = hierarchy

        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            current = current[part]

        # Add the file
        filename = parts[-1]
        if item_type == 'page':
            current[filename] = 'page'
        else:
            current[filename] = 'database'

    def _format_export(self, pages: List[Dict], databases: List[Dict],
                       path: Path) -> str:
        """Format Notion export as readable text."""
        lines = [
            f"=== Notion Export: {path.name} ===",
            "",
            f"Pages: {len(pages)}",
            f"Databases: {len(databases)}",
            "",
        ]

        # Pages section
        if pages:
            lines.extend([
                "=" * 50,
                "PAGES",
                "=" * 50,
                "",
            ])

            for page in pages[:50]:  # Limit pages shown
                lines.append(f"--- Page: {page['title']} ---")
                lines.append(f"Path: {page.get('path', 'unknown')}")

                # Headings outline
                if page.get('headings'):
                    lines.append("Structure:")
                    for level, heading in page['headings'][:10]:
                        indent = "  " * (level - 1)
                        lines.append(f"  {indent}{heading}")

                # Links
                if page.get('links'):
                    lines.append(f"Links to: {', '.join(page['links'][:5])}")

                # Content preview
                content = page.get('content', '')[:500]
                if content:
                    # Skip the first heading line
                    preview_lines = content.split('\n')
                    preview = '\n'.join(preview_lines[:10])
                    lines.append(f"Preview:")
                    lines.append(preview)

                lines.append("")

            if len(pages) > 50:
                lines.append(f"... and {len(pages) - 50} more pages")
                lines.append("")

        # Databases section
        if databases:
            lines.extend([
                "=" * 50,
                "DATABASES",
                "=" * 50,
                "",
            ])

            for db in databases:
                lines.append(f"--- Database: {db['title']} ---")
                lines.append(f"Path: {db.get('path', 'unknown')}")
                lines.append(f"Rows: {db['row_count']}")

                if db.get('columns'):
                    lines.append(f"Columns: {', '.join(db['columns'][:10])}")

                # Sample entries
                if db.get('sample'):
                    lines.append("Sample entries:")
                    for row in db['sample'][:3]:
                        # Show first few columns
                        cols = list(row.items())[:3]
                        entry = ', '.join(f"{k}: {v}" for k, v in cols if v)
                        lines.append(f"  - {entry[:100]}")

                lines.append("")

        return "\n".join(lines)


__all__ = ["NotionParser"]

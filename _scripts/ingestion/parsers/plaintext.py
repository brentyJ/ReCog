"""
Plain text parser.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from .base import BaseParser
from ..types import ParsedContent


class PlaintextParser(BaseParser):
    """Parse plain text files."""
    
    def get_extensions(self):
        return [".txt", ".text"]
    
    def can_parse(self, path: Path) -> bool:
        # Accept .txt and extensionless files
        return path.suffix.lower() in (".txt", ".text", "")
    
    def get_file_type(self) -> str:
        return "text"
    
    def parse(self, path: Path) -> ParsedContent:
        """
        Read plain text file.
        """
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except UnicodeDecodeError:
            # Try latin-1 as fallback
            content = path.read_text(encoding="latin-1", errors="replace")
        
        # Try to extract title from first line if it looks like a title
        title = self._extract_title(content) or path.stem
        
        # Try to extract date from content or filename
        doc_date = self._extract_date(content, path.name)
        
        return ParsedContent(
            text=content,
            metadata={"source_file": path.name},
            title=title,
            date=doc_date,
        )
    
    def _extract_title(self, content: str) -> Optional[str]:
        """Try to extract a title from the first line."""
        lines = content.strip().split("\n", 1)
        if not lines:
            return None
        
        first_line = lines[0].strip()
        
        # If first line is short and doesn't end in punctuation, use as title
        if len(first_line) < 100 and not first_line.endswith((".", "?", "!", ",")):
            return first_line
        
        return None
    
    def _extract_date(self, content: str, filename: str) -> Optional[str]:
        """Try to extract a date from content or filename."""
        # Try filename first (common patterns: YYYY-MM-DD, YYYYMMDD)
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{4})(\d{2})(\d{2})',
            r'(\d{2})-(\d{2})-(\d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                groups = match.groups()
                if len(groups) == 1:
                    return groups[0]
                elif len(groups) == 3:
                    if len(groups[0]) == 4:
                        return f"{groups[0]}-{groups[1]}-{groups[2]}"
                    else:
                        return f"{groups[2]}-{groups[1]}-{groups[0]}"
        
        return None

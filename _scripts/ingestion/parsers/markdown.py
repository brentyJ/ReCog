"""
Markdown parser with YAML frontmatter extraction.
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .base import BaseParser
from ..types import ParsedContent


class MarkdownParser(BaseParser):
    """Parse Markdown files with YAML frontmatter."""
    
    def get_extensions(self):
        return [".md", ".markdown"]
    
    FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n',
        re.DOTALL
    )
    
    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in (".md", ".markdown")
    
    def get_file_type(self) -> str:
        return "markdown"
    
    def parse(self, path: Path) -> ParsedContent:
        """
        Extract content and frontmatter from markdown.
        """
        content = path.read_text(encoding="utf-8", errors="replace")
        
        # Extract frontmatter
        frontmatter, body = self._extract_frontmatter(content)
        
        # Build metadata
        metadata = frontmatter.copy() if frontmatter else {}
        
        # Extract title from frontmatter or first heading
        title = frontmatter.get("title") if frontmatter else None
        if not title:
            title = self._extract_first_heading(body) or path.stem
        
        # Extract date
        doc_date = None
        if frontmatter:
            doc_date = frontmatter.get("date") or frontmatter.get("created")
            if doc_date and not isinstance(doc_date, str):
                doc_date = str(doc_date)
        
        # Extract author
        author = frontmatter.get("author") if frontmatter else None
        
        return ParsedContent(
            text=body,
            metadata=metadata,
            title=title,
            author=author,
            date=doc_date,
            subject=frontmatter.get("subject") if frontmatter else None,
        )
    
    def _extract_frontmatter(self, content: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Extract YAML frontmatter from content.
        
        Returns:
            Tuple of (frontmatter dict or None, body text)
        """
        match = self.FRONTMATTER_PATTERN.match(content)
        
        if not match:
            return None, content
        
        frontmatter_text = match.group(1)
        body = content[match.end():]
        
        if not HAS_YAML:
            # Return raw frontmatter as single key if yaml not available
            return {"_raw": frontmatter_text}, body
        
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            if not isinstance(frontmatter, dict):
                frontmatter = {"_raw": frontmatter_text}
            return frontmatter, body
        except yaml.YAMLError:
            return {"_raw": frontmatter_text}, body
    
    def _extract_first_heading(self, text: str) -> Optional[str]:
        """Extract the first markdown heading."""
        # Match # Heading
        match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        # Match underlined heading
        match = re.search(r'^(.+)\n[=]+\s*$', text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        return None

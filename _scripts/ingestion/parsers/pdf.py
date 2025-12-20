"""
PDF parser using pypdf.

Install: pip install pypdf
"""

import re
from pathlib import Path
from typing import List, Optional
from .base import BaseParser

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    try:
        from PyPDF2 import PdfReader
        HAS_PYPDF = True
    except ImportError:
        HAS_PYPDF = False

from ..types import ParsedContent


class PDFParser(BaseParser):
    """Parse PDF files."""
    
    def get_extensions(self):
        return [".pdf"]
    
    def can_parse(self, path: Path) -> bool:
        if not HAS_PYPDF:
            return False
        return path.suffix.lower() == ".pdf"
    
    def get_file_type(self) -> str:
        return "pdf"
    
    def parse(self, path: Path) -> ParsedContent:
        """
        Extract text and metadata from PDF.
        """
        if not HAS_PYPDF:
            raise ImportError("pypdf required: pip install pypdf")
        
        reader = PdfReader(str(path))
        
        # Extract pages
        pages: List[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            # Clean up common PDF extraction issues
            text = self._clean_pdf_text(text)
            pages.append(text)
        
        full_text = "\n\n".join(pages)
        
        # Extract metadata
        metadata = {}
        if reader.metadata:
            metadata = {
                "title": reader.metadata.get("/Title"),
                "author": reader.metadata.get("/Author"),
                "subject": reader.metadata.get("/Subject"),
                "creator": reader.metadata.get("/Creator"),
                "producer": reader.metadata.get("/Producer"),
                "creation_date": str(reader.metadata.get("/CreationDate", "")),
            }
        
        # Try to extract date from metadata
        doc_date = None
        if metadata.get("creation_date"):
            doc_date = self._parse_pdf_date(metadata["creation_date"])
        
        return ParsedContent(
            text=full_text,
            metadata=metadata,
            pages=pages,
            title=metadata.get("title") or path.stem,
            author=metadata.get("author"),
            date=doc_date,
            subject=metadata.get("subject"),
        )
    
    def _clean_pdf_text(self, text: str) -> str:
        """Clean common PDF extraction artifacts."""
        # Fix hyphenation at line breaks
        text = re.sub(r'-\n(\w)', r'\1', text)
        
        # Normalize whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Fix multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def _parse_pdf_date(self, date_str: str) -> Optional[str]:
        """
        Parse PDF date format (D:YYYYMMDDHHmmSS) to ISO.
        """
        if not date_str:
            return None
        
        # Remove D: prefix
        date_str = date_str.replace("D:", "").strip()
        
        # Try to extract YYYYMMDD
        match = re.match(r"(\d{4})(\d{2})(\d{2})", date_str)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        
        return None

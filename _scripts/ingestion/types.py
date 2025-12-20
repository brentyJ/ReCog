"""
Ingestion type definitions.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class ParsedContent:
    """Result from a parser."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    pages: Optional[List[str]] = None  # For PDFs, text per page
    
    # Extracted metadata
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    subject: Optional[str] = None
    recipients: Optional[List[str]] = None


@dataclass
class DocumentChunk:
    """A chunk of document content."""
    content: str
    chunk_index: int
    token_count: int
    
    # Position in source
    start_char: int
    end_char: int
    page_number: Optional[int] = None
    
    # Context
    preceding_context: str = ""
    following_context: str = ""


@dataclass
class IngestedDocument:
    """Represents an ingested document."""
    id: Optional[int] = None
    filename: str = ""
    file_hash: str = ""
    file_type: str = ""
    file_path: str = ""
    file_size: int = 0
    ingested_at: Optional[datetime] = None
    
    # Metadata
    doc_date: Optional[str] = None
    doc_author: Optional[str] = None
    doc_subject: Optional[str] = None
    doc_recipients: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Processing state
    status: str = "pending"
    chunk_count: int = 0
    insights_extracted: int = 0
    error_message: Optional[str] = None
    
    # Content
    chunks: List[DocumentChunk] = field(default_factory=list)


@dataclass
class FileDetectionResult:
    """Result of file format detection."""
    supported: bool
    file_type: str
    parser_name: Optional[str] = None
    
    # Guidance for user
    needs_action: bool = False
    action_message: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    
    # For containers (ZIP, etc)
    is_container: bool = False
    contained_files: List[str] = field(default_factory=list)


__all__ = [
    "ParsedContent",
    "DocumentChunk",
    "IngestedDocument",
    "FileDetectionResult",
]

"""
Universal File Detector and Ingestion Guide

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3

Intelligently detects file formats and provides guidance for unsupported
or container formats.
"""

import os
import zipfile
import mimetypes
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field

from .types import FileDetectionResult, ParsedContent
from .parsers.base import get_parser, get_all_parsers, get_supported_extensions
from recog_engine.core.types import Document


# =============================================================================
# FORMAT DEFINITIONS
# =============================================================================

SUPPORTED_FORMATS = {
    # Documents
    ".pdf": ("PDF Document", "pdf"),
    ".md": ("Markdown", "markdown"),
    ".markdown": ("Markdown", "markdown"),
    ".txt": ("Plain Text", "text"),
    ".text": ("Plain Text", "text"),
    
    # Data exports
    ".json": ("JSON (may contain chat exports)", "json"),
    
    # Messages
    ".xml": ("XML Messages", "messages"),
    ".mbox": ("Email Archive", "messages"),
}

CONTAINER_FORMATS = {
    ".zip": "ZIP Archive",
    ".tar": "TAR Archive",
    ".gz": "GZip Archive",
    ".7z": "7-Zip Archive",
    ".rar": "RAR Archive",
}

UNSUPPORTED_WITH_SUGGESTIONS = {
    ".docx": {
        "name": "Microsoft Word",
        "suggestions": [
            "Export as PDF from Word (File → Save As → PDF)",
            "Copy/paste the text content into a .txt file",
            "Use online converter to convert to PDF or plain text"
        ]
    },
    ".doc": {
        "name": "Microsoft Word (Legacy)",
        "suggestions": [
            "Open in Word and save as PDF or .docx first",
            "Copy/paste the text content into a .txt file"
        ]
    },
    ".xlsx": {
        "name": "Microsoft Excel",
        "suggestions": [
            "Export as CSV (File → Save As → CSV)",
            "Copy/paste relevant data into a text file"
        ]
    },
    ".xls": {
        "name": "Microsoft Excel (Legacy)", 
        "suggestions": [
            "Open in Excel and save as CSV",
            "Copy/paste relevant data into a text file"
        ]
    },
    ".pptx": {
        "name": "Microsoft PowerPoint",
        "suggestions": [
            "Export as PDF (File → Save As → PDF)",
            "Copy/paste slide content into a text file"
        ]
    },
    ".rtf": {
        "name": "Rich Text Format",
        "suggestions": [
            "Open in Word/TextEdit and save as plain text",
            "Copy/paste content into a .txt file"
        ]
    },
    ".html": {
        "name": "HTML Document",
        "suggestions": [
            "Save as plain text from browser",
            "Copy/paste visible text into a .txt file"
        ]
    },
    ".htm": {
        "name": "HTML Document",
        "suggestions": [
            "Save as plain text from browser",
            "Copy/paste visible text into a .txt file"
        ]
    },
    ".epub": {
        "name": "eBook",
        "suggestions": [
            "Use Calibre to convert to plain text",
            "Export individual chapters as text"
        ]
    },
    ".odt": {
        "name": "OpenDocument Text",
        "suggestions": [
            "Export as PDF from LibreOffice",
            "Save as plain text (.txt)"
        ]
    },
    ".pages": {
        "name": "Apple Pages",
        "suggestions": [
            "Export as PDF from Pages",
            "Export as plain text from Pages"
        ]
    },
}

IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"}
AUDIO_FORMATS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}
VIDEO_FORMATS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv"}


# =============================================================================
# DETECTOR CLASS
# =============================================================================

class UniversalDetector:
    """
    Detects file formats and provides intelligent guidance.
    
    Usage:
        detector = UniversalDetector()
        result = detector.detect(path)
        
        if result.supported:
            # Process directly
            documents = detector.ingest(path)
        elif result.needs_action:
            # Show guidance to user
            print(result.action_message)
            for suggestion in result.suggestions:
                print(f"  - {suggestion}")
    """
    
    def detect(self, path: str | Path) -> FileDetectionResult:
        """
        Detect file format and return guidance.
        
        Args:
            path: Path to file
        
        Returns:
            FileDetectionResult with support status and guidance
        """
        path = Path(path)
        
        if not path.exists():
            return FileDetectionResult(
                supported=False,
                file_type="not_found",
                needs_action=True,
                action_message=f"File not found: {path}",
            )
        
        if path.is_dir():
            return self._detect_directory(path)
        
        suffix = path.suffix.lower()
        
        # Check for container formats (ZIP, etc)
        if suffix in CONTAINER_FORMATS:
            return self._detect_container(path, suffix)
        
        # Check for supported formats
        parser = get_parser(path)
        if parser:
            return FileDetectionResult(
                supported=True,
                file_type=parser.get_file_type(),
                parser_name=parser.__class__.__name__,
            )
        
        # Check for unsupported with suggestions
        if suffix in UNSUPPORTED_WITH_SUGGESTIONS:
            info = UNSUPPORTED_WITH_SUGGESTIONS[suffix]
            return FileDetectionResult(
                supported=False,
                file_type=suffix[1:],  # Remove dot
                needs_action=True,
                action_message=f"{info['name']} files are not directly supported.",
                suggestions=info["suggestions"],
            )
        
        # Check for media files
        if suffix in IMAGE_FORMATS:
            return FileDetectionResult(
                supported=False,
                file_type="image",
                needs_action=True,
                action_message="Image files cannot be processed for text content.",
                suggestions=[
                    "If this contains text, use OCR software to extract it",
                    "Describe the image content in a text file if relevant"
                ],
            )
        
        if suffix in AUDIO_FORMATS:
            return FileDetectionResult(
                supported=False,
                file_type="audio",
                needs_action=True,
                action_message="Audio files need transcription first.",
                suggestions=[
                    "Use a transcription service (Whisper, Otter.ai, etc.)",
                    "Upload the transcript as a text file"
                ],
            )
        
        if suffix in VIDEO_FORMATS:
            return FileDetectionResult(
                supported=False,
                file_type="video",
                needs_action=True,
                action_message="Video files need transcription first.",
                suggestions=[
                    "Extract audio and transcribe it",
                    "Use a video transcription service",
                    "Upload the transcript as a text file"
                ],
            )
        
        # Unknown format - try as plain text
        if self._looks_like_text(path):
            return FileDetectionResult(
                supported=True,
                file_type="text",
                parser_name="PlaintextParser",
                action_message=f"Unknown extension '{suffix}' - treating as plain text."
            )
        
        return FileDetectionResult(
            supported=False,
            file_type="unknown",
            needs_action=True,
            action_message=f"Unknown file format: {suffix}",
            suggestions=[
                "If this is a text file, rename it with .txt extension",
                "If this is a document, export it as PDF or plain text",
                f"Supported formats: {', '.join(get_supported_extensions())}"
            ],
        )
    
    def _detect_directory(self, path: Path) -> FileDetectionResult:
        """Detect contents of a directory."""
        files = list(path.rglob("*"))
        files = [f for f in files if f.is_file()]
        
        supported = []
        unsupported = []
        
        for f in files:
            result = self.detect(f)
            if result.supported:
                supported.append(f.name)
            else:
                unsupported.append(f.name)
        
        return FileDetectionResult(
            supported=len(supported) > 0,
            file_type="directory",
            is_container=True,
            contained_files=supported[:20],  # Limit display
            needs_action=len(unsupported) > 0,
            action_message=f"Directory contains {len(supported)} supported and {len(unsupported)} unsupported files.",
            suggestions=[
                f"Supported files found: {len(supported)}",
                f"Unsupported files: {len(unsupported)}"
            ] if unsupported else [],
        )
    
    def _detect_container(self, path: Path, suffix: str) -> FileDetectionResult:
        """Detect contents of a container file."""
        container_name = CONTAINER_FORMATS[suffix]
        
        if suffix == ".zip":
            return self._detect_zip(path)
        
        return FileDetectionResult(
            supported=False,
            file_type=suffix[1:],
            is_container=True,
            needs_action=True,
            action_message=f"{container_name} detected. Please extract first.",
            suggestions=[
                f"Extract the {container_name} contents",
                "Upload the extracted files individually",
                "Or upload the entire extracted folder"
            ],
        )
    
    def _detect_zip(self, path: Path) -> FileDetectionResult:
        """Analyze contents of a ZIP file."""
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                names = zf.namelist()
                
                # Filter out directories and hidden files
                files = [n for n in names if not n.endswith('/') and not n.startswith('__')]
                
                supported = []
                unsupported = []
                
                for name in files:
                    ext = Path(name).suffix.lower()
                    if ext in SUPPORTED_FORMATS or ext == ".json":
                        supported.append(name)
                    else:
                        unsupported.append(name)
                
                # Check for known export formats
                if any("conversations.json" in f for f in files):
                    return FileDetectionResult(
                        supported=True,
                        file_type="chatgpt_export",
                        is_container=True,
                        contained_files=supported,
                        action_message="ChatGPT export detected! Extract and upload conversations.json",
                        suggestions=[
                            "Extract the ZIP file",
                            "Upload the 'conversations.json' file"
                        ],
                    )
                
                return FileDetectionResult(
                    supported=len(supported) > 0,
                    file_type="zip",
                    is_container=True,
                    contained_files=supported[:20],
                    needs_action=True,
                    action_message=f"ZIP contains {len(supported)} processable files.",
                    suggestions=[
                        "Extract the ZIP file first",
                        "Upload extracted files individually or as a folder"
                    ],
                )
                
        except zipfile.BadZipFile:
            return FileDetectionResult(
                supported=False,
                file_type="zip",
                needs_action=True,
                action_message="Invalid or corrupted ZIP file.",
            )
    
    def _looks_like_text(self, path: Path) -> bool:
        """Check if file appears to be text content."""
        try:
            with open(path, 'rb') as f:
                chunk = f.read(1024)
                
            # Check for null bytes (binary indicator)
            if b'\x00' in chunk:
                return False
            
            # Try to decode as UTF-8
            try:
                chunk.decode('utf-8')
                return True
            except UnicodeDecodeError:
                pass
            
            # Try Latin-1
            try:
                chunk.decode('latin-1')
                # If mostly printable, treat as text
                printable = sum(1 for b in chunk if 32 <= b <= 126 or b in (9, 10, 13))
                return printable / len(chunk) > 0.8
            except:
                pass
            
            return False
        except:
            return False
    
    # =========================================================================
    # INGESTION
    # =========================================================================
    
    def ingest(self, path: str | Path) -> List[Document]:
        """
        Ingest a file and return Documents ready for ReCog.
        
        Args:
            path: Path to file
        
        Returns:
            List of Document objects
        
        Raises:
            ValueError: If file is not supported
        """
        path = Path(path)
        result = self.detect(path)
        
        if not result.supported:
            raise ValueError(f"Unsupported file: {result.action_message}")
        
        parser = get_parser(path)
        if not parser:
            raise ValueError(f"No parser available for {path}")
        
        parsed = parser.parse(path)
        
        # Convert to Document
        doc = Document.create(
            content=parsed.text,
            source_type=result.file_type,
            source_ref=str(path),
            metadata={
                "filename": path.name,
                "title": parsed.title,
                "author": parsed.author,
                "date": parsed.date,
                **parsed.metadata,
            }
        )
        
        return [doc]
    
    def ingest_batch(self, paths: List[str | Path]) -> Tuple[List[Document], List[Dict]]:
        """
        Ingest multiple files.
        
        Args:
            paths: List of file paths
        
        Returns:
            Tuple of (successful documents, error reports)
        """
        documents = []
        errors = []
        
        for path in paths:
            try:
                docs = self.ingest(path)
                documents.extend(docs)
            except Exception as e:
                errors.append({
                    "path": str(path),
                    "error": str(e),
                })
        
        return documents, errors


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def detect_file(path: str | Path) -> FileDetectionResult:
    """Detect file format and get guidance."""
    return UniversalDetector().detect(path)


def ingest_file(path: str | Path) -> List[Document]:
    """Ingest a file and return Documents."""
    return UniversalDetector().ingest(path)


def get_format_info() -> Dict[str, Any]:
    """Get information about supported formats."""
    return {
        "supported": SUPPORTED_FORMATS,
        "containers": CONTAINER_FORMATS,
        "unsupported_with_help": list(UNSUPPORTED_WITH_SUGGESTIONS.keys()),
        "extensions": get_supported_extensions(),
    }


__all__ = [
    "UniversalDetector",
    "detect_file",
    "ingest_file",
    "get_format_info",
    "FileDetectionResult",
]

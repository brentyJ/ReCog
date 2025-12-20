"""
Document Ingestion Service v1.0

Main service for processing documents dropped into _inbox/.
"""

import hashlib
import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .types import IngestedDocument, DocumentChunk, ParsedContent
from .chunker import Chunker
from .parsers import get_parser

logger = logging.getLogger(__name__)


class IngestService:
    """
    Document ingestion service.
    
    Monitors inbox folder, parses documents, chunks content,
    and queues for ReCog processing.
    """
    
    def __init__(
        self,
        db_path: str,
        inbox_path: Optional[str] = None,
        processed_path: Optional[str] = None,
        chunk_tokens: int = 2000,
    ):
        """
        Args:
            db_path: Path to SQLite database
            inbox_path: Folder to watch for new documents
            processed_path: Folder to move processed documents
            chunk_tokens: Target chunk size in tokens
        """
        self.db_path = Path(db_path)
        
        # Default paths relative to EhkoForge root
        if inbox_path:
            self.inbox_path = Path(inbox_path)
        else:
            self.inbox_path = self.db_path.parent.parent / "_inbox"
        
        if processed_path:
            self.processed_path = Path(processed_path)
        else:
            self.processed_path = self.inbox_path / "_processed"
        
        self.chunker = Chunker(target_tokens=chunk_tokens)
        
        # Ensure directories exist
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        self.processed_path.mkdir(parents=True, exist_ok=True)
    
    def get_db(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    # =========================================================================
    # MAIN PROCESSING
    # =========================================================================
    
    def process_inbox(self, move_after: bool = True) -> Dict[str, Any]:
        """
        Process all files in inbox folder.
        
        Args:
            move_after: Move files to _processed after ingestion
        
        Returns:
            Summary of processing
        """
        results = {
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "files": [],
        }
        
        # Get all files (not directories)
        files = [f for f in self.inbox_path.iterdir() 
                 if f.is_file() and not f.name.startswith(".")]
        
        logger.info(f"Found {len(files)} files in inbox")
        
        for file_path in files:
            try:
                result = self.ingest_file(file_path, move_after=move_after)
                
                if result.get("skipped"):
                    results["skipped"] += 1
                elif result.get("error"):
                    results["failed"] += 1
                else:
                    results["processed"] += 1
                
                results["files"].append(result)
                
            except Exception as e:
                logger.error(f"Failed to process {file_path.name}: {e}")
                results["failed"] += 1
                results["files"].append({
                    "filename": file_path.name,
                    "error": str(e),
                })
        
        logger.info(
            f"Inbox processing complete: {results['processed']} processed, "
            f"{results['skipped']} skipped, {results['failed']} failed"
        )
        
        return results
    
    def ingest_file(
        self,
        file_path: Path,
        move_after: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest a single file.
        
        Args:
            file_path: Path to file
            move_after: Move to _processed after
        
        Returns:
            Ingestion result
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {"filename": file_path.name, "error": "File not found"}
        
        # Calculate hash
        file_hash = self._hash_file(file_path)
        
        # Check for duplicate
        if self._is_duplicate(file_hash):
            logger.info(f"Skipping duplicate: {file_path.name}")
            return {"filename": file_path.name, "skipped": True, "reason": "duplicate"}
        
        # Get parser
        parser = get_parser(file_path)
        if not parser:
            logger.warning(f"No parser for: {file_path.name}")
            return {"filename": file_path.name, "skipped": True, "reason": "unsupported"}
        
        logger.info(f"Parsing: {file_path.name} ({parser.get_file_type()})")
        
        try:
            # Parse
            parsed = parser.parse(file_path)
            
            # Create document record
            doc = IngestedDocument(
                filename=file_path.name,
                file_hash=file_hash,
                file_type=parser.get_file_type(),
                file_path=str(file_path),
                file_size=file_path.stat().st_size,
                doc_date=parsed.date,
                doc_author=parsed.author,
                doc_subject=parsed.subject or parsed.title,
                doc_recipients=parsed.recipients,
                metadata=parsed.metadata,
                status="chunking",
            )
            
            # Save document
            doc_id = self._save_document(doc)
            doc.id = doc_id
            
            self._log_action(doc_id, "parsing", {"parser": parser.get_file_type()})
            
            # Chunk
            chunks = self.chunker.chunk_parsed_content(parsed)
            doc.chunk_count = len(chunks)
            
            logger.info(f"Created {len(chunks)} chunks from {file_path.name}")
            
            # Save chunks
            self._save_chunks(doc_id, chunks)
            
            self._log_action(doc_id, "chunking", {"chunk_count": len(chunks)})
            
            # Update status
            self._update_document_status(doc_id, "pending", chunk_count=len(chunks))
            
            # Move file
            if move_after:
                dest = self.processed_path / file_path.name
                if dest.exists():
                    # Add timestamp to avoid collision
                    stem = file_path.stem
                    suffix = file_path.suffix
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dest = self.processed_path / f"{stem}_{timestamp}{suffix}"
                
                shutil.move(str(file_path), str(dest))
                logger.info(f"Moved to: {dest}")
            
            self._log_action(doc_id, "complete", {"moved_to": str(dest) if move_after else None})
            
            return {
                "filename": file_path.name,
                "document_id": doc_id,
                "file_type": parser.get_file_type(),
                "chunks": len(chunks),
                "title": parsed.title,
            }
            
        except Exception as e:
            logger.error(f"Error ingesting {file_path.name}: {e}")
            if 'doc_id' in locals():
                self._update_document_status(doc_id, "failed", error=str(e))
            return {"filename": file_path.name, "error": str(e)}
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    def _hash_file(self, path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _is_duplicate(self, file_hash: str) -> bool:
        """Check if file hash already exists."""
        conn = self.get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM ingested_documents WHERE file_hash = ?",
            (file_hash,)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def _save_document(self, doc: IngestedDocument) -> int:
        """Save document to database, return ID."""
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ingested_documents (
                filename, file_hash, file_type, file_path, file_size,
                doc_date, doc_author, doc_subject, doc_recipients,
                metadata, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc.filename,
            doc.file_hash,
            doc.file_type,
            doc.file_path,
            doc.file_size,
            doc.doc_date,
            doc.doc_author,
            doc.doc_subject,
            json.dumps(doc.doc_recipients) if doc.doc_recipients else None,
            json.dumps(doc.metadata) if doc.metadata else None,
            doc.status,
        ))
        
        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return doc_id
    
    def _save_chunks(self, doc_id: int, chunks: List[DocumentChunk]) -> None:
        """Save document chunks to database."""
        conn = self.get_db()
        cursor = conn.cursor()
        
        for chunk in chunks:
            cursor.execute("""
                INSERT INTO document_chunks (
                    document_id, chunk_index, content, token_count,
                    start_char, end_char, page_number,
                    preceding_context, following_context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id,
                chunk.chunk_index,
                chunk.content,
                chunk.token_count,
                chunk.start_char,
                chunk.end_char,
                chunk.page_number,
                chunk.preceding_context,
                chunk.following_context,
            ))
        
        conn.commit()
        conn.close()
    
    def _update_document_status(
        self,
        doc_id: int,
        status: str,
        chunk_count: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """Update document status."""
        conn = self.get_db()
        cursor = conn.cursor()
        
        if error:
            cursor.execute("""
                UPDATE ingested_documents 
                SET status = ?, error_message = ?
                WHERE id = ?
            """, (status, error, doc_id))
        elif chunk_count is not None:
            cursor.execute("""
                UPDATE ingested_documents 
                SET status = ?, chunk_count = ?
                WHERE id = ?
            """, (status, chunk_count, doc_id))
        else:
            cursor.execute("""
                UPDATE ingested_documents 
                SET status = ?
                WHERE id = ?
            """, (status, doc_id))
        
        conn.commit()
        conn.close()
    
    def _log_action(self, doc_id: int, action: str, details: Dict = None) -> None:
        """Log ingestion action."""
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ingestion_log (document_id, action, details)
            VALUES (?, ?, ?)
        """, (doc_id, action, json.dumps(details) if details else None))
        
        conn.commit()
        conn.close()
    
    # =========================================================================
    # QUERY METHODS
    # =========================================================================
    
    def get_pending_documents(self) -> List[Dict]:
        """Get documents pending ReCog processing."""
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, filename, file_type, chunk_count, doc_subject, ingested_at
            FROM ingested_documents
            WHERE status = 'pending'
            ORDER BY ingested_at ASC
        """)
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_unprocessed_chunks(self, limit: int = 100) -> List[Dict]:
        """Get chunks not yet processed by ReCog."""
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.id, c.document_id, c.chunk_index, c.content, c.token_count,
                c.preceding_context, c.following_context,
                d.filename, d.file_type, d.doc_subject
            FROM document_chunks c
            JOIN ingested_documents d ON c.document_id = d.id
            WHERE c.recog_processed = 0
            ORDER BY d.ingested_at ASC, c.chunk_index ASC
            LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics."""
        conn = self.get_db()
        cursor = conn.cursor()
        
        # Document counts by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM ingested_documents
            GROUP BY status
        """)
        status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        # Document counts by type
        cursor.execute("""
            SELECT file_type, COUNT(*) as count
            FROM ingested_documents
            GROUP BY file_type
        """)
        type_counts = {row["file_type"]: row["count"] for row in cursor.fetchall()}
        
        # Chunk stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_chunks,
                SUM(CASE WHEN recog_processed = 0 THEN 1 ELSE 0 END) as unprocessed,
                SUM(token_count) as total_tokens
            FROM document_chunks
        """)
        chunk_stats = dict(cursor.fetchone())
        
        conn.close()
        
        return {
            "documents": {
                "by_status": status_counts,
                "by_type": type_counts,
                "total": sum(status_counts.values()),
            },
            "chunks": chunk_stats,
        }

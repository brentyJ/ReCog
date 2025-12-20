"""
Document chunker with context preservation.

Splits large documents into processable chunks while maintaining:
- Source position tracking
- Overlapping context for coherence
- Token count estimation
"""

import re
from typing import List, Optional, Tuple
from .types import DocumentChunk, ParsedContent


class Chunker:
    """Splits documents into chunks with context preservation."""
    
    def __init__(
        self,
        target_tokens: int = 2000,
        overlap_tokens: int = 200,
        context_chars: int = 200,
    ):
        """
        Args:
            target_tokens: Target chunk size in tokens (~4 chars/token)
            overlap_tokens: Overlap between chunks for context
            context_chars: Characters of context to preserve
        """
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.context_chars = context_chars
        
        # Approximate chars per token
        self.chars_per_token = 4
        self.target_chars = target_tokens * self.chars_per_token
        self.overlap_chars = overlap_tokens * self.chars_per_token
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token count estimation."""
        return len(text) // self.chars_per_token
    
    def chunk_text(
        self,
        text: str,
        page_boundaries: Optional[List[int]] = None
    ) -> List[DocumentChunk]:
        """
        Split text into chunks.
        
        Args:
            text: Full document text
            page_boundaries: Character positions where pages start (for PDFs)
        
        Returns:
            List of DocumentChunk objects
        """
        if not text or not text.strip():
            return []
        
        text = text.strip()
        total_len = len(text)
        
        # If small enough, return as single chunk
        if total_len <= self.target_chars:
            return [DocumentChunk(
                content=text,
                chunk_index=0,
                token_count=self.estimate_tokens(text),
                start_char=0,
                end_char=total_len,
                page_number=self._get_page_number(0, page_boundaries),
                preceding_context="",
                following_context="",
            )]
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < total_len:
            # Calculate end position
            end = min(start + self.target_chars, total_len)
            
            # Try to break at sentence/paragraph boundary
            if end < total_len:
                end = self._find_break_point(text, start, end)
            
            # Extract chunk content
            content = text[start:end].strip()
            
            if content:
                # Get context
                preceding = text[max(0, start - self.context_chars):start].strip()
                following = text[end:min(total_len, end + self.context_chars)].strip()
                
                chunk = DocumentChunk(
                    content=content,
                    chunk_index=chunk_index,
                    token_count=self.estimate_tokens(content),
                    start_char=start,
                    end_char=end,
                    page_number=self._get_page_number(start, page_boundaries),
                    preceding_context=preceding,
                    following_context=following,
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # Move start position (with overlap)
            start = end - self.overlap_chars
            if start <= chunks[-1].start_char if chunks else 0:
                # Prevent infinite loop
                start = end
        
        return chunks
    
    def chunk_parsed_content(self, parsed: ParsedContent) -> List[DocumentChunk]:
        """
        Chunk parsed content, respecting page boundaries if available.
        """
        if parsed.pages:
            # Build page boundary positions
            boundaries = []
            pos = 0
            full_text_parts = []
            
            for page_text in parsed.pages:
                boundaries.append(pos)
                full_text_parts.append(page_text)
                pos += len(page_text) + 1  # +1 for newline between pages
            
            full_text = "\n".join(full_text_parts)
            return self.chunk_text(full_text, boundaries)
        else:
            return self.chunk_text(parsed.text)
    
    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """
        Find a good break point (paragraph > sentence > word).
        Searches backwards from end position.
        """
        search_start = max(start, end - 500)  # Look back up to 500 chars
        segment = text[search_start:end]
        
        # Try paragraph break (double newline)
        para_match = list(re.finditer(r'\n\n', segment))
        if para_match:
            return search_start + para_match[-1].end()
        
        # Try sentence break
        sentence_match = list(re.finditer(r'[.!?]\s+', segment))
        if sentence_match:
            return search_start + sentence_match[-1].end()
        
        # Try single newline
        newline_match = list(re.finditer(r'\n', segment))
        if newline_match:
            return search_start + newline_match[-1].end()
        
        # Try word break
        word_match = list(re.finditer(r'\s+', segment))
        if word_match:
            return search_start + word_match[-1].end()
        
        # No good break found, use original end
        return end
    
    def _get_page_number(
        self,
        char_pos: int,
        page_boundaries: Optional[List[int]]
    ) -> Optional[int]:
        """Get page number for a character position."""
        if not page_boundaries:
            return None
        
        for i, boundary in enumerate(page_boundaries):
            if char_pos < boundary:
                return i  # 0-indexed
        
        return len(page_boundaries) - 1

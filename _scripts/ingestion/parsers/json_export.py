"""
JSON Export parser for ChatGPT, Claude, and similar exports.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3

Phase 6 Refinements:
- Progress reporting callback for large exports
- Better edge case handling (tool calls, multimodal, empty content)
- Enhanced metadata extraction (model, timestamps, word counts)
- Container mode: return separate documents per conversation
"""

import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
import logging

from .base import BaseParser
from ..types import ParsedContent

logger = logging.getLogger(__name__)

# Progress callback signature: (current: int, total: int, message: str) -> None
ProgressCallback = Callable[[int, int, str], None]


class JSONExportParser(BaseParser):
    """
    Parse JSON exports from AI chat platforms.
    
    Supports:
    - ChatGPT exports (conversations.json format)
    - Claude exports
    - Generic conversation JSON
    - Message array formats
    
    Features:
    - Progress reporting for large exports
    - Handles tool calls and multimodal content
    - Extracts model and timing metadata
    - Can return as container (multiple documents)
    """
    
    def __init__(self, progress_callback: Optional[ProgressCallback] = None):
        """Initialize parser with optional progress callback."""
        self.progress_callback = progress_callback
        self._current_file: Optional[Path] = None
    
    def get_extensions(self) -> List[str]:
        return [".json"]
    
    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".json":
            return False
        
        # Quick check if it's a conversation-like JSON
        try:
            with open(path, 'r', encoding='utf-8') as f:
                # Read first 2000 chars to detect format
                sample = f.read(2000)
                
                # Look for conversation indicators
                indicators = [
                    '"messages"', '"conversations"', '"mapping"',
                    '"role"', '"content"', '"author"',
                    '"user"', '"assistant"', '"system"'
                ]
                
                return any(ind in sample for ind in indicators)
        except Exception as e:
            logger.debug(f"Error checking JSON file: {e}")
            return False
    
    def get_file_type(self) -> str:
        return "json_export"
    
    def is_container(self, path: Path) -> bool:
        """Check if this JSON contains multiple conversations."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # ChatGPT export is array of conversations
            if isinstance(data, list) and len(data) > 1:
                if data and isinstance(data[0], dict) and "mapping" in data[0]:
                    return True
            return False
        except:
            return False
    
    def _report_progress(self, current: int, total: int, message: str):
        """Report progress if callback is set."""
        if self.progress_callback:
            try:
                self.progress_callback(current, total, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    def parse(self, path: Path) -> ParsedContent:
        """Parse JSON export file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Detect format and parse accordingly
        if isinstance(data, list):
            # Array of conversations or messages
            if data and isinstance(data[0], dict):
                if "mapping" in data[0]:
                    # ChatGPT export format
                    return self._parse_chatgpt_export(data, path)
                elif "messages" in data[0]:
                    # Array of conversations with messages
                    return self._parse_conversation_array(data, path)
                elif "role" in data[0] or "author" in data[0]:
                    # Direct message array
                    return self._parse_message_array(data, path)
        
        elif isinstance(data, dict):
            if "mapping" in data:
                # Single ChatGPT conversation
                return self._parse_chatgpt_conversation(data, path)
            elif "messages" in data:
                # Single conversation with messages
                return self._parse_single_conversation(data, path)
        
        # Fallback: just stringify the JSON
        return ParsedContent(
            text=json.dumps(data, indent=2),
            title=path.stem,
            metadata={"format": "unknown_json"}
        )
    
    def _parse_chatgpt_export(self, conversations: List[Dict], path: Path) -> ParsedContent:
        """
        Parse ChatGPT full export format.
        
        Includes progress reporting for large exports.
        """
        all_text = []
        total_messages = 0
        total_words = 0
        models_used = set()
        date_range = {"earliest": None, "latest": None}
        
        total_convs = len(conversations)
        self._report_progress(0, total_convs, "Starting ChatGPT export parse...")
        
        for idx, conv in enumerate(conversations):
            title = conv.get("title", "Untitled")
            create_time = conv.get("create_time")
            update_time = conv.get("update_time")
            
            # Track date range
            for ts in [create_time, update_time]:
                if ts:
                    if date_range["earliest"] is None or ts < date_range["earliest"]:
                        date_range["earliest"] = ts
                    if date_range["latest"] is None or ts > date_range["latest"]:
                        date_range["latest"] = ts
            
            all_text.append(f"\n{'='*60}")
            all_text.append(f"Conversation: {title}")
            if create_time:
                try:
                    dt = datetime.fromtimestamp(create_time)
                    all_text.append(f"Date: {dt.strftime('%Y-%m-%d %H:%M')}")
                except:
                    pass
            all_text.append("="*60 + "\n")
            
            # Parse mapping structure
            mapping = conv.get("mapping", {})
            messages = self._extract_chatgpt_messages(mapping)
            total_messages += len(messages)
            
            for msg in messages:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                model = msg.get("model")
                
                if model:
                    models_used.add(model)
                
                all_text.append(f"**{role}:**")
                all_text.append(content)
                all_text.append("")
                
                # Count words (rough estimate)
                total_words += len(content.split())
            
            # Report progress every 10 conversations or for small exports
            if (idx + 1) % 10 == 0 or total_convs <= 20:
                self._report_progress(
                    idx + 1, total_convs,
                    f"Parsed {idx + 1}/{total_convs} conversations ({total_messages} messages)"
                )
        
        self._report_progress(total_convs, total_convs, "Parse complete")
        
        # Format date range for metadata
        date_range_str = None
        if date_range["earliest"] and date_range["latest"]:
            try:
                start = datetime.fromtimestamp(date_range["earliest"]).strftime('%Y-%m-%d')
                end = datetime.fromtimestamp(date_range["latest"]).strftime('%Y-%m-%d')
                date_range_str = f"{start} to {end}"
            except:
                pass
        
        return ParsedContent(
            text="\n".join(all_text),
            title=f"ChatGPT Export - {len(conversations)} conversations",
            metadata={
                "format": "chatgpt_export",
                "conversation_count": len(conversations),
                "message_count": total_messages,
                "word_count": total_words,
                "models_used": list(models_used) if models_used else None,
                "date_range": date_range_str,
            }
        )
    
    def _extract_chatgpt_messages(self, mapping: Dict) -> List[Dict]:
        """
        Extract messages from ChatGPT mapping structure.
        
        Handles edge cases:
        - Tool calls (code interpreter, plugins)
        - Multimodal content (images, files) 
        - Empty/null content
        - System messages
        - Model metadata
        """
        messages = []
        models_used = set()
        
        for node_id, node in mapping.items():
            message = node.get("message")
            if not message:
                continue
            
            author = message.get("author", {})
            role = author.get("role", "unknown")
            
            # Skip system messages unless they have meaningful content
            if role == "system":
                continue
            
            # Extract model info if available
            model_slug = message.get("metadata", {}).get("model_slug")
            if model_slug:
                models_used.add(model_slug)
            
            # Handle content extraction
            content_obj = message.get("content", {})
            content_type = content_obj.get("content_type", "text")
            
            # Handle different content types
            if content_type == "text":
                content_parts = content_obj.get("parts", [])
                content = self._extract_text_parts(content_parts)
            elif content_type == "code":
                # Code interpreter input
                code_text = content_obj.get("text", "")
                content = f"[Code]\n```\n{code_text}\n```"
            elif content_type == "execution_output":
                # Code interpreter output
                output = content_obj.get("text", "")
                content = f"[Output]\n{output}"
            elif content_type == "multimodal_text":
                # Contains images or other media
                parts = content_obj.get("parts", [])
                content = self._extract_multimodal_parts(parts)
            else:
                # Unknown content type - try to extract something
                content = str(content_obj.get("parts", content_obj.get("text", "")))
            
            # Handle tool calls
            if role == "tool":
                tool_name = author.get("name", "tool")
                content = f"[Tool: {tool_name}]\n{content}"
            
            if content and content.strip():
                messages.append({
                    "role": role,
                    "content": content.strip(),
                    "create_time": message.get("create_time"),
                    "model": model_slug,
                })
        
        # Sort by create_time if available
        messages.sort(key=lambda m: m.get("create_time") or 0)
        
        return messages
    
    def _extract_text_parts(self, parts: List) -> str:
        """Extract text from content parts, handling various types."""
        text_pieces = []
        for part in parts:
            if part is None:
                continue
            if isinstance(part, str):
                text_pieces.append(part)
            elif isinstance(part, dict):
                # Could be image reference or other structured content
                if "text" in part:
                    text_pieces.append(part["text"])
                elif "asset_pointer" in part:
                    text_pieces.append("[Image]")
                else:
                    # Unknown structure, stringify it
                    text_pieces.append(f"[Content: {list(part.keys())}]")
            else:
                text_pieces.append(str(part))
        return "\n".join(text_pieces)
    
    def _extract_multimodal_parts(self, parts: List) -> str:
        """Extract content from multimodal message parts."""
        text_pieces = []
        for part in parts:
            if isinstance(part, str):
                text_pieces.append(part)
            elif isinstance(part, dict):
                content_type = part.get("content_type", "")
                if content_type == "image_asset_pointer":
                    text_pieces.append("[Image uploaded]")
                elif content_type == "text":
                    text_pieces.append(part.get("text", ""))
                elif "asset_pointer" in part:
                    text_pieces.append("[File attachment]")
                else:
                    text_pieces.append(f"[{content_type or 'attachment'}]")
        return "\n".join(text_pieces)
    
    def _parse_chatgpt_conversation(self, conv: Dict, path: Path) -> ParsedContent:
        """Parse single ChatGPT conversation."""
        return self._parse_chatgpt_export([conv], path)
    
    def parse_as_container(self, path: Path) -> List[ParsedContent]:
        """
        Parse ChatGPT export as multiple documents (one per conversation).
        
        Useful for preflight workflow where each conversation can be
        reviewed/filtered independently.
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            # Single conversation or non-array format
            return [self.parse(path)]
        
        documents = []
        total = len(data)
        
        self._report_progress(0, total, f"Parsing {total} conversations...")
        
        for idx, conv in enumerate(data):
            if not isinstance(conv, dict):
                continue
            
            # Only process ChatGPT format conversations
            if "mapping" not in conv:
                continue
            
            title = conv.get("title", f"Conversation {idx + 1}")
            create_time = conv.get("create_time")
            
            # Extract messages
            mapping = conv.get("mapping", {})
            messages = self._extract_chatgpt_messages(mapping)
            
            if not messages:
                continue
            
            # Build text for this conversation
            text_parts = []
            word_count = 0
            models = set()
            
            for msg in messages:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                model = msg.get("model")
                
                if model:
                    models.add(model)
                
                text_parts.append(f"**{role}:** {content}\n")
                word_count += len(content.split())
            
            # Build metadata
            metadata = {
                "format": "chatgpt_conversation",
                "message_count": len(messages),
                "word_count": word_count,
                "source_file": path.name,
                "conversation_index": idx,
            }
            
            if create_time:
                try:
                    metadata["date"] = datetime.fromtimestamp(create_time).isoformat()
                except:
                    pass
            
            if models:
                metadata["models_used"] = list(models)
            
            documents.append(ParsedContent(
                text="\n".join(text_parts),
                title=title,
                metadata=metadata,
            ))
            
            # Progress reporting
            if (idx + 1) % 20 == 0:
                self._report_progress(
                    idx + 1, total,
                    f"Parsed {idx + 1}/{total} conversations"
                )
        
        self._report_progress(total, total, f"Complete: {len(documents)} conversations")
        
        logger.info(f"Parsed {len(documents)} conversations from {path.name}")
        return documents
    
    def _parse_conversation_array(self, conversations: List[Dict], path: Path) -> ParsedContent:
        """Parse array of conversations with messages field."""
        all_text = []
        
        for conv in conversations:
            title = conv.get("title", conv.get("name", "Untitled"))
            all_text.append(f"\n--- {title} ---\n")
            
            messages = conv.get("messages", [])
            for msg in messages:
                role = msg.get("role", msg.get("author", "unknown")).upper()
                content = msg.get("content", msg.get("text", ""))
                all_text.append(f"**{role}:** {content}\n")
        
        return ParsedContent(
            text="\n".join(all_text),
            title=path.stem,
            metadata={"format": "conversation_array", "count": len(conversations)}
        )
    
    def _parse_message_array(self, messages: List[Dict], path: Path) -> ParsedContent:
        """Parse direct array of messages."""
        all_text = []
        
        for msg in messages:
            role = msg.get("role", msg.get("author", "unknown")).upper()
            content = msg.get("content", msg.get("text", ""))
            all_text.append(f"**{role}:** {content}\n")
        
        return ParsedContent(
            text="\n".join(all_text),
            title=path.stem,
            metadata={"format": "message_array", "count": len(messages)}
        )
    
    def _parse_single_conversation(self, conv: Dict, path: Path) -> ParsedContent:
        """Parse single conversation with messages field."""
        return self._parse_conversation_array([conv], path)


__all__ = ["JSONExportParser"]

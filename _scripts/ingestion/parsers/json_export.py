"""
JSON Export parser for ChatGPT, Claude, and similar exports.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import BaseParser
from ..types import ParsedContent


class JSONExportParser(BaseParser):
    """
    Parse JSON exports from AI chat platforms.
    
    Supports:
    - ChatGPT exports (conversations.json format)
    - Generic conversation JSON
    - Message array formats
    """
    
    def get_extensions(self) -> List[str]:
        return [".json"]
    
    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".json":
            return False
        
        # Quick check if it's a conversation-like JSON
        try:
            with open(path, 'r', encoding='utf-8') as f:
                # Read first 1000 chars to detect format
                sample = f.read(1000)
                
                # Look for conversation indicators
                indicators = [
                    '"messages"', '"conversations"', '"mapping"',
                    '"role"', '"content"', '"author"',
                    '"user"', '"assistant"', '"system"'
                ]
                
                return any(ind in sample for ind in indicators)
        except:
            return False
    
    def get_file_type(self) -> str:
        return "json_export"
    
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
        """Parse ChatGPT full export format."""
        all_text = []
        total_messages = 0
        
        for conv in conversations:
            title = conv.get("title", "Untitled")
            create_time = conv.get("create_time")
            
            all_text.append(f"\n{'='*60}")
            all_text.append(f"Conversation: {title}")
            if create_time:
                try:
                    dt = datetime.fromtimestamp(create_time)
                    all_text.append(f"Date: {dt.isoformat()}")
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
                all_text.append(f"**{role}:**")
                all_text.append(content)
                all_text.append("")
        
        return ParsedContent(
            text="\n".join(all_text),
            title=f"ChatGPT Export - {len(conversations)} conversations",
            metadata={
                "format": "chatgpt_export",
                "conversation_count": len(conversations),
                "message_count": total_messages,
            }
        )
    
    def _extract_chatgpt_messages(self, mapping: Dict) -> List[Dict]:
        """Extract messages from ChatGPT mapping structure."""
        messages = []
        
        for node_id, node in mapping.items():
            message = node.get("message")
            if not message:
                continue
            
            author = message.get("author", {})
            role = author.get("role", "unknown")
            
            content_parts = message.get("content", {}).get("parts", [])
            content = "\n".join(str(p) for p in content_parts if p)
            
            if content.strip():
                messages.append({
                    "role": role,
                    "content": content,
                    "create_time": message.get("create_time"),
                })
        
        # Sort by create_time if available
        messages.sort(key=lambda m: m.get("create_time") or 0)
        
        return messages
    
    def _parse_chatgpt_conversation(self, conv: Dict, path: Path) -> ParsedContent:
        """Parse single ChatGPT conversation."""
        return self._parse_chatgpt_export([conv], path)
    
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

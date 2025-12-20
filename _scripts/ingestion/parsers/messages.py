"""
Message export parser.

Handles:
- WhatsApp exports (.txt)
- iMessage exports (various formats)
- SMS backup exports
- Generic chat logs
"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import xml.etree.ElementTree as ET

from .base import BaseParser
from ..types import ParsedContent


class MessagesParser(BaseParser):
    """
    Parse message/chat exports from various platforms.
    
    Detects format from content and extracts:
    - Individual messages with timestamps
    - Participants
    - Thread structure
    """
    
    def get_extensions(self):
        return [".txt", ".xml", ".csv"]  # Various message export formats
    
    # WhatsApp patterns
    WHATSAPP_PATTERN = re.compile(
        r'^\[?(\d{1,2}/\d{1,2}/\d{2,4},?\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\]?\s*-?\s*([^:]+):\s*(.+)$',
        re.MULTILINE
    )
    
    # Generic chat pattern: [timestamp] name: message
    GENERIC_CHAT_PATTERN = re.compile(
        r'^\[?(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}(?::\d{2})?)\]?\s*([^:]+):\s*(.+)$',
        re.MULTILINE
    )
    
    # iMessage/SMS pattern varies widely
    IMESSAGE_PATTERN = re.compile(
        r'^(Read|Delivered|Sent)?\s*(\w+\s+\d+,\s+\d{4}\s+at\s+\d+:\d+\s*(?:AM|PM)?)\s*\n?(.+?)(?=\n(?:Read|Delivered|Sent|\w+\s+\d+)|$)',
        re.MULTILINE | re.DOTALL
    )
    
    def can_parse(self, path: Path) -> bool:
        """Check if file looks like a message export."""
        if path.suffix.lower() not in (".txt", ".json", ".csv", ".xml"):
            return False
        
        # Quick content check
        try:
            content = path.read_text(encoding="utf-8", errors="replace")[:2000]
            return self._detect_message_format(content) is not None
        except:
            return False
    
    def get_file_type(self) -> str:
        return "messages"
    
    def parse(self, path: Path) -> ParsedContent:
        """
        Parse message export file.
        """
        content = path.read_text(encoding="utf-8", errors="replace")
        
        # Detect format
        format_type = self._detect_message_format(content)
        
        if format_type == "sms_xml":
            messages, participants = self._parse_sms_backup_xml(content)
        elif format_type == "whatsapp":
            messages, participants = self._parse_whatsapp(content)
        elif format_type == "json":
            messages, participants = self._parse_json_messages(content)
        elif format_type == "generic":
            messages, participants = self._parse_generic_chat(content)
        else:
            # Fall back to treating as plain text
            return ParsedContent(
                text=content,
                metadata={"format": "unknown_messages"},
                title=path.stem,
            )
        
        # Build structured output
        formatted_text = self._format_messages(messages)
        
        # Extract date range
        dates = [m.get("timestamp") for m in messages if m.get("timestamp")]
        first_date = min(dates) if dates else None
        last_date = max(dates) if dates else None
        
        metadata = {
            "format": format_type,
            "message_count": len(messages),
            "participants": participants,
            "first_message": first_date,
            "last_message": last_date,
            "messages": messages,  # Preserve structured data
        }
        
        return ParsedContent(
            text=formatted_text,
            metadata=metadata,
            title=f"Chat: {', '.join(participants[:3])}{'...' if len(participants) > 3 else ''}",
            date=first_date,
            recipients=participants,
        )
    
    def _detect_message_format(self, content: str) -> Optional[str]:
        """Detect the message format from content."""
        # Check for SMS Backup & Restore XML format
        if "<smses" in content[:500] or "SMS Backup & Restore" in content[:500]:
            return "sms_xml"
        
        # Check for JSON
        if content.strip().startswith(("{", "[")):
            try:
                json.loads(content)
                return "json"
            except:
                pass
        
        # Check for WhatsApp format
        if self.WHATSAPP_PATTERN.search(content[:2000]):
            return "whatsapp"
        
        # Check for generic chat format
        if self.GENERIC_CHAT_PATTERN.search(content[:2000]):
            return "generic"
        
        # Check for indicators
        whatsapp_indicators = [
            "Messages and calls are end-to-end encrypted",
            "Media omitted",
            "<attached:",
        ]
        for indicator in whatsapp_indicators:
            if indicator in content[:5000]:
                return "whatsapp"
        
        return None
    
    def _parse_sms_backup_xml(self, content: str) -> Tuple[List[Dict], List[str]]:
        """Parse SMS Backup & Restore XML format."""
        messages = []
        participants = set()
        
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return [], []
        
        # Find all sms elements
        for sms in root.findall('.//sms'):
            msg_type = sms.get('type', '1')  # 1=received, 2=sent
            body = sms.get('body', '')
            contact_name = sms.get('contact_name', 'Unknown')
            readable_date = sms.get('readable_date', '')
            date_ms = sms.get('date', '')
            
            # Skip empty messages
            if not body or body == 'null':
                continue
            
            # Decode HTML entities
            body = body.replace('&#10;', '\n')
            
            # Determine sender
            if msg_type == '2':  # Sent by user
                sender = 'Me'
            else:  # Received
                sender = contact_name if contact_name != '(Unknown)' else 'Unknown'
            
            participants.add(contact_name)
            
            # Parse timestamp
            timestamp = None
            if date_ms and date_ms.isdigit():
                try:
                    timestamp = datetime.fromtimestamp(int(date_ms) / 1000).isoformat()
                except:
                    timestamp = readable_date
            else:
                timestamp = readable_date
            
            messages.append({
                "timestamp": timestamp,
                "sender": sender,
                "text": body,
                "contact": contact_name,
                "direction": "sent" if msg_type == '2' else "received",
            })
        
        # Sort by timestamp
        messages.sort(key=lambda m: m.get('timestamp', '') or '')
        
        return messages, list(participants)
    
    def _parse_whatsapp(self, content: str) -> Tuple[List[Dict], List[str]]:
        """Parse WhatsApp export format."""
        messages = []
        participants = set()
        
        for match in self.WHATSAPP_PATTERN.finditer(content):
            timestamp_str, sender, text = match.groups()
            
            # Skip system messages
            if sender.strip() in ("", "Messages and calls are end-to-end encrypted"):
                continue
            
            sender = sender.strip()
            participants.add(sender)
            
            # Parse timestamp
            timestamp = self._parse_whatsapp_timestamp(timestamp_str)
            
            messages.append({
                "timestamp": timestamp,
                "sender": sender,
                "text": text.strip(),
                "raw_timestamp": timestamp_str,
            })
        
        return messages, list(participants)
    
    def _parse_whatsapp_timestamp(self, ts: str) -> Optional[str]:
        """Parse WhatsApp timestamp to ISO format."""
        patterns = [
            "%d/%m/%Y, %H:%M",
            "%d/%m/%y, %H:%M",
            "%m/%d/%Y, %H:%M",
            "%m/%d/%y, %H:%M",
            "%d/%m/%Y, %I:%M %p",
            "%m/%d/%Y, %I:%M %p",
        ]
        
        ts = ts.strip().replace("\u202f", " ")  # Handle narrow no-break space
        
        for pattern in patterns:
            try:
                dt = datetime.strptime(ts, pattern)
                return dt.isoformat()
            except ValueError:
                continue
        
        return None
    
    def _parse_json_messages(self, content: str) -> Tuple[List[Dict], List[str]]:
        """Parse JSON message export."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return [], []
        
        messages = []
        participants = set()
        
        # Handle various JSON structures
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("messages", data.get("data", []))
        else:
            return [], []
        
        for item in items:
            if not isinstance(item, dict):
                continue
            
            # Try common field names
            sender = item.get("sender") or item.get("from") or item.get("author") or ""
            text = item.get("text") or item.get("message") or item.get("content") or item.get("body") or ""
            timestamp = item.get("timestamp") or item.get("date") or item.get("time") or ""
            
            if text:
                if sender:
                    participants.add(sender)
                
                messages.append({
                    "timestamp": str(timestamp) if timestamp else None,
                    "sender": sender,
                    "text": str(text),
                })
        
        return messages, list(participants)
    
    def _parse_generic_chat(self, content: str) -> Tuple[List[Dict], List[str]]:
        """Parse generic chat log format."""
        messages = []
        participants = set()
        
        for match in self.GENERIC_CHAT_PATTERN.finditer(content):
            timestamp_str, sender, text = match.groups()
            
            sender = sender.strip()
            participants.add(sender)
            
            messages.append({
                "timestamp": timestamp_str,
                "sender": sender,
                "text": text.strip(),
            })
        
        return messages, list(participants)
    
    def _format_messages(self, messages: List[Dict]) -> str:
        """Format messages into readable text."""
        lines = []
        
        for msg in messages:
            sender = msg.get("sender", "Unknown")
            text = msg.get("text", "")
            timestamp = msg.get("timestamp", "")
            
            if timestamp:
                lines.append(f"[{timestamp}] {sender}: {text}")
            else:
                lines.append(f"{sender}: {text}")
        
        return "\n".join(lines)

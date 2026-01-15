"""
Email file parsers for MSG (Outlook) and EML (standard) formats.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import email
import re
from email.policy import default as email_policy
from email.utils import parsedate_to_datetime, getaddresses
from pathlib import Path
from typing import List, Optional, Dict, Any

from .base import BaseParser
from ..types import ParsedContent


class EmlParser(BaseParser):
    """Parse standard EML email files."""

    PARSER_METADATA = {
        "file_type": "Email Message (EML)",
        "extensions": [".eml"],
        "cypher_context": {
            "description": "Standard email message file with headers and body",
            "extractable": [
                "Sender and recipients (To, CC, BCC)",
                "Subject and date",
                "Email body (plain text and HTML)",
                "Attachment list"
            ],
            "suggestions": [
                "Check email headers for routing information",
                "Attachments are listed but not extracted",
                "Thread references can show conversation context"
            ]
        }
    }

    def get_extensions(self) -> List[str]:
        return [".eml"]

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".eml":
            return False
        # Verify it looks like an email file
        try:
            with open(path, 'rb') as f:
                first_lines = f.read(500).decode('utf-8', errors='ignore')
                # Check for common email headers
                return any(h in first_lines for h in ['From:', 'Received:', 'MIME-Version:', 'Date:'])
        except Exception:
            return False

    def get_file_type(self) -> str:
        return "eml"

    def parse(self, path: Path) -> ParsedContent:
        """Parse EML file and extract email content."""
        try:
            with open(path, 'rb') as f:
                msg = email.message_from_binary_file(f, policy=email_policy)
        except Exception as e:
            return ParsedContent(
                text=f"[Error opening EML file: {e}]",
                title=path.stem,
                metadata={"error": "open_failed", "details": str(e)}
            )

        # Extract headers
        subject = msg.get('Subject', '(No Subject)')
        from_addr = msg.get('From', '')
        to_addr = msg.get('To', '')
        cc_addr = msg.get('Cc', '')
        bcc_addr = msg.get('Bcc', '')
        date_str = msg.get('Date', '')
        message_id = msg.get('Message-ID', '')
        in_reply_to = msg.get('In-Reply-To', '')

        # Parse date
        date_iso = self._parse_date(date_str)

        # Extract body
        body = self._get_body(msg)

        # Get attachments
        attachments = self._get_attachments(msg)

        # Build text representation
        lines = [
            f"From: {from_addr}",
            f"To: {to_addr}",
        ]
        if cc_addr:
            lines.append(f"Cc: {cc_addr}")
        if bcc_addr:
            lines.append(f"Bcc: {bcc_addr}")
        lines.extend([
            f"Subject: {subject}",
            f"Date: {date_str}",
        ])
        if attachments:
            lines.append(f"Attachments: {', '.join(attachments)}")
        lines.extend(["", body])

        full_text = "\n".join(lines)

        # Build metadata
        recipients = self._parse_recipients(to_addr)
        if cc_addr:
            recipients.extend(self._parse_recipients(cc_addr))

        metadata = {
            "format": "eml",
            "from": from_addr,
            "to": to_addr,
            "cc": cc_addr or None,
            "bcc": bcc_addr or None,
            "subject": subject,
            "message_id": message_id or None,
            "in_reply_to": in_reply_to or None,
            "attachments": attachments,
            "attachment_count": len(attachments),
        }

        return ParsedContent(
            text=full_text,
            title=subject or path.stem,
            author=self._extract_email_addr(from_addr),
            date=date_iso,
            recipients=recipients,
            metadata=metadata
        )

    def _get_body(self, msg) -> str:
        """Extract email body, preferring plain text."""
        if msg.is_multipart():
            # Try plain text first
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get('Content-Disposition', ''))

                if 'attachment' in disposition:
                    continue

                if content_type == 'text/plain':
                    try:
                        return part.get_content()
                    except Exception:
                        continue

            # Fall back to HTML
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get('Content-Disposition', ''))

                if 'attachment' in disposition:
                    continue

                if content_type == 'text/html':
                    try:
                        html = part.get_content()
                        return self._strip_html(html)
                    except Exception:
                        continue

            return "(No readable body content)"
        else:
            try:
                content = msg.get_content()
                if msg.get_content_type() == 'text/html':
                    return self._strip_html(content)
                return content
            except Exception:
                return "(Unable to decode body)"

    def _strip_html(self, html: str) -> str:
        """Remove HTML tags and clean up text."""
        # Remove script and style
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', html)

        # Decode entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')

        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _get_attachments(self, msg) -> List[str]:
        """Get list of attachment filenames."""
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                disposition = str(part.get('Content-Disposition', ''))
                if 'attachment' in disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append(filename)
                    else:
                        attachments.append(f"unnamed.{part.get_content_subtype()}")
        return attachments

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse email date to ISO format."""
        if not date_str:
            return None
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.date().isoformat()
        except Exception:
            return None

    def _parse_recipients(self, addr_str: str) -> List[str]:
        """Parse address header into list of emails."""
        if not addr_str:
            return []
        return [addr for name, addr in getaddresses([addr_str]) if addr]

    def _extract_email_addr(self, addr_str: str) -> Optional[str]:
        """Extract just the email address."""
        if not addr_str:
            return None
        addresses = getaddresses([addr_str])
        return addresses[0][1] if addresses else None


class MsgParser(BaseParser):
    """Parse Microsoft Outlook MSG files."""

    PARSER_METADATA = {
        "file_type": "Outlook Email (MSG)",
        "extensions": [".msg"],
        "cypher_context": {
            "description": "Microsoft Outlook email message with rich metadata",
            "extractable": [
                "Sender and recipients",
                "Subject, date, and importance",
                "Email body (RTF, HTML, plain text)",
                "Attachments and embedded objects"
            ],
            "suggestions": [
                "MSG files preserve Outlook-specific metadata",
                "Check importance and sensitivity flags",
                "Embedded images may be attachments"
            ]
        }
    }

    def get_extensions(self) -> List[str]:
        return [".msg"]

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".msg":
            return False
        # Check for OLE compound document signature
        try:
            with open(path, 'rb') as f:
                signature = f.read(8)
                # OLE signature: D0 CF 11 E0 A1 B1 1A E1
                return signature[:4] == b'\xd0\xcf\x11\xe0'
        except Exception:
            return False

    def get_file_type(self) -> str:
        return "msg"

    def parse(self, path: Path) -> ParsedContent:
        """Parse MSG file and extract email content."""
        try:
            import extract_msg
        except ImportError:
            return ParsedContent(
                text="[MSG parsing requires extract-msg: pip install extract-msg]",
                title=path.stem,
                metadata={"error": "extract-msg not installed"}
            )

        try:
            msg = extract_msg.Message(str(path))
        except Exception as e:
            return ParsedContent(
                text=f"[Error opening MSG file: {e}]",
                title=path.stem,
                metadata={"error": "open_failed", "details": str(e)}
            )

        try:
            # Extract fields
            subject = msg.subject or '(No Subject)'
            sender = msg.sender or ''
            to = msg.to or ''
            cc = msg.cc or ''
            date_str = str(msg.date) if msg.date else ''

            # Get body (prefer plain text)
            body = msg.body or ''
            if not body and hasattr(msg, 'htmlBody') and msg.htmlBody:
                body = self._strip_html(msg.htmlBody)

            # Get attachments
            attachments = []
            if hasattr(msg, 'attachments') and msg.attachments:
                for att in msg.attachments:
                    if hasattr(att, 'longFilename') and att.longFilename:
                        attachments.append(att.longFilename)
                    elif hasattr(att, 'shortFilename') and att.shortFilename:
                        attachments.append(att.shortFilename)
                    else:
                        attachments.append('unnamed_attachment')

            # Build text representation
            lines = [
                f"From: {sender}",
                f"To: {to}",
            ]
            if cc:
                lines.append(f"Cc: {cc}")
            lines.extend([
                f"Subject: {subject}",
                f"Date: {date_str}",
            ])
            if attachments:
                lines.append(f"Attachments: {', '.join(attachments)}")
            lines.extend(["", body])

            full_text = "\n".join(lines)

            # Parse date
            date_iso = None
            if msg.date:
                try:
                    date_iso = msg.date.date().isoformat()
                except Exception:
                    pass

            # Build metadata
            metadata = {
                "format": "msg",
                "from": sender,
                "to": to,
                "cc": cc or None,
                "subject": subject,
                "attachments": attachments,
                "attachment_count": len(attachments),
            }

            # Add Outlook-specific metadata if available
            if hasattr(msg, 'importance') and msg.importance:
                metadata["importance"] = str(msg.importance)
            if hasattr(msg, 'sensitivity') and msg.sensitivity:
                metadata["sensitivity"] = str(msg.sensitivity)
            if hasattr(msg, 'messageId') and msg.messageId:
                metadata["message_id"] = msg.messageId

            # Parse recipients
            recipients = []
            if to:
                recipients = [addr.strip() for addr in to.split(';') if addr.strip()]

            return ParsedContent(
                text=full_text,
                title=subject,
                author=sender,
                date=date_iso,
                recipients=recipients,
                metadata=metadata
            )

        finally:
            msg.close()

    def _strip_html(self, html: str) -> str:
        """Remove HTML tags and clean up text."""
        if not html:
            return ""
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


__all__ = ["EmlParser", "MsgParser"]

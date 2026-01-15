"""
MBOX email archive parser.

Parses standard MBOX format email archives, extracting headers, body text,
and attachment information from each message.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import mailbox
import re
from email.utils import parsedate_to_datetime, getaddresses
from pathlib import Path
from typing import List, Optional

from .base import BaseParser
from ..types import ParsedContent


class MboxParser(BaseParser):
    """Parse MBOX email archive files."""

    def get_extensions(self) -> List[str]:
        return [".mbox"]

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".mbox":
            return False
        # Verify it looks like an mbox file (starts with "From ")
        try:
            with open(path, 'rb') as f:
                first_line = f.readline()
                return first_line.startswith(b'From ')
        except Exception:
            return False

    def get_file_type(self) -> str:
        return "mbox"

    def parse(self, path: Path) -> ParsedContent:
        """
        Parse MBOX file and extract all emails.

        Args:
            path: Path to .mbox file

        Returns:
            ParsedContent with all emails concatenated
        """
        try:
            mbox = mailbox.mbox(str(path))
        except Exception as e:
            return ParsedContent(
                text=f"[Error opening MBOX file: {e}]",
                title=path.stem,
                metadata={"error": "open_failed", "details": str(e)}
            )

        emails = []
        total_attachments = 0
        senders = set()
        recipients_all = set()
        dates = []

        for i, message in enumerate(mbox):
            try:
                email_data = self._parse_message(message, i + 1)
                emails.append(email_data["text"])

                if email_data.get("from"):
                    senders.add(email_data["from"])
                if email_data.get("recipients"):
                    recipients_all.update(email_data["recipients"])
                if email_data.get("date"):
                    dates.append(email_data["date"])
                total_attachments += email_data.get("attachment_count", 0)
            except Exception as e:
                emails.append(f"--- Email {i + 1} ---\n[Parse error: {e}]\n")

        mbox.close()

        # Combine all emails
        full_text = "\n\n".join(emails)

        # Determine date range
        date_range = None
        if dates:
            dates_sorted = sorted(dates)
            if len(dates_sorted) > 1:
                date_range = f"{dates_sorted[0]} to {dates_sorted[-1]}"
            else:
                date_range = dates_sorted[0]

        return ParsedContent(
            text=full_text,
            title=f"{path.stem} ({len(emails)} emails)",
            metadata={
                "format": "mbox",
                "email_count": len(emails),
                "total_attachments": total_attachments,
                "unique_senders": len(senders),
                "unique_recipients": len(recipients_all),
                "date_range": date_range,
                "senders": list(senders)[:20],  # Limit for metadata
                "recipients": list(recipients_all)[:20],
            }
        )

    def _parse_message(self, message, index: int) -> dict:
        """Parse a single email message."""
        # Extract headers
        subject = message.get('Subject', '(No Subject)')
        from_addr = message.get('From', '')
        to_addr = message.get('To', '')
        cc_addr = message.get('Cc', '')
        date_str = message.get('Date', '')

        # Parse date
        date_iso = self._parse_date(date_str)

        # Parse recipients
        recipients = self._parse_recipients(to_addr)
        if cc_addr:
            recipients.extend(self._parse_recipients(cc_addr))

        # Extract body
        body = self._get_body(message)

        # Get attachment names
        attachments = self._get_attachments(message)

        # Build text representation
        lines = [
            f"--- Email {index} ---",
            f"From: {from_addr}",
            f"To: {to_addr}",
        ]
        if cc_addr:
            lines.append(f"Cc: {cc_addr}")
        lines.extend([
            f"Subject: {subject}",
            f"Date: {date_str}",
        ])
        if attachments:
            lines.append(f"Attachments: {', '.join(attachments)}")
        lines.extend(["", body])

        return {
            "text": "\n".join(lines),
            "from": self._extract_email(from_addr),
            "recipients": recipients,
            "date": date_iso,
            "attachment_count": len(attachments),
        }

    def _get_body(self, message) -> str:
        """Extract email body, preferring plain text."""
        if message.is_multipart():
            # Try to find plain text part first
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            return payload.decode(charset, errors='replace')
                    except Exception:
                        continue

            # Fall back to HTML
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    continue

                if content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            html = payload.decode(charset, errors='replace')
                            return self._strip_html(html)
                    except Exception:
                        continue

            return "(No readable body content)"
        else:
            # Non-multipart message
            try:
                payload = message.get_payload(decode=True)
                if payload:
                    charset = message.get_content_charset() or 'utf-8'
                    text = payload.decode(charset, errors='replace')
                    if message.get_content_type() == "text/html":
                        return self._strip_html(text)
                    return text
            except Exception:
                pass
            return "(Unable to decode body)"

    def _strip_html(self, html: str) -> str:
        """Remove HTML tags and decode entities."""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)

        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")

        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)

        return text.strip()

    def _get_attachments(self, message) -> List[str]:
        """Get list of attachment filenames."""
        attachments = []
        if message.is_multipart():
            for part in message.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in content_disposition:
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
        """Parse address header into list of email addresses."""
        if not addr_str:
            return []
        return [addr for name, addr in getaddresses([addr_str]) if addr]

    def _extract_email(self, addr_str: str) -> Optional[str]:
        """Extract just the email address from a From header."""
        if not addr_str:
            return None
        addresses = getaddresses([addr_str])
        if addresses:
            return addresses[0][1] or None
        return None


__all__ = ["MboxParser"]

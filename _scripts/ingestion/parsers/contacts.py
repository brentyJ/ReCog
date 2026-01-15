"""
VCF Contact parser.

Parses vCard (.vcf) files from phone contacts, email clients,
and CRM systems.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from collections import defaultdict

from .base import BaseParser
from ..types import ParsedContent


class VCFParser(BaseParser):
    """
    Parse vCard (.vcf) contact files.

    Extracts contact information, organizations, and relationship data.
    """

    PARSER_METADATA = {
        "file_type": "vCard (VCF)",
        "extensions": [".vcf"],
        "cypher_context": {
            "description": "Contact information from phone, email client, or CRM system",
            "requires_user_input": ["consider_anonymization"],
            "extractable": [
                "Professional and personal network mapping",
                "Organizational affiliations and clusters",
                "Communication channels per relationship",
                "Relationship context from notes",
                "Important dates (birthdays, anniversaries)",
                "Social profiles and online presence"
            ],
            "suggestions": [
                "I can map your network by organization and category",
                "Note fields often contain valuable relationship context",
                "Categories reveal how you organize your relationships",
                "Consider anonymizing names if sharing this analysis publicly"
            ],
            "privacy_warning": "Contact data is highly personal. Consider anonymization before external analysis."
        }
    }

    def get_extensions(self) -> List[str]:
        return [".vcf"]

    def can_parse(self, path: Path) -> bool:
        """Check if this is a VCF file."""
        if path.suffix.lower() != '.vcf':
            return False

        # Verify it looks like vCard
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = f.read(500)
                return 'BEGIN:VCARD' in first_lines
        except Exception:
            return path.suffix.lower() == '.vcf'

    def get_file_type(self) -> str:
        return "contacts"

    def parse(self, path: Path) -> ParsedContent:
        """Parse VCF contact file."""
        try:
            import vobject
        except ImportError:
            return ParsedContent(
                text="[VCF parsing requires vobject: pip install vobject]",
                title=path.stem,
                metadata={"error": "vobject_not_installed"}
            )

        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            contacts = []
            for vcard in vobject.readComponents(content):
                contact = self._extract_contact(vcard)
                if contact:
                    contacts.append(contact)

            # Sort alphabetically by name
            contacts.sort(key=lambda c: c.get('name', '').lower())

            # Format as text
            text = self._format_contacts(contacts)

            # Build metadata
            metadata = self._build_metadata(contacts, path)

            return ParsedContent(
                text=text,
                title=f"Contacts - {path.stem}",
                metadata=metadata
            )

        except Exception as e:
            return ParsedContent(
                text=f"[Contact parsing error: {e}]",
                title=path.stem,
                metadata={"error": "parse_failed", "details": str(e)}
            )

    def _extract_contact(self, vcard) -> Optional[Dict[str, Any]]:
        """Extract contact data from vCard object."""
        try:
            contact = {}

            # Full name (FN)
            if hasattr(vcard, 'fn'):
                contact['name'] = str(vcard.fn.value)
            elif hasattr(vcard, 'n'):
                # Build name from components
                n = vcard.n.value
                parts = []
                if n.prefix:
                    parts.append(n.prefix)
                if n.given:
                    parts.append(n.given)
                if n.additional:
                    parts.append(n.additional)
                if n.family:
                    parts.append(n.family)
                if n.suffix:
                    parts.append(n.suffix)
                contact['name'] = ' '.join(parts)

            if not contact.get('name'):
                return None  # Skip contacts without names

            # Organization
            if hasattr(vcard, 'org'):
                org_value = vcard.org.value
                if isinstance(org_value, list):
                    contact['organization'] = org_value[0] if org_value else None
                else:
                    contact['organization'] = str(org_value)

            # Title
            if hasattr(vcard, 'title'):
                contact['title'] = str(vcard.title.value)

            # Email addresses
            emails = []
            if hasattr(vcard, 'email_list'):
                for email in vcard.email_list:
                    emails.append(str(email.value))
            elif hasattr(vcard, 'email'):
                emails.append(str(vcard.email.value))
            if emails:
                contact['emails'] = emails

            # Phone numbers
            phones = []
            if hasattr(vcard, 'tel_list'):
                for tel in vcard.tel_list:
                    phone_type = ''
                    if hasattr(tel, 'type_param'):
                        phone_type = tel.type_param
                    phones.append({
                        'number': str(tel.value),
                        'type': phone_type
                    })
            elif hasattr(vcard, 'tel'):
                phones.append({
                    'number': str(vcard.tel.value),
                    'type': ''
                })
            if phones:
                contact['phones'] = phones

            # Categories
            if hasattr(vcard, 'categories'):
                cats = vcard.categories.value
                if isinstance(cats, list):
                    contact['categories'] = [str(c) for c in cats]
                else:
                    contact['categories'] = [str(cats)]

            # Note
            if hasattr(vcard, 'note'):
                contact['note'] = str(vcard.note.value)[:500]

            # Birthday
            if hasattr(vcard, 'bday'):
                contact['birthday'] = str(vcard.bday.value)

            # URL
            urls = []
            if hasattr(vcard, 'url_list'):
                for url in vcard.url_list:
                    urls.append(str(url.value))
            elif hasattr(vcard, 'url'):
                urls.append(str(vcard.url.value))
            if urls:
                contact['urls'] = urls

            # Address
            if hasattr(vcard, 'adr'):
                adr = vcard.adr.value
                addr_parts = []
                if adr.street:
                    addr_parts.append(adr.street)
                if adr.city:
                    addr_parts.append(adr.city)
                if adr.region:
                    addr_parts.append(adr.region)
                if adr.code:
                    addr_parts.append(adr.code)
                if adr.country:
                    addr_parts.append(adr.country)
                if addr_parts:
                    contact['address'] = ', '.join(addr_parts)

            return contact

        except Exception:
            return None

    def _format_contacts(self, contacts: List[Dict]) -> str:
        """Format contacts as readable text."""
        if not contacts:
            return "No contacts found in file."

        lines = [
            f"=== Contacts: {len(contacts)} Total ===",
            "",
        ]

        for contact in contacts:
            lines.append(f"--- Contact: {contact.get('name', 'Unknown')} ---")

            # Organization and title
            if contact.get('organization'):
                org_line = contact['organization']
                if contact.get('title'):
                    org_line += f" ({contact['title']})"
                lines.append(f"Organization: {org_line}")
            elif contact.get('title'):
                lines.append(f"Title: {contact['title']}")

            # Email
            if contact.get('emails'):
                lines.append(f"Email: {', '.join(contact['emails'])}")

            # Phone
            if contact.get('phones'):
                phone_strs = []
                for p in contact['phones']:
                    if p.get('type'):
                        phone_strs.append(f"{p['number']} ({p['type']})")
                    else:
                        phone_strs.append(p['number'])
                lines.append(f"Phone: {', '.join(phone_strs)}")

            # Address
            if contact.get('address'):
                lines.append(f"Address: {contact['address']}")

            # Categories
            if contact.get('categories'):
                lines.append(f"Categories: {', '.join(contact['categories'])}")

            # Birthday
            if contact.get('birthday'):
                lines.append(f"Birthday: {contact['birthday']}")

            # URLs
            if contact.get('urls'):
                lines.append(f"URLs: {', '.join(contact['urls'])}")

            # Note
            if contact.get('note'):
                note = contact['note'][:200]
                if len(contact['note']) > 200:
                    note += '...'
                lines.append(f"Note: {note}")

            lines.append("")

        return "\n".join(lines)

    def _build_metadata(self, contacts: List[Dict], path: Path) -> Dict[str, Any]:
        """Build contact list metadata."""
        metadata = {
            "format": "vcf",
            "parser": "VCFParser",
            "contact_count": len(contacts),
        }

        if not contacts:
            return metadata

        # Organizations
        orgs = set()
        for c in contacts:
            if c.get('organization'):
                orgs.add(c['organization'])
        metadata['unique_organizations'] = len(orgs)
        metadata['top_organizations'] = sorted(orgs)[:10]

        # Categories
        all_categories = []
        for c in contacts:
            if c.get('categories'):
                all_categories.extend(c['categories'])
        metadata['unique_categories'] = len(set(all_categories))

        # Email domains
        domains = defaultdict(int)
        for c in contacts:
            if c.get('emails'):
                for email in c['emails']:
                    if '@' in email:
                        domain = email.split('@')[-1].lower()
                        domains[domain] += 1
        metadata['top_domains'] = dict(sorted(domains.items(), key=lambda x: -x[1])[:10])

        # Contacts with notes
        with_notes = sum(1 for c in contacts if c.get('note'))
        metadata['contacts_with_notes'] = with_notes

        # Contacts with birthdays
        with_birthday = sum(1 for c in contacts if c.get('birthday'))
        metadata['contacts_with_birthday'] = with_birthday

        return metadata


__all__ = ["VCFParser"]

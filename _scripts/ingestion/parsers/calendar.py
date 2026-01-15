"""
ICS Calendar parser.

Parses iCalendar (.ics) files from Google Calendar, Apple Calendar,
Outlook, and other calendar apps.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from .base import BaseParser
from ..types import ParsedContent


class ICSParser(BaseParser):
    """
    Parse iCalendar (.ics) files.

    Extracts events, attendees, locations, and scheduling patterns.
    """

    PARSER_METADATA = {
        "file_type": "iCalendar (ICS)",
        "extensions": [".ics", ".ical"],
        "cypher_context": {
            "description": "Calendar events from Google Calendar, Apple Calendar, Outlook, or any calendar app",
            "requires_user_input": [],
            "extractable": [
                "Event timeline and scheduling patterns",
                "Meeting frequency with specific people",
                "Recurring commitments and routines",
                "Work/life balance from event types",
                "Location patterns (where time is spent)",
                "Collaboration networks from attendees"
            ],
            "suggestions": [
                "I can identify your busiest periods and free time patterns",
                "Meeting attendees reveal your professional network",
                "Recurring events show your routines and commitments",
                "Location data indicates where you spend your time",
                "Event titles and descriptions contain contextual insights"
            ]
        }
    }

    def get_extensions(self) -> List[str]:
        return [".ics", ".ical"]

    def can_parse(self, path: Path) -> bool:
        """Check if this is an ICS file."""
        if path.suffix.lower() not in self.get_extensions():
            return False

        # Optionally verify it looks like ICS
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = f.read(500)
                return 'BEGIN:VCALENDAR' in first_lines
        except Exception:
            return path.suffix.lower() in self.get_extensions()

    def get_file_type(self) -> str:
        return "calendar"

    def parse(self, path: Path) -> ParsedContent:
        """Parse ICS calendar file."""
        try:
            from icalendar import Calendar
        except ImportError:
            return ParsedContent(
                text="[ICS parsing requires icalendar: pip install icalendar]",
                title=path.stem,
                metadata={"error": "icalendar_not_installed"}
            )

        try:
            with open(path, 'rb') as f:
                cal = Calendar.from_ical(f.read())

            events = []
            for component in cal.walk():
                if component.name == 'VEVENT':
                    event = self._extract_event(component)
                    if event:
                        events.append(event)

            # Sort chronologically
            events.sort(key=lambda e: e.get('start') or datetime.min.replace(tzinfo=timezone.utc))

            # Format as text
            text = self._format_events(events)

            # Build metadata
            metadata = self._build_metadata(events, path)

            return ParsedContent(
                text=text,
                title=f"Calendar - {path.stem}",
                metadata=metadata
            )

        except Exception as e:
            return ParsedContent(
                text=f"[Calendar parsing error: {e}]",
                title=path.stem,
                metadata={"error": "parse_failed", "details": str(e)}
            )

    def _extract_event(self, component) -> Optional[Dict[str, Any]]:
        """Extract event data from VEVENT component."""
        try:
            event = {}

            # Summary (title)
            summary = component.get('SUMMARY')
            event['summary'] = str(summary) if summary else 'Untitled Event'

            # Start time
            dtstart = component.get('DTSTART')
            if dtstart:
                start = dtstart.dt
                if hasattr(start, 'tzinfo') and start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                elif not hasattr(start, 'hour'):  # Date only, all-day event
                    event['all_day'] = True
                event['start'] = start

            # End time
            dtend = component.get('DTEND')
            if dtend:
                end = dtend.dt
                if hasattr(end, 'tzinfo') and end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                event['end'] = end

            # Duration (fallback if no end time)
            duration = component.get('DURATION')
            if duration and 'end' not in event and 'start' in event:
                event['end'] = event['start'] + duration.dt

            # Location
            location = component.get('LOCATION')
            if location:
                event['location'] = str(location)

            # Description
            description = component.get('DESCRIPTION')
            if description:
                event['description'] = str(description)[:500]  # Limit length

            # Organizer
            organizer = component.get('ORGANIZER')
            if organizer:
                org_str = str(organizer)
                if 'mailto:' in org_str.lower():
                    event['organizer'] = org_str.split('mailto:')[-1].split(':')[0]
                else:
                    event['organizer'] = org_str

            # Attendees
            attendees = component.get('ATTENDEE')
            if attendees:
                if not isinstance(attendees, list):
                    attendees = [attendees]
                event['attendees'] = []
                for att in attendees:
                    att_str = str(att)
                    if 'mailto:' in att_str.lower():
                        event['attendees'].append(att_str.split('mailto:')[-1].split(':')[0])
                    else:
                        event['attendees'].append(att_str)

            # Recurring
            rrule = component.get('RRULE')
            if rrule:
                event['recurring'] = True
                event['rrule'] = str(rrule.to_ical().decode('utf-8'))

            # Status
            status = component.get('STATUS')
            if status:
                event['status'] = str(status)

            # Categories
            categories = component.get('CATEGORIES')
            if categories:
                if hasattr(categories, 'cats'):
                    event['categories'] = [str(c) for c in categories.cats]
                else:
                    event['categories'] = [str(categories)]

            return event

        except Exception:
            return None

    def _format_events(self, events: List[Dict]) -> str:
        """Format events as readable text."""
        if not events:
            return "No events found in calendar."

        lines = [
            f"=== Calendar: {len(events)} Events ===",
            "",
        ]

        for event in events:
            lines.append(f"--- Event: {event.get('summary', 'Untitled')} ---")

            # Date/time
            start = event.get('start')
            end = event.get('end')
            if start:
                if event.get('all_day'):
                    if hasattr(start, 'strftime'):
                        lines.append(f"Date: {start.strftime('%Y-%m-%d')} (All Day)")
                    else:
                        lines.append(f"Date: {start} (All Day)")
                else:
                    try:
                        start_str = start.strftime('%Y-%m-%d %H:%M')
                        if end:
                            end_str = end.strftime('%H:%M') if start.date() == end.date() else end.strftime('%Y-%m-%d %H:%M')
                            lines.append(f"Date: {start_str} - {end_str}")
                        else:
                            lines.append(f"Date: {start_str}")
                    except Exception:
                        lines.append(f"Date: {start}")

            # Location
            if event.get('location'):
                lines.append(f"Location: {event['location']}")

            # Recurring
            if event.get('recurring'):
                lines.append(f"Recurring: Yes")

            # Status
            if event.get('status') and event['status'] != 'CONFIRMED':
                lines.append(f"Status: {event['status']}")

            # Organizer
            if event.get('organizer'):
                lines.append(f"Organizer: {event['organizer']}")

            # Attendees
            if event.get('attendees'):
                attendees = event['attendees'][:10]  # Limit display
                lines.append(f"Attendees: {', '.join(attendees)}")
                if len(event['attendees']) > 10:
                    lines.append(f"  ... and {len(event['attendees']) - 10} more")

            # Categories
            if event.get('categories'):
                lines.append(f"Categories: {', '.join(event['categories'])}")

            # Description
            if event.get('description'):
                desc = event['description'][:200]
                if len(event['description']) > 200:
                    desc += '...'
                lines.append(f"Description: {desc}")

            lines.append("")

        return "\n".join(lines)

    def _build_metadata(self, events: List[Dict], path: Path) -> Dict[str, Any]:
        """Build calendar metadata."""
        metadata = {
            "format": "ics",
            "parser": "ICSParser",
            "event_count": len(events),
        }

        if not events:
            return metadata

        # Date range
        dates = [e['start'] for e in events if e.get('start')]
        if dates:
            try:
                date_objs = []
                for d in dates:
                    if hasattr(d, 'date'):
                        date_objs.append(d)
                    else:
                        date_objs.append(datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc))
                metadata['earliest_event'] = min(date_objs).isoformat()
                metadata['latest_event'] = max(date_objs).isoformat()
            except Exception:
                pass

        # Recurring count
        recurring = [e for e in events if e.get('recurring')]
        metadata['recurring_events'] = len(recurring)

        # Unique locations
        locations = set()
        for e in events:
            if e.get('location'):
                locations.add(e['location'])
        metadata['unique_locations'] = len(locations)

        # Unique attendees
        attendees = set()
        for e in events:
            if e.get('attendees'):
                attendees.update(e['attendees'])
        metadata['unique_attendees'] = len(attendees)

        # All-day events
        all_day = [e for e in events if e.get('all_day')]
        metadata['all_day_events'] = len(all_day)

        return metadata


__all__ = ["ICSParser"]

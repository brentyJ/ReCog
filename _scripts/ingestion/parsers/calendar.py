"""
ICS Calendar parser.

Parses iCalendar (.ics) files from Google Calendar, Apple Calendar,
Outlook, and other calendar apps.

Features:
- Timezone normalization (Windows TZID mapping, UTC conversion)
- Recurring event detection with RRULE parsing
- Multi-day and all-day event handling

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta, date
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

    # Windows timezone ID to IANA mapping
    # Outlook uses Windows timezone names instead of IANA
    WINDOWS_TZ_MAP = {
        "Pacific Standard Time": "America/Los_Angeles",
        "Mountain Standard Time": "America/Denver",
        "Central Standard Time": "America/Chicago",
        "Eastern Standard Time": "America/New_York",
        "GMT Standard Time": "Europe/London",
        "W. Europe Standard Time": "Europe/Berlin",
        "Central European Standard Time": "Europe/Warsaw",
        "AUS Eastern Standard Time": "Australia/Sydney",
        "E. Australia Standard Time": "Australia/Brisbane",
        "Tokyo Standard Time": "Asia/Tokyo",
        "China Standard Time": "Asia/Shanghai",
        "India Standard Time": "Asia/Kolkata",
        "UTC": "UTC",
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

    def _normalize_to_utc(self, dt_value) -> Optional[datetime]:
        """
        Normalize datetime to UTC.

        Handles:
        - Naive datetimes (assume UTC)
        - Timezone-aware datetimes (convert to UTC)
        - Date objects (convert to datetime at midnight UTC)
        """
        if dt_value is None:
            return None

        # Handle date objects (all-day events)
        if isinstance(dt_value, date) and not isinstance(dt_value, datetime):
            return datetime.combine(dt_value, datetime.min.time(), tzinfo=timezone.utc)

        # Handle datetime objects
        if isinstance(dt_value, datetime):
            if dt_value.tzinfo is None:
                # Naive datetime - assume UTC
                return dt_value.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC
                try:
                    return dt_value.astimezone(timezone.utc)
                except Exception:
                    return dt_value.replace(tzinfo=timezone.utc)

        return None

    def _get_calendar_timezone(self, cal) -> Optional[str]:
        """
        Extract default timezone from calendar.

        Google uses X-WR-TIMEZONE header.
        """
        # Check for X-WR-TIMEZONE (Google Calendar)
        x_wr_tz = cal.get('X-WR-TIMEZONE')
        if x_wr_tz:
            tz_str = str(x_wr_tz)
            # Check if it's a Windows timezone
            if tz_str in self.WINDOWS_TZ_MAP:
                return self.WINDOWS_TZ_MAP[tz_str]
            return tz_str

        return None

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

            # Get default timezone
            default_tz = self._get_calendar_timezone(cal)

            events = []
            for component in cal.walk():
                if component.name == 'VEVENT':
                    event = self._extract_event(component, default_tz)
                    if event:
                        events.append(event)

            # Sort chronologically by UTC time
            events.sort(key=lambda e: e.get('start_utc') or datetime.min.replace(tzinfo=timezone.utc))

            # Format as text
            text = self._format_events(events)

            # Build metadata
            metadata = self._build_metadata(events, path, default_tz)

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

    def _extract_event(self, component, default_tz: Optional[str] = None) -> Optional[Dict[str, Any]]:
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
                # Check if all-day event (date without time)
                if isinstance(start, date) and not isinstance(start, datetime):
                    event['all_day'] = True
                    event['start'] = start
                    event['start_utc'] = self._normalize_to_utc(start)
                else:
                    event['start'] = start
                    event['start_utc'] = self._normalize_to_utc(start)

            # End time
            dtend = component.get('DTEND')
            if dtend:
                end = dtend.dt
                event['end'] = end
                event['end_utc'] = self._normalize_to_utc(end)

            # Duration (fallback if no end time)
            duration = component.get('DURATION')
            if duration and 'end' not in event and 'start' in event:
                try:
                    if hasattr(duration, 'dt'):
                        dur = duration.dt
                        if event.get('start_utc'):
                            event['end_utc'] = event['start_utc'] + dur
                except Exception:
                    pass

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
                try:
                    event['rrule'] = str(rrule.to_ical().decode('utf-8'))
                    # Parse frequency for human-readable format
                    rrule_dict = dict(rrule)
                    freq = rrule_dict.get('FREQ', [None])[0]
                    if freq:
                        event['frequency'] = freq
                except Exception:
                    pass

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

            # UID for deduplication
            uid = component.get('UID')
            if uid:
                event['uid'] = str(uid)

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

            # Date/time (use UTC normalized time)
            start = event.get('start_utc') or event.get('start')
            end = event.get('end_utc') or event.get('end')

            if start:
                if event.get('all_day'):
                    if hasattr(start, 'strftime'):
                        lines.append(f"Date: {start.strftime('%Y-%m-%d')} (All Day)")
                    else:
                        lines.append(f"Date: {start} (All Day)")
                else:
                    try:
                        start_str = start.strftime('%Y-%m-%d %H:%M UTC')
                        if end:
                            if hasattr(start, 'date') and hasattr(end, 'date') and start.date() == end.date():
                                end_str = end.strftime('%H:%M')
                            else:
                                end_str = end.strftime('%Y-%m-%d %H:%M')
                            lines.append(f"Date: {start_str} - {end_str}")
                        else:
                            lines.append(f"Date: {start_str}")
                    except Exception:
                        lines.append(f"Date: {start}")

            # Location
            if event.get('location'):
                lines.append(f"Location: {event['location']}")

            # Recurring with frequency
            if event.get('recurring'):
                freq = event.get('frequency', 'Yes')
                lines.append(f"Recurring: {freq}")

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

    def _build_metadata(self, events: List[Dict], path: Path, default_tz: Optional[str]) -> Dict[str, Any]:
        """Build calendar metadata."""
        metadata = {
            "format": "ics",
            "parser": "ICSParser",
            "event_count": len(events),
        }

        if default_tz:
            metadata['calendar_timezone'] = default_tz

        if not events:
            return metadata

        # Date range (using UTC normalized times)
        dates = [e['start_utc'] for e in events if e.get('start_utc')]
        if dates:
            try:
                metadata['earliest_event'] = min(dates).isoformat()
                metadata['latest_event'] = max(dates).isoformat()
            except Exception:
                pass

        # Recurring count by frequency
        recurring = [e for e in events if e.get('recurring')]
        metadata['recurring_events'] = len(recurring)

        freq_counts = defaultdict(int)
        for e in recurring:
            freq = e.get('frequency', 'UNKNOWN')
            freq_counts[freq] += 1
        if freq_counts:
            metadata['recurring_by_frequency'] = dict(freq_counts)

        # Unique locations
        locations = set()
        for e in events:
            if e.get('location'):
                locations.add(e['location'])
        metadata['unique_locations'] = len(locations)
        metadata['top_locations'] = sorted(locations)[:10]

        # Unique attendees
        attendees = set()
        for e in events:
            if e.get('attendees'):
                attendees.update(e['attendees'])
        metadata['unique_attendees'] = len(attendees)

        # All-day events
        all_day = [e for e in events if e.get('all_day')]
        metadata['all_day_events'] = len(all_day)

        # Cancelled events
        cancelled = [e for e in events if e.get('status') == 'CANCELLED']
        metadata['cancelled_events'] = len(cancelled)

        # Events by status
        status_counts = defaultdict(int)
        for e in events:
            status = e.get('status', 'CONFIRMED')
            status_counts[status] += 1
        metadata['events_by_status'] = dict(status_counts)

        return metadata


__all__ = ["ICSParser"]

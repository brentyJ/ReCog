"""
Enhanced CSV parser with format detection.

Automatically detects and parses CSV exports from LinkedIn, Netflix,
Spotify, Amazon, bank statements, and more.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import csv
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
import re

from .base import BaseParser
from ..types import ParsedContent


class EnhancedCSVParser(BaseParser):
    """
    Enhanced CSV parser with automatic format detection.

    Detects known formats (LinkedIn, Netflix, Spotify, etc.) and
    applies specialized parsing for each.
    """

    PARSER_METADATA = {
        "file_type": "CSV (Comma-Separated Values)",
        "extensions": [".csv"],
        "cypher_context": {
            "description": "Structured data from spreadsheet, database, or platform export",
            "requires_user_input": [],
            "extractable": [
                "LinkedIn: Professional network and connections",
                "Netflix: Viewing history and preferences",
                "Spotify: Music listening patterns",
                "Bank/PayPal: Financial transaction history",
                "Fitness: Health and activity tracking",
                "Amazon: Purchase history and spending",
                "Generic: Patterns in any tabular data"
            ],
            "suggestions": [
                "I'll automatically detect if this is from LinkedIn, Netflix, Spotify, etc.",
                "Date columns help me identify patterns over time",
                "I can summarize categories, trends, and anomalies",
                "Financial data can reveal spending patterns"
            ],
            "privacy_warning": "CSV files may contain financial or personal data. Review before sharing analysis."
        }
    }

    # Known CSV formats with their detection signatures
    KNOWN_FORMATS = {
        'linkedin_connections': {
            'required_columns': ['first name', 'last name', 'company', 'position'],
            'optional_columns': ['email address', 'connected on'],
            'description': 'LinkedIn professional network export',
            'date_column': 'connected on'
        },
        'linkedin_messages': {
            'required_columns': ['from', 'to', 'date', 'subject'],
            'description': 'LinkedIn messages export',
            'date_column': 'date'
        },
        'netflix_history': {
            'required_columns': ['title', 'date'],
            'optional_columns': ['duration', 'device type'],
            'description': 'Netflix viewing history',
            'date_column': 'date'
        },
        'spotify_streaming': {
            'required_columns': ['ts', 'master_metadata_track_name', 'master_metadata_album_artist_name'],
            'optional_columns': ['ms_played', 'spotify_track_uri'],
            'description': 'Spotify streaming history',
            'date_column': 'ts'
        },
        'spotify_simple': {
            'required_columns': ['endtime', 'artistname', 'trackname'],
            'optional_columns': ['msplayed'],
            'description': 'Spotify simple streaming history',
            'date_column': 'endtime'
        },
        'amazon_orders': {
            'required_columns': ['order date', 'order id', 'title'],
            'optional_columns': ['purchase price per unit', 'quantity'],
            'description': 'Amazon order history',
            'date_column': 'order date'
        },
        'bank_statement': {
            'required_columns': ['date', 'description', 'amount'],
            'optional_columns': ['balance', 'category'],
            'description': 'Bank transaction history',
            'date_column': 'date'
        },
        'paypal_history': {
            'required_columns': ['date', 'name', 'type', 'status', 'gross'],
            'description': 'PayPal transaction history',
            'date_column': 'date'
        },
        'fitbit_sleep': {
            'required_columns': ['start time', 'end time', 'minutes asleep'],
            'description': 'Fitbit sleep tracking data',
            'date_column': 'start time'
        },
        'myfitnesspal': {
            'required_columns': ['date', 'calories'],
            'optional_columns': ['carbohydrates (g)', 'fat (g)', 'protein (g)'],
            'description': 'MyFitnessPal nutrition tracking',
            'date_column': 'date'
        },
        'uber_trips': {
            'required_columns': ['city', 'request time', 'dropoff time', 'fare amount'],
            'description': 'Uber ride history',
            'date_column': 'request time'
        },
        'apple_health': {
            'required_columns': ['type', 'sourcename', 'value', 'startdate'],
            'description': 'Apple Health export',
            'date_column': 'startdate'
        },
    }

    def get_extensions(self) -> List[str]:
        return [".csv"]

    def can_parse(self, path: Path) -> bool:
        """Check if this is a CSV file."""
        return path.suffix.lower() == '.csv'

    def get_file_type(self) -> str:
        return "csv_enhanced"

    def parse(self, path: Path) -> ParsedContent:
        """Parse CSV with automatic format detection."""
        try:
            # Try to detect encoding
            encoding = self._detect_encoding(path)

            # Read and detect format
            with open(path, 'r', encoding=encoding, errors='replace', newline='') as f:
                # Detect delimiter
                sample = f.read(8192)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')

                reader = csv.DictReader(f, dialect=dialect)
                columns = reader.fieldnames or []

                # Read all rows
                rows = list(reader)

            if not rows:
                return ParsedContent(
                    text="[Empty CSV file]",
                    title=path.stem,
                    metadata={"error": "empty_file", "format": "csv"}
                )

            # Detect format
            format_name, format_spec = self._detect_format(columns)

            # Parse based on format
            if format_name != 'generic':
                return self._parse_known_format(format_name, format_spec, rows, columns, path)
            else:
                return self._parse_generic(rows, columns, path)

        except Exception as e:
            return ParsedContent(
                text=f"[CSV parsing error: {e}]",
                title=path.stem,
                metadata={"error": "parse_failed", "details": str(e)}
            )

    def _detect_encoding(self, path: Path) -> str:
        """Try to detect file encoding."""
        # Try UTF-8 first
        try:
            with open(path, 'r', encoding='utf-8') as f:
                f.read(1024)
            return 'utf-8'
        except UnicodeDecodeError:
            pass

        # Try UTF-16
        try:
            with open(path, 'r', encoding='utf-16') as f:
                f.read(1024)
            return 'utf-16'
        except Exception:
            pass

        # Fallback to latin-1 (accepts anything)
        return 'latin-1'

    def _detect_format(self, columns: List[str]) -> Tuple[str, Dict]:
        """Detect CSV format from column names."""
        normalized_cols = [col.strip().lower() for col in columns]

        for format_name, spec in self.KNOWN_FORMATS.items():
            required = [r.lower() for r in spec['required_columns']]
            if all(req in normalized_cols for req in required):
                return format_name, spec

        return 'generic', {}

    def _parse_known_format(self, format_name: str, spec: Dict, rows: List[Dict],
                            columns: List[str], path: Path) -> ParsedContent:
        """Parse a known CSV format with specialized handling."""
        handlers = {
            'linkedin_connections': self._parse_linkedin,
            'linkedin_messages': self._parse_linkedin_messages,
            'netflix_history': self._parse_netflix,
            'spotify_streaming': self._parse_spotify,
            'spotify_simple': self._parse_spotify_simple,
            'amazon_orders': self._parse_amazon,
            'bank_statement': self._parse_bank,
            'paypal_history': self._parse_paypal,
            'fitbit_sleep': self._parse_fitbit,
            'uber_trips': self._parse_uber,
        }

        handler = handlers.get(format_name)
        if handler:
            return handler(rows, columns, path, spec)
        else:
            # Fallback to generic with format tag
            result = self._parse_generic(rows, columns, path)
            result.metadata['detected_format'] = format_name
            result.metadata['format_description'] = spec.get('description', '')
            return result

    def _parse_linkedin(self, rows: List[Dict], columns: List[str],
                        path: Path, spec: Dict) -> ParsedContent:
        """Parse LinkedIn connections export."""
        companies = defaultdict(int)
        positions = defaultdict(int)

        for row in rows:
            company = self._get_col(row, 'company')
            position = self._get_col(row, 'position')
            if company:
                companies[company] += 1
            if position:
                positions[position] += 1

        lines = [
            "=== LinkedIn Professional Network ===",
            "",
            f"Total Connections: {len(rows)}",
            "",
            "Top Companies:",
        ]

        for company, count in sorted(companies.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  {company}: {count}")

        lines.extend(["", "Top Positions:"])
        for position, count in sorted(positions.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  {position}: {count}")

        # Sample connections
        lines.extend(["", "Sample Connections:"])
        for row in rows[:20]:
            name = f"{self._get_col(row, 'first name')} {self._get_col(row, 'last name')}"
            company = self._get_col(row, 'company') or 'Unknown'
            position = self._get_col(row, 'position') or 'Unknown'
            lines.append(f"  - {name} | {position} at {company}")

        if len(rows) > 20:
            lines.append(f"  ... and {len(rows) - 20} more")

        return ParsedContent(
            text="\n".join(lines),
            title=f"LinkedIn Connections - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "linkedin_connections",
                "connection_count": len(rows),
                "unique_companies": len(companies),
                "unique_positions": len(positions),
                "top_companies": dict(sorted(companies.items(), key=lambda x: -x[1])[:10]),
            }
        )

    def _parse_linkedin_messages(self, rows: List[Dict], columns: List[str],
                                  path: Path, spec: Dict) -> ParsedContent:
        """Parse LinkedIn messages export."""
        conversations = defaultdict(list)

        for row in rows:
            from_name = self._get_col(row, 'from')
            to_name = self._get_col(row, 'to')
            key = tuple(sorted([from_name, to_name]))
            conversations[key].append(row)

        lines = [
            "=== LinkedIn Messages ===",
            "",
            f"Total Messages: {len(rows)}",
            f"Conversations: {len(conversations)}",
            "",
        ]

        # Top conversations
        lines.append("Top Conversations:")
        sorted_convos = sorted(conversations.items(), key=lambda x: -len(x[1]))[:10]
        for (p1, p2), msgs in sorted_convos:
            lines.append(f"  {p1} <-> {p2}: {len(msgs)} messages")

        return ParsedContent(
            text="\n".join(lines),
            title=f"LinkedIn Messages - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "linkedin_messages",
                "message_count": len(rows),
                "conversation_count": len(conversations),
            }
        )

    def _parse_netflix(self, rows: List[Dict], columns: List[str],
                       path: Path, spec: Dict) -> ParsedContent:
        """Parse Netflix viewing history."""
        titles = defaultdict(int)

        for row in rows:
            title = self._get_col(row, 'title')
            if title:
                # Extract show name (before episode info)
                show = title.split(':')[0].strip()
                titles[show] += 1

        lines = [
            "=== Netflix Viewing History ===",
            "",
            f"Total Views: {len(rows)}",
            f"Unique Titles: {len(titles)}",
            "",
            "Most Watched:",
        ]

        for title, count in sorted(titles.items(), key=lambda x: -x[1])[:20]:
            lines.append(f"  {title}: {count} views")

        return ParsedContent(
            text="\n".join(lines),
            title=f"Netflix History - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "netflix_history",
                "view_count": len(rows),
                "unique_titles": len(titles),
                "top_titles": dict(sorted(titles.items(), key=lambda x: -x[1])[:10]),
            }
        )

    def _parse_spotify(self, rows: List[Dict], columns: List[str],
                       path: Path, spec: Dict) -> ParsedContent:
        """Parse Spotify streaming history."""
        artists = defaultdict(int)
        tracks = defaultdict(int)
        total_ms = 0

        for row in rows:
            artist = self._get_col(row, 'master_metadata_album_artist_name')
            track = self._get_col(row, 'master_metadata_track_name')
            ms = self._get_col(row, 'ms_played')

            if artist:
                artists[artist] += 1
            if track:
                tracks[f"{track} - {artist}"] += 1
            if ms:
                try:
                    total_ms += int(ms)
                except ValueError:
                    pass

        hours = total_ms / (1000 * 60 * 60)

        lines = [
            "=== Spotify Streaming History ===",
            "",
            f"Total Streams: {len(rows)}",
            f"Total Listening Time: {hours:.1f} hours",
            f"Unique Artists: {len(artists)}",
            "",
            "Top Artists:",
        ]

        for artist, count in sorted(artists.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  {artist}: {count} plays")

        lines.extend(["", "Top Tracks:"])
        for track, count in sorted(tracks.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  {track}: {count} plays")

        return ParsedContent(
            text="\n".join(lines),
            title=f"Spotify History - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "spotify_streaming",
                "stream_count": len(rows),
                "total_hours": round(hours, 1),
                "unique_artists": len(artists),
                "unique_tracks": len(tracks),
                "top_artists": dict(sorted(artists.items(), key=lambda x: -x[1])[:10]),
            }
        )

    def _parse_spotify_simple(self, rows: List[Dict], columns: List[str],
                               path: Path, spec: Dict) -> ParsedContent:
        """Parse Spotify simple streaming history format."""
        artists = defaultdict(int)
        tracks = defaultdict(int)
        total_ms = 0

        for row in rows:
            artist = self._get_col(row, 'artistname')
            track = self._get_col(row, 'trackname')
            ms = self._get_col(row, 'msplayed')

            if artist:
                artists[artist] += 1
            if track:
                tracks[f"{track} - {artist}"] += 1
            if ms:
                try:
                    total_ms += int(ms)
                except ValueError:
                    pass

        hours = total_ms / (1000 * 60 * 60)

        lines = [
            "=== Spotify Streaming History ===",
            "",
            f"Total Streams: {len(rows)}",
            f"Total Listening Time: {hours:.1f} hours",
            "",
            "Top Artists:",
        ]

        for artist, count in sorted(artists.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  {artist}: {count} plays")

        return ParsedContent(
            text="\n".join(lines),
            title=f"Spotify History - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "spotify_simple",
                "stream_count": len(rows),
                "total_hours": round(hours, 1),
                "top_artists": dict(sorted(artists.items(), key=lambda x: -x[1])[:10]),
            }
        )

    def _parse_amazon(self, rows: List[Dict], columns: List[str],
                      path: Path, spec: Dict) -> ParsedContent:
        """Parse Amazon order history."""
        categories = defaultdict(int)
        total_orders = len(rows)

        lines = [
            "=== Amazon Order History ===",
            "",
            f"Total Orders: {total_orders}",
            "",
            "Sample Orders:",
        ]

        for row in rows[:30]:
            date = self._get_col(row, 'order date')
            title = self._get_col(row, 'title')
            price = self._get_col(row, 'purchase price per unit')

            if title:
                title_short = title[:60] + '...' if len(title) > 60 else title
                lines.append(f"  [{date}] {title_short}")

        if len(rows) > 30:
            lines.append(f"  ... and {len(rows) - 30} more orders")

        return ParsedContent(
            text="\n".join(lines),
            title=f"Amazon Orders - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "amazon_orders",
                "order_count": total_orders,
            }
        )

    def _parse_bank(self, rows: List[Dict], columns: List[str],
                    path: Path, spec: Dict) -> ParsedContent:
        """Parse bank statement."""
        total_income = 0
        total_expense = 0
        merchants = defaultdict(float)

        for row in rows:
            desc = self._get_col(row, 'description')
            amount_str = self._get_col(row, 'amount')

            if amount_str:
                try:
                    # Handle various number formats
                    amount_str = amount_str.replace('$', '').replace(',', '').replace(' ', '')
                    amount = float(amount_str)
                    if amount > 0:
                        total_income += amount
                    else:
                        total_expense += abs(amount)
                        if desc:
                            merchants[desc[:30]] += abs(amount)
                except ValueError:
                    pass

        lines = [
            "=== Bank Statement Analysis ===",
            "",
            f"Total Transactions: {len(rows)}",
            f"Total Income: ${total_income:,.2f}",
            f"Total Expenses: ${total_expense:,.2f}",
            f"Net: ${total_income - total_expense:,.2f}",
            "",
            "Top Expense Categories:",
        ]

        for merchant, amount in sorted(merchants.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  {merchant}: ${amount:,.2f}")

        return ParsedContent(
            text="\n".join(lines),
            title=f"Bank Statement - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "bank_statement",
                "transaction_count": len(rows),
                "total_income": round(total_income, 2),
                "total_expense": round(total_expense, 2),
                "privacy_warning": "Contains financial data",
            }
        )

    def _parse_paypal(self, rows: List[Dict], columns: List[str],
                      path: Path, spec: Dict) -> ParsedContent:
        """Parse PayPal history."""
        return self._parse_bank(rows, columns, path, spec)

    def _parse_fitbit(self, rows: List[Dict], columns: List[str],
                      path: Path, spec: Dict) -> ParsedContent:
        """Parse Fitbit sleep data."""
        total_sleep = 0

        for row in rows:
            minutes = self._get_col(row, 'minutes asleep')
            if minutes:
                try:
                    total_sleep += int(minutes)
                except ValueError:
                    pass

        avg_sleep = total_sleep / len(rows) if rows else 0

        lines = [
            "=== Fitbit Sleep Data ===",
            "",
            f"Total Records: {len(rows)}",
            f"Total Sleep: {total_sleep / 60:.1f} hours",
            f"Average Sleep: {avg_sleep / 60:.1f} hours/night",
        ]

        return ParsedContent(
            text="\n".join(lines),
            title=f"Fitbit Sleep - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "fitbit_sleep",
                "record_count": len(rows),
                "avg_sleep_hours": round(avg_sleep / 60, 1),
            }
        )

    def _parse_uber(self, rows: List[Dict], columns: List[str],
                    path: Path, spec: Dict) -> ParsedContent:
        """Parse Uber trip history."""
        cities = defaultdict(int)
        total_fare = 0

        for row in rows:
            city = self._get_col(row, 'city')
            fare = self._get_col(row, 'fare amount')

            if city:
                cities[city] += 1
            if fare:
                try:
                    total_fare += float(fare.replace('$', '').replace(',', ''))
                except ValueError:
                    pass

        lines = [
            "=== Uber Trip History ===",
            "",
            f"Total Trips: {len(rows)}",
            f"Total Spent: ${total_fare:,.2f}",
            "",
            "Trips by City:",
        ]

        for city, count in sorted(cities.items(), key=lambda x: -x[1]):
            lines.append(f"  {city}: {count} trips")

        return ParsedContent(
            text="\n".join(lines),
            title=f"Uber Trips - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "uber_trips",
                "trip_count": len(rows),
                "total_fare": round(total_fare, 2),
            }
        )

    def _parse_generic(self, rows: List[Dict], columns: List[str],
                       path: Path) -> ParsedContent:
        """Parse generic CSV with auto-detection of column types."""
        lines = [
            f"=== CSV Data: {path.name} ===",
            "",
            f"Rows: {len(rows)}",
            f"Columns: {len(columns)}",
            "",
            "Column Names:",
        ]

        for col in columns:
            lines.append(f"  - {col}")

        # Sample data
        lines.extend(["", "Sample Data:"])
        for i, row in enumerate(rows[:10]):
            lines.append(f"  Row {i+1}:")
            for col in columns[:8]:  # Limit columns shown
                val = row.get(col, '')
                if len(str(val)) > 50:
                    val = str(val)[:50] + '...'
                lines.append(f"    {col}: {val}")

        if len(rows) > 10:
            lines.append(f"  ... and {len(rows) - 10} more rows")

        # Column statistics
        col_stats = self._analyze_columns(rows, columns)

        return ParsedContent(
            text="\n".join(lines),
            title=f"CSV - {path.stem}",
            metadata={
                "format": "csv",
                "detected_format": "generic",
                "row_count": len(rows),
                "column_count": len(columns),
                "columns": columns,
                "column_stats": col_stats,
            }
        )

    def _analyze_columns(self, rows: List[Dict], columns: List[str]) -> Dict[str, Any]:
        """Analyze column types and statistics."""
        stats = {}

        for col in columns[:20]:  # Limit analysis
            values = [row.get(col, '') for row in rows[:100]]
            non_empty = [v for v in values if v]

            col_info = {
                "non_empty": len(non_empty),
                "unique": len(set(non_empty)),
            }

            # Detect if numeric
            numeric_count = sum(1 for v in non_empty if self._is_numeric(str(v)))
            if numeric_count > len(non_empty) * 0.8:
                col_info["type"] = "numeric"

            # Detect if date
            date_count = sum(1 for v in non_empty if self._looks_like_date(str(v)))
            if date_count > len(non_empty) * 0.8:
                col_info["type"] = "date"

            stats[col] = col_info

        return stats

    def _is_numeric(self, value: str) -> bool:
        """Check if value looks numeric."""
        try:
            float(value.replace(',', '').replace('$', '').replace('%', ''))
            return True
        except ValueError:
            return False

    def _looks_like_date(self, value: str) -> bool:
        """Check if value looks like a date."""
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2024-01-15
            r'\d{2}/\d{2}/\d{4}',  # 01/15/2024
            r'\d{2}-\d{2}-\d{4}',  # 15-01-2024
        ]
        return any(re.search(p, value) for p in date_patterns)

    def _get_col(self, row: Dict, col_name: str) -> Optional[str]:
        """Get column value case-insensitively."""
        # Try exact match first
        if col_name in row:
            return str(row[col_name]).strip()

        # Try case-insensitive
        col_lower = col_name.lower()
        for key in row:
            if key.lower() == col_lower:
                return str(row[key]).strip()

        return None


__all__ = ["EnhancedCSVParser"]

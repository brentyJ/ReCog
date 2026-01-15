# ReCog Parser Implementation - Phase 1: Quick Wins
**Status:** Ready for Implementation  
**Estimated Time:** 1-2 sessions  
**Priority:** CRITICAL - Unlocks platform export analysis

---

## Overview

Implement 5 high-value, low-complexity parsers that enable analysis of the most common file types and unlock all major platform exports.

**Goal:** Enable ReCog to handle archives, calendars, contacts, CSV exports, and Notion notes.

---

## Architecture Philosophy

**Parser Pattern:**
```python
class SomeParser(BaseParser):
    PARSER_METADATA = {
        "file_type": "Human-readable name",
        "extensions": [".ext"],
        "cypher_context": {
            "description": "What this file contains",
            "extractable": ["What insights can be found"],
            "suggestions": ["How Cypher should guide users"]
        }
    }
    
    def can_parse(self, file_path: str) -> bool:
        # Quick check if this parser handles this file
        
    def parse(self, file_path: str) -> ParsedDocument:
        # Extract content, return structured document
```

**Key Principles:**
1. **Fail gracefully** - bad data shouldn't crash the parser
2. **Preserve structure** - maintain hierarchy/relationships
3. **Extract metadata** - dates, authors, locations, etc.
4. **Format as text** - LLMs need readable text for extraction
5. **Register metadata** - Cypher needs to know what each format offers

---

## Task 1: ZIP/Archive Parser (FOUNDATION)

**Priority:** ⭐⭐⭐⭐⭐ CRITICAL - Enables ALL platform exports

**Why First:** Facebook, Twitter, Google Takeout, etc. all come as ZIP files. Without this, users can't upload them.

### Requirements

**Create:** `_scripts/recog_engine/ingestion/parsers/archive.py`

**Must Handle:**
- ZIP files (`zipfile` stdlib)
- TAR.GZ files (`tarfile` stdlib)
- Extract to temporary directory
- Detect known formats (Facebook, Google Takeout, Twitter)
- Route to specialized parser OR process generically
- Clean up temporary files

**Format Detection Logic:**

```python
def _detect_export_format(self, directory: str) -> Optional[str]:
    """
    Detect platform export by signature files/structure.
    
    Returns:
    - 'facebook' if Facebook export detected
    - 'google_takeout' if Google Takeout detected
    - 'twitter' if Twitter archive detected
    - None for generic archive
    """
    
    path = Path(directory)
    
    # Facebook: has posts/your_posts_1.json
    if (path / 'posts' / 'your_posts_1.json').exists():
        return 'facebook'
    
    # Facebook alt: has messages/inbox/
    if (path / 'messages' / 'inbox').exists():
        return 'facebook'
    
    # Google Takeout: has Takeout/ root folder
    if (path / 'Takeout').exists():
        return 'google_takeout'
    
    # Twitter: has data/tweets.js or data/tweet.js
    if (path / 'data' / 'tweets.js').exists():
        return 'twitter'
    if (path / 'data' / 'tweet.js').exists():
        return 'twitter'
    
    # Instagram: has media.json
    if (path / 'media.json').exists():
        return 'instagram'
    
    return None
```

**Generic Archive Handling:**

When format is unknown:
1. Recursively scan for all supported files
2. Skip binary/media files (images, videos)
3. Parse each supported file with appropriate parser
4. Combine into sections: "File 1", "File 2", etc.
5. Return single ParsedDocument with all content

**Temporary File Management:**

```python
import tempfile
from pathlib import Path

def parse(self, file_path: str) -> ParsedDocument:
    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract
        self._extract_archive(file_path, temp_dir)
        
        # Process
        result = self._process_contents(temp_dir)
        
        # Temp dir auto-deleted when with block exits
        return result
```

**Error Handling:**
- Corrupted archives: return error in ParsedDocument
- Encrypted archives: detect and inform user (can't extract)
- Nested archives: extract first level only (don't recurse infinitely)
- Size limits: warn if extracted size > 500MB

**PARSER_METADATA:**

```python
PARSER_METADATA = {
    "file_type": "Archive (ZIP/TAR)",
    "extensions": [".zip", ".tar", ".tar.gz", ".tgz"],
    "cypher_context": {
        "description": "Compressed archive that may contain platform exports or document collections",
        "requires_user_input": [],
        "extractable": [
            "Facebook/Instagram export analysis",
            "Google Takeout data extraction",
            "Twitter archive insights",
            "Multiple document analysis"
        ],
        "suggestions": [
            "I'll extract and identify the contents automatically",
            "Large archives (>100MB) may take 2-5 minutes to process",
            "If this is a known export (Facebook, Google, Twitter), I'll use specialized parsing"
        ],
        "privacy_warning": "Archives may contain years of personal data across multiple file types"
    }
}
```

**Stub Methods for Future:**

```python
def _parse_facebook_export(self, directory: str) -> ParsedDocument:
    """
    Route to FacebookParser when implemented.
    For now: return basic info about what was found.
    """
    return ParsedDocument(
        content="Facebook export detected. Parser not yet implemented.",
        metadata={'detected_format': 'facebook', 'parser': 'ArchiveParser'}
    )

def _parse_google_takeout(self, directory: str) -> ParsedDocument:
    """Future: Google Takeout parser"""
    return ParsedDocument(
        content="Google Takeout detected. Parser not yet implemented.",
        metadata={'detected_format': 'google_takeout', 'parser': 'ArchiveParser'}
    )

def _parse_twitter_export(self, directory: str) -> ParsedDocument:
    """Future: Twitter parser"""
    return ParsedDocument(
        content="Twitter archive detected. Parser not yet implemented.",
        metadata={'detected_format': 'twitter', 'parser': 'ArchiveParser'}
    )
```

---

## Task 2: ICS Calendar Parser

**Priority:** ⭐⭐⭐⭐ HIGH - Universal format, huge use case

**Why Important:** Every calendar app (Google, Apple, Outlook) exports to ICS. Scheduling patterns reveal routines, relationships, work/life balance.

### Requirements

**Create:** `_scripts/recog_engine/ingestion/parsers/calendar.py`

**Dependencies:** Add to requirements.txt:
```
icalendar>=5.0.0
```

**Must Extract:**

From each VEVENT:
- **SUMMARY** - Event title/description
- **DTSTART** - Start date/time
- **DTEND** - End date/time (if present)
- **DURATION** - Duration (if DTEND not present)
- **LOCATION** - Where event takes place
- **DESCRIPTION** - Additional notes
- **ATTENDEE** - List of attendees (emails)
- **ORGANIZER** - Who created the event
- **RRULE** - Recurrence rule (is it recurring?)
- **STATUS** - CONFIRMED, TENTATIVE, CANCELLED
- **CATEGORIES** - Event tags

**Text Formatting:**

Convert events to readable text for LLM extraction:

```
=== Event: Team Standup ===
Date: 2024-01-15 09:00-09:30
Location: Zoom
Recurring: Daily (weekdays)
Attendees: john@company.com, sarah@company.com, mike@company.com
Description: Daily team sync

=== Event: Client Meeting - Acme Corp ===
Date: 2024-01-16 14:00-15:00
Location: Office, Conference Room A
Organizer: sarah@company.com
Attendees: client@acme.com, boss@company.com
Description: Q1 roadmap discussion
```

**Metadata to Track:**
- Total events
- Date range (earliest to latest)
- Recurring event count
- Unique locations
- Unique attendees
- Event density (events per week/month)

**Sorting:**
- Chronological order (oldest to newest)
- Group recurring events together

**Edge Cases:**
- All-day events (DTSTART has no time)
- Multi-day events (conference, vacation)
- Cancelled events (STATUS:CANCELLED) - include but note
- Timezone handling (convert to UTC or preserve original)

**PARSER_METADATA:**

```python
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
```

**Implementation Notes:**

```python
from icalendar import Calendar
from datetime import datetime, timezone

def parse(self, file_path: str) -> ParsedDocument:
    with open(file_path, 'rb') as f:
        cal = Calendar.from_ical(f.read())
    
    events = []
    for component in cal.walk('VEVENT'):
        # Extract event data
        event = self._extract_event_data(component)
        events.append(event)
    
    # Sort chronologically
    events.sort(key=lambda e: e.get('start', datetime.min))
    
    # Format as text
    text = self._format_events_as_text(events)
    
    # Build metadata
    metadata = self._build_event_metadata(events)
    
    return ParsedDocument(content=text, metadata=metadata)
```

---

## Task 3: VCF Contact Parser

**Priority:** ⭐⭐⭐⭐ HIGH - Pairs perfectly with calendar

**Why Important:** Contacts + Calendar = complete relationship map. Who you meet with, who you communicate with, organizational affiliations.

### Requirements

**Create:** `_scripts/recog_engine/ingestion/parsers/contacts.py`

**Dependencies:** Add to requirements.txt:
```
vobject>=0.9.6
```

**Must Extract:**

From each vCard:
- **FN** (Formatted Name) - Full name
- **N** (Name components) - Family, Given, Middle, Prefix, Suffix
- **ORG** - Organization/company
- **TITLE** - Job title
- **EMAIL** - Email addresses (can be multiple)
- **TEL** - Phone numbers (can be multiple)
- **ADR** - Physical addresses
- **URL** - Websites, social profiles
- **NOTE** - Free-form notes about contact
- **CATEGORIES** - Tags/groups (Family, Work, etc.)
- **BDAY** - Birthday
- **ANNIVERSARY** - Anniversary date
- **REV** - Last modified date

**Text Formatting:**

```
=== Contact: John Smith ===
Organization: Acme Corporation
Title: Senior Engineer
Email: john.smith@acme.com, jsmith@personal.com
Phone: +1-555-123-4567 (work), +1-555-987-6543 (mobile)
Categories: Work, Engineering Team
Note: Met at conference 2023. Interested in collaboration on Project X.

=== Contact: Sarah Johnson ===
Organization: University of Melbourne
Title: Professor of Computer Science
Email: s.johnson@unimelb.edu.au
Categories: Academic, Collaborators
```

**Metadata to Track:**
- Total contacts
- Organizations (unique list)
- Categories/groups
- Contacts with notes (indicates closer relationships)
- Contacts with birthdays/anniversaries
- Most common domains (@company.com, @gmail.com)

**Privacy Considerations:**
- Suggest anonymization before sharing analysis
- Flag if exporting to external services
- Note field often contains sensitive relationship context

**Edge Cases:**
- Multiple vCards in one file (common) - parse all
- Encoding issues (vCard uses quoted-printable) - handle gracefully
- Missing required fields (some cards have only name/phone)
- Organization without person (company contacts)

**PARSER_METADATA:**

```python
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
```

**Implementation Notes:**

```python
import vobject

def parse(self, file_path: str) -> ParsedDocument:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    contacts = []
    for vcard in vobject.readComponents(content):
        contact = self._extract_contact_data(vcard)
        contacts.append(contact)
    
    # Sort alphabetically by name
    contacts.sort(key=lambda c: c.get('name', ''))
    
    # Format as text
    text = self._format_contacts_as_text(contacts)
    
    # Build metadata
    metadata = self._build_contact_metadata(contacts)
    
    return ParsedDocument(content=text, metadata=metadata)
```

---

## Task 4: Enhanced CSV Parser

**Priority:** ⭐⭐⭐⭐ HIGH - Powers 20+ export types

**Why Important:** LinkedIn, Netflix, Spotify, bank statements, Amazon orders, etc. all export as CSV. Smart detection makes ReCog feel magical.

### Requirements

**Create:** `_scripts/recog_engine/ingestion/parsers/csv_enhanced.py`

**No New Dependencies** (uses stdlib `csv`)

**Format Detection Dictionary:**

```python
KNOWN_FORMATS = {
    'linkedin_connections': {
        'required_columns': ['First Name', 'Last Name', 'Company', 'Position'],
        'optional_columns': ['Email Address', 'Connected On'],
        'description': 'LinkedIn professional network export',
        'date_column': 'Connected On'
    },
    'netflix_history': {
        'required_columns': ['Title', 'Date'],
        'optional_columns': ['Duration', 'Device Type'],
        'description': 'Netflix viewing history',
        'date_column': 'Date'
    },
    'spotify_streaming': {
        'required_columns': ['ts', 'master_metadata_track_name', 'master_metadata_album_artist_name'],
        'optional_columns': ['ms_played', 'spotify_track_uri'],
        'description': 'Spotify streaming history',
        'date_column': 'ts'
    },
    'amazon_orders': {
        'required_columns': ['Order Date', 'Order ID', 'Title', 'Purchase Price Per Unit'],
        'description': 'Amazon order history',
        'date_column': 'Order Date'
    },
    'bank_statement': {
        'required_columns': ['Date', 'Description', 'Amount'],
        'optional_columns': ['Balance', 'Category'],
        'description': 'Bank transaction history',
        'date_column': 'Date'
    },
    'paypal_history': {
        'required_columns': ['Date', 'Name', 'Type', 'Status', 'Gross'],
        'description': 'PayPal transaction history',
        'date_column': 'Date'
    },
    'fitbit_sleep': {
        'required_columns': ['Start Time', 'End Time', 'Minutes Asleep'],
        'description': 'Fitbit sleep tracking data',
        'date_column': 'Start Time'
    },
    'myfitnesspal': {
        'required_columns': ['Date', 'Calories', 'Carbohydrates (g)', 'Fat (g)', 'Protein (g)'],
        'description': 'MyFitnessPal nutrition tracking',
        'date_column': 'Date'
    }
}
```

**Detection Logic:**

```python
def _detect_csv_format(self, columns: List[str]) -> Tuple[str, Dict]:
    """
    Match CSV columns against known formats.
    
    Returns: (format_name, format_spec) or ('generic', {})
    """
    
    # Normalize column names (case-insensitive, strip whitespace)
    normalized_cols = [col.strip().lower() for col in columns]
    
    for format_name, spec in self.KNOWN_FORMATS.items():
        # Check required columns
        required = [r.lower() for r in spec['required_columns']]
        if all(req in normalized_cols for req in required):
            return format_name, spec
    
    return 'generic', {}
```

**Format-Specific Parsing:**

Each detected format gets custom handling:

```python
def _parse_linkedin(self, rows: List[Dict]) -> ParsedDocument:
    """
    LinkedIn: Focus on professional network.
    Extract: Companies, positions, connection timeline
    """
    
    companies = {}
    positions = {}
    
    for row in rows:
        company = row.get('Company', '')
        position = row.get('Position', '')
        
        if company:
            companies[company] = companies.get(company, 0) + 1
        if position:
            positions[position] = positions.get(position, 0) + 1
    
    # Format findings
    text = "=== LinkedIn Professional Network ===\n\n"
    text += f"Total Connections: {len(rows)}\n\n"
    
    text += "Top Companies:\n"
    for company, count in sorted(companies.items(), key=lambda x: -x[1])[:10]:
        text += f"- {company}: {count} connections\n"
    
    # ... more formatting
    
    return ParsedDocument(content=text, metadata={...})
```

**Generic CSV Handling:**

When format unknown:
1. Detect date columns (by name or content)
2. Detect numeric columns
3. Identify categorical columns (low cardinality)
4. Create summary statistics
5. Format as readable text

**PARSER_METADATA:**

```python
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
```

---

## Task 5: Notion Export Parser

**Priority:** ⭐⭐⭐⭐ HIGH - "Second brain" platform

**Why Important:** Notion is hugely popular for personal knowledge management. Exports preserve structure that reveals how user thinks and organizes.

### Requirements

**Create:** `_scripts/recog_engine/ingestion/parsers/notion.py`

**Dependencies:** Add to requirements.txt:
```
markdown>=3.5.0
```

**Notion Export Structure:**

```
Export-XXXXX/
├── Personal 123abc.md
├── Work Notes 456def.md
├── Project Alpha 789ghi/
│   ├── Project Alpha 789ghi.md
│   ├── Meeting Notes 111jkl.md
│   └── Todo List 222mno.csv
├── Databases/
│   └── Task Database 333pqr.csv
└── images/
    └── screenshot_444stu.png
```

**Format Detection:**

Notion export detection signals:
- Root folder named `Export-XXXXXXXX`
- Markdown files with ID suffixes (e.g., `Page Name 123abc.md`)
- CSV files for database views
- `images/` or `files/` subdirectories

**What to Extract:**

**From Markdown Files:**
- Page title (first H1 or filename)
- Content (preserve heading hierarchy)
- Internal links `[[Other Page]]`
- Database embeds
- Created/modified dates (from filename ID if available)
- Tags/properties in frontmatter (if present)

**From CSV Files (Databases):**
- Column headers (property names)
- Rows (database entries)
- Dates, tags, relations
- Format as structured text

**Text Formatting:**

```
=== Notion Page: Personal Goals ===
Path: Root > Personal
Type: Page

# 2025 Goals

## Career
- Launch ReCog commercial plugins
- Build EhkoLabs consulting business

## Personal
- Complete Mirrorwell identity work
- Regular therapy sessions

Links to: [[Career Planning]], [[Therapy Notes]]

---

=== Notion Database: Task Tracker ===
Path: Root > Work Notes > Task Database

Properties:
- Name (text)
- Status (select: Not Started, In Progress, Done)
- Priority (select: Low, Medium, High)
- Due Date (date)

Sample Entries:
1. Complete ReCog documentation | Status: In Progress | Priority: High | Due: 2025-01-20
2. Update EhkoLabs website | Status: Not Started | Priority: Medium | Due: 2025-01-25
...
```

**Hierarchy Preservation:**

Maintain folder structure in metadata:
```python
metadata = {
    'page_count': 15,
    'database_count': 3,
    'hierarchy': {
        'Root': {
            'Personal': ['Personal Goals.md', 'Therapy Notes.md'],
            'Work Notes': ['Meeting Notes.md', 'Task Database.csv'],
            'Project Alpha': ['Project Alpha.md', 'Todo List.csv']
        }
    }
}
```

**Edge Cases:**
- Untitled pages (use filename)
- Empty pages (note as placeholder)
- Deleted/archived pages (include with flag)
- Very large pages (>50,000 words) - chunk
- Nested pages (>5 levels deep) - preserve structure

**PARSER_METADATA:**

```python
PARSER_METADATA = {
    "file_type": "Notion Export",
    "extensions": [".md", ".csv"],  # Within Notion structure
    "cypher_context": {
        "description": "Notion workspace containing notes, databases, and knowledge base",
        "requires_user_input": [],
        "extractable": [
            "Note content and knowledge organization",
            "Database entries with properties and relations",
            "Page hierarchy and information architecture",
            "Internal links showing concept relationships",
            "Created/modified timestamps",
            "Tags and categorization system",
            "Tasks and project tracking"
        ],
        "suggestions": [
            "Notion exports preserve your knowledge structure",
            "Database properties reveal how you organize information",
            "Internal links show how concepts connect in your mind",
            "Page hierarchy indicates your mental models",
            "Tags and properties are valuable metadata for pattern detection"
        ]
    }
}
```

**Implementation Strategy:**

```python
def parse(self, file_path: str) -> ParsedDocument:
    """
    Handle Notion export by:
    1. Detecting if file is part of Notion export
    2. Finding export root directory
    3. Parsing all .md and .csv files
    4. Reconstructing hierarchy
    5. Combining into structured document
    """
    
    # Find export root
    export_root = self._find_export_root(file_path)
    
    if export_root:
        # Process entire export
        return self._parse_full_export(export_root)
    else:
        # Single Notion-style markdown file
        return self._parse_single_markdown(file_path)
```

---

## Registration & Integration

### Update Parser Registry

**File:** `_scripts/recog_engine/ingestion/parsers/__init__.py`

```python
from .archive import ArchiveParser
from .calendar import ICSParser
from .contacts import VCFParser
from .csv_enhanced import EnhancedCSVParser
from .notion import NotionParser

# Existing imports...
from .text import TextParser
from .pdf import PDFParser
# ... etc

# Parser registry
ALL_PARSERS = [
    ArchiveParser,      # Must be first (handles containers)
    ICSParser,
    VCFParser,
    EnhancedCSVParser,
    NotionParser,
    # Existing parsers...
    TextParser,
    PDFParser,
    # ...
]
```

**Order Matters:**
- ArchiveParser first (detects containers)
- Specialized parsers before generic (EnhancedCSVParser before basic CSV)

---

## Dependencies

**Update:** `_scripts/requirements.txt`

```txt
# Existing dependencies...
python-docx>=1.1.0
extract-msg>=0.48.0
openpyxl>=3.1.0

# Phase 1 additions
icalendar>=5.0.0        # ICS calendar parsing
vobject>=0.9.6          # VCF contact parsing
markdown>=3.5.0         # Markdown enhancement (Notion)

# Note: zipfile, tarfile, csv are stdlib - no install needed
```

---

## Testing Strategy

### Create Test Fixtures

**Directory:** `_scripts/tests/fixtures/phase1/`

**Sample Files Needed:**

1. **sample_archive.zip**
   - Contains: 1 PDF, 1 DOCX, 1 TXT
   - Used to test generic archive extraction

2. **sample_calendar.ics**
   - 10-20 events
   - Mix of single/recurring
   - Include attendees, locations

3. **sample_contacts.vcf**
   - 10-20 contacts
   - Mix of complete/minimal info
   - Different organizations

4. **sample_linkedin.csv**
   - LinkedIn connection export format
   - 20+ rows

5. **sample_netflix.csv**
   - Netflix viewing history format
   - 50+ rows

6. **sample_spotify.csv**
   - Spotify streaming history format
   - 100+ rows

7. **sample_notion_export.zip**
   - Notion export structure
   - 3-5 pages
   - 1 database CSV

### Unit Tests

**File:** `_scripts/tests/test_parsers_phase1.py`

```python
import pytest
from pathlib import Path
from recog_engine.ingestion.parsers import (
    ArchiveParser, ICSParser, VCFParser, 
    EnhancedCSVParser, NotionParser
)

FIXTURES = Path(__file__).parent / 'fixtures' / 'phase1'

class TestArchiveParser:
    def test_can_parse_zip(self):
        parser = ArchiveParser()
        assert parser.can_parse('test.zip')
        assert parser.can_parse('test.tar.gz')
        assert not parser.can_parse('test.pdf')
    
    def test_extracts_zip(self):
        parser = ArchiveParser()
        result = parser.parse(str(FIXTURES / 'sample_archive.zip'))
        assert result.content
        assert 'parser' in result.metadata

class TestICSParser:
    def test_can_parse_ics(self):
        parser = ICSParser()
        assert parser.can_parse('calendar.ics')
        assert not parser.can_parse('calendar.txt')
    
    def test_extracts_events(self):
        parser = ICSParser()
        result = parser.parse(str(FIXTURES / 'sample_calendar.ics'))
        assert 'event' in result.content.lower()
        assert result.metadata['event_count'] > 0

class TestVCFParser:
    def test_can_parse_vcf(self):
        parser = VCFParser()
        assert parser.can_parse('contacts.vcf')
    
    def test_extracts_contacts(self):
        parser = VCFParser()
        result = parser.parse(str(FIXTURES / 'sample_contacts.vcf'))
        assert 'contact' in result.content.lower()
        assert result.metadata['contact_count'] > 0

class TestEnhancedCSVParser:
    def test_detects_linkedin(self):
        parser = EnhancedCSVParser()
        result = parser.parse(str(FIXTURES / 'sample_linkedin.csv'))
        assert 'linkedin' in result.metadata.get('detected_format', '')
    
    def test_detects_netflix(self):
        parser = EnhancedCSVParser()
        result = parser.parse(str(FIXTURES / 'sample_netflix.csv'))
        assert 'netflix' in result.metadata.get('detected_format', '')

class TestNotionParser:
    def test_can_detect_notion_export(self):
        parser = NotionParser()
        # Should detect Notion-style filenames
        assert parser.can_parse('Export-XXX/Page Name 123abc.md')
    
    def test_parses_notion_export(self):
        parser = NotionParser()
        result = parser.parse(str(FIXTURES / 'sample_notion_export.zip'))
        assert 'notion' in result.content.lower()
```

**Run Tests:**
```bash
cd C:\EhkoVaults\ReCog\_scripts
pytest tests/test_parsers_phase1.py -v
```

---

## Integration with Upload Flow

### Current Upload Process

1. User uploads file → `/api/upload`
2. File saved, parser detected → Returns `file_id`
3. Preflight created → `/api/preflight/<id>`
4. User confirms → `/api/preflight/<id>/confirm`
5. Processing queued → Worker extracts insights

### What Changes (None!)

Archive parser integrates seamlessly:
- Upload ZIP → Detected as ArchiveParser
- Preflight sees archive contents
- Confirm → Worker extracts and processes

**No API changes needed.**

---

## Cypher Integration

### Upload Response Enhancement

**File:** `_scripts/server.py`

In `/api/upload` endpoint, include parser metadata:

```python
@app.route("/api/upload", methods=["POST"])
def upload_file():
    # ... existing upload logic ...
    
    # Detect parser
    parser = detect_parser(file_path)
    
    # Include metadata in response
    file_info = {
        "id": file_id,
        "filename": filename,
        "size": file_size,
        "detected_parser": parser.__class__.__name__,
        "parser_metadata": getattr(parser, 'PARSER_METADATA', None)
    }
    
    return api_response(data=file_info)
```

### Cypher Context Usage

Frontend `CypherContext.jsx` can use `parser_metadata.cypher_context`:

```javascript
// When file uploaded
if (parserMetadata?.cypher_context) {
    const { description, extractable, suggestions } = parserMetadata.cypher_context;
    
    // Show Cypher message
    addMessage({
        role: 'assistant',
        content: `I see you've uploaded a ${parserMetadata.file_type}. ${description}
        
I can extract: ${extractable.join(', ')}

${suggestions[0]}`
    });
}
```

---

## Success Criteria

### Phase 1 Complete When:

- [x] All 5 parsers implemented
- [x] All parsers registered in `__init__.py`
- [x] Dependencies added to `requirements.txt`
- [x] Unit tests pass
- [x] Sample files processed successfully
- [x] Parser metadata included in upload responses
- [x] Cypher shows format-specific suggestions
- [x] Archive extraction works end-to-end
- [x] No breaking changes to existing parsers

### Quality Checks

**Code Quality:**
- Docstrings on all classes/methods
- Type hints where helpful
- Error handling (try/except)
- Logging for debugging

**User Experience:**
- Helpful error messages
- Processing time estimates
- Privacy warnings where appropriate
- Clear metadata in responses

**Performance:**
- Large files (>50MB) don't crash
- Temp file cleanup works
- Memory usage reasonable

---

## Next Steps After Phase 1

**Immediate (Same Session):**
1. Test with real files (if available)
2. Fix any bugs found
3. Update documentation

**Phase 2 Prep:**
1. Get Facebook export
2. Spec Facebook/Instagram parsers
3. Spec Twitter parser
4. Spec Telegram/Discord parsers

**Documentation:**
- Update README with supported formats
- Add parser development guide
- Create format detection troubleshooting guide

---

## Implementation Priority

**Claude Code should implement in this order:**

1. **ArchiveParser** (Foundation - everything else depends on this)
2. **ICSParser** (Quick win, well-documented format)
3. **VCFParser** (Quick win, similar to ICS)
4. **EnhancedCSVParser** (More complex, but high value)
5. **NotionParser** (Most complex, but important)

After each parser:
- Write basic test
- Verify it registers
- Test with sample file

**Don't wait to test all at once** - iterative testing catches issues early.

---

## Common Pitfalls to Avoid

1. **Character Encoding**
   - Always use UTF-8
   - Handle BOM (Byte Order Mark) in CSVs: `encoding='utf-8-sig'`
   - Test with international characters

2. **Temporary File Cleanup**
   - Use `with tempfile.TemporaryDirectory()` - auto-cleanup
   - Don't manually delete temp files (error-prone)

3. **Date Parsing**
   - Timezones are hard - document assumptions
   - Use ISO format when possible
   - Handle missing/malformed dates gracefully

4. **Large Files**
   - Don't load entire file into memory
   - Stream/chunk large CSVs
   - Set reasonable size limits

5. **Parser Detection**
   - File extensions lie (user can rename)
   - Always validate content
   - Fail gracefully if format unexpected

---

## Reference Documentation

**Python Libraries:**
- `zipfile`: https://docs.python.org/3/library/zipfile.html
- `tarfile`: https://docs.python.org/3/library/tarfile.html
- `icalendar`: https://icalendar.readthedocs.io/
- `vobject`: https://vobject.readthedocs.io/
- `csv`: https://docs.python.org/3/library/csv.html

**Format Specs:**
- iCalendar (RFC 5545): https://datatracker.ietf.org/doc/html/rfc5545
- vCard (RFC 6350): https://datatracker.ietf.org/doc/html/rfc6350
- CSV (RFC 4180): https://datatracker.ietf.org/doc/html/rfc4180

---

**Ready for implementation. Claude Code has full autonomy to prioritize tasks and make implementation decisions within this spec.**

# Parser Quirks and Known Issues

This document catalogs format-specific quirks, known issues, and workarounds
implemented in ReCog's parser system.

## Table of Contents

1. [Archive Formats](#archive-formats)
2. [Calendar (ICS)](#calendar-ics)
3. [Contacts (VCF)](#contacts-vcf)
4. [CSV](#csv)
5. [Platform Exports](#platform-exports)
6. [XML](#xml)

---

## Archive Formats

### ZIP

**Security Risks:**
- **Zip Bombs**: Malicious archives with extreme compression ratios (e.g., 42.zip expands from 42KB to 4.5PB)
  - *Defense*: MAX_COMPRESSION_RATIO = 100 (100:1 limit)
  - *Defense*: MAX_FILE_COUNT = 10000
  - *Defense*: MAX_EXTRACTED_SIZE = 500MB

- **Path Traversal (ZipSlip)**: Filenames containing `../` can write outside target directory
  - *Defense*: `Path.resolve()` + `is_relative_to()` validation

- **Nested Archives**: Archives within archives can bypass single-level security checks
  - *Defense*: MAX_NESTING_DEPTH = 3

**Encrypted Archives:**
- Detected via `info.flag_bits & 0x1` check
- Returns error message rather than attempting extraction

### TAR

**Security:**
- Python 3.12+ uses `tarfile.extractall(filter='data')` by default
- Older versions fall back to manual path validation
- TAR supports symlinks which could be malicious - filtered out

**Compression:**
- `.tar.gz` and `.tgz` handled identically
- Compression ratio not easily pre-calculated (streamed decompression)

---

## Calendar (ICS)

### Timezone Handling

**Windows vs IANA Timezones:**
Outlook exports use Windows timezone names instead of IANA identifiers.

| Windows Name | IANA Name |
|--------------|-----------|
| "Eastern Standard Time" | "America/New_York" |
| "Pacific Standard Time" | "America/Los_Angeles" |
| "GMT Standard Time" | "Europe/London" |
| "AUS Eastern Standard Time" | "Australia/Sydney" |

*Implementation*: `WINDOWS_TZ_MAP` in `calendar.py`

**Google Calendar:**
- Uses `X-WR-TIMEZONE` header for default timezone
- May contain non-standard TZID values

**Apple Calendar:**
- Includes `X-APPLE-*` custom properties
- Usually follows IANA conventions

### Recurring Events

**RRULE Parsing:**
- `recurring-ical-events` library handles complex rules
- EXDATE (exceptions) and RDATE (additions) supported
- DST transitions can cause off-by-one-hour issues

**All-Day Events:**
- Stored as DATE (not DATETIME) values
- `isinstance(dt, date) and not isinstance(dt, datetime)` check
- Converted to midnight UTC for storage

---

## Contacts (VCF)

### Encoding Issues

**vCard Version Differences:**
| Version | Charset | Common Sources |
|---------|---------|----------------|
| 2.1 | Any (often Windows-1252) | Old Android, Outlook 2003 |
| 3.0 | UTF-8 (usually) | Most modern apps |
| 4.0 | UTF-8 (mandated) | Apple Contacts, Google |

**Encoding Fallback Chain:**
1. UTF-8
2. UTF-16 (Windows export)
3. Windows-1252 (legacy Outlook)
4. ISO-8859-1 (Latin-1 fallback)

**Samsung/Android Quirk:**
- Uses `CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE`
- Requires explicit decoding after vobject parsing

### Phone Number Normalization

**E.164 Format:**
- Uses `phonenumbers` library when available
- Falls back to digit-only cleaning
- Default region: 'AU' (configurable)

Example: `(555) 123-4567` → `+15551234567`

---

## CSV

### Encoding Detection

**Detection Order:**
1. BOM (Byte Order Mark) detection
2. `charset-normalizer` library (4-5x faster than chardet)
3. Heuristic: UTF-8 → UTF-16 → Latin-1

**BOM Values:**
| BOM | Encoding |
|-----|----------|
| `\xef\xbb\xbf` | UTF-8-sig |
| `\xff\xfe` | UTF-16-LE |
| `\xfe\xff` | UTF-16-BE |

### Large File Handling

**Threshold:** Files > 100MB use `polars` with lazy evaluation

**polars Benefits:**
- Streaming: doesn't load entire file
- Lazy evaluation: only computes what's needed
- Memory efficient for multi-GB files

**Fallback:** Standard `csv` module with warning if polars unavailable

### Delimiter Detection

**Supported Delimiters:** `,`, `;`, `\t`, `|`

**csv.Sniffer Limitations:**
- Struggles with tab-delimited files
- Can be fooled by quoted fields containing delimiters
- Falls back to comma if detection fails

---

## Platform Exports

### Facebook / Instagram

**Mojibake Encoding Bug:**
Meta exports JSON with UTF-8 double-encoded as Latin-1.

```
"café" appears as "cafÃ©"
```

**Fix:** `text.encode('latin1').decode('utf-8')`

**Detection:**
- Facebook: `messages/inbox/` directory structure
- Instagram: `instagram_` prefix in filenames

### Twitter

**JavaScript-Wrapped JSON:**
Twitter archives wrap JSON data in JavaScript assignments:

```javascript
window.YTD.tweet.part0 = [...]
```

**Fix:** Strip prefix with regex before JSON parsing:
```python
re.sub(r'^window\.YTD\.\w+\.part\d+\s*=\s*', '', content)
```

### Google Takeout

**Format Complexity:**
Different Google services use different formats:

| Service | Format | Notes |
|---------|--------|-------|
| Gmail | MBOX | Standard email archive |
| Chrome History | SQLite | WebKit timestamps |
| Location History | JSON | E7 coordinates |
| YouTube | HTML/JSON | Mixed formats |

**WebKit Timestamps:**
Microseconds since January 1, 1601.

**E7 Coordinates:**
Latitude/longitude stored as integers. Divide by 10^7 for decimal degrees.

### LinkedIn

**CSV Format:**
Uses standard CSV with headers:
- `Connections.csv`: First Name, Last Name, Company, Position, Connected On
- `Messages.csv`: From, To, Date, Subject, Content

### WhatsApp

**Text Export Format:**
```
[date, time] - sender: message
```

**Timestamp Quirk:** Format varies by device locale. Common patterns:
- `[15/01/2024, 10:30:00]`
- `[1/15/24, 10:30 AM]`
- `[2024-01-15 10:30]`

---

## XML

### Apple Health

**File Size:** Can exceed 1GB with millions of records

**Streaming Required:**
- Use `lxml.etree.iterparse()` with `elem.clear()` after each record
- Also clear preceding siblings to prevent memory buildup

**Record Types:**
| Type Identifier | Friendly Name |
|-----------------|---------------|
| `HKQuantityTypeIdentifierStepCount` | steps |
| `HKQuantityTypeIdentifierHeartRate` | heart_rate |
| `HKQuantityTypeIdentifierActiveEnergyBurned` | active_energy |
| `HKCategoryTypeIdentifierSleepAnalysis` | sleep |

### Browser History

**Database Locking:**
Chrome and Firefox lock their SQLite databases during operation.
- *Workaround*: Copy file before opening

**Chrome Timestamps:** WebKit format (microseconds since 1601-01-01)
**Firefox Timestamps:** Unix epoch microseconds

---

## Parser Selection Decision Tree

```
                    File Input
                        │
                        ▼
               ┌──────────────────┐
               │ Content Detection│
               │  (python-magic)  │
               └────────┬─────────┘
                        │
            ┌───────────┴───────────┐
            │                       │
            ▼                       ▼
     Is Archive?              Other Format
            │                       │
            ▼                       ▼
    ┌───────────────┐      Route by MIME
    │Platform Export│         or Extension
    │  Detection    │
    └───────┬───────┘
            │
    ┌───────┴────────────────────────┐
    │         │          │           │
    ▼         ▼          ▼           ▼
Facebook  Twitter  Google      Generic
Parser    Parser   Takeout     Archive
                   Parser      Processor
```

---

## Adding New Parsers

1. Create parser class in `ingestion/parsers/`
2. Extend `BaseParser` ABC
3. Implement required methods:
   - `can_parse(path)` - content/extension check
   - `parse(path)` - returns ParsedContent
   - `get_file_type()` - type identifier
   - `get_extensions()` - list of extensions
4. Add to parser list in `base.py:get_parser()`
5. Document quirks here if applicable
6. Add test fixtures and property tests

---

## License Compatibility

| Library | License | AGPL Safe |
|---------|---------|-----------|
| icalendar | BSD | ✅ |
| vobject | Apache-2.0 | ✅ |
| polars | MIT | ✅ |
| phonenumbers | Apache-2.0 | ✅ |
| charset-normalizer | MIT | ✅ |
| python-magic | MIT | ✅ |
| lxml | BSD | ✅ |
| hypothesis | MPL-2.0 | ✅ |
| chardet | LGPL-2.1 | ⚠️ (LGPL) |
| whatstk | GPL-3.0 | ❌ |

GPL-3.0 libraries cannot be used without releasing code under GPL.
LGPL libraries require careful handling (dynamic linking OK, modifications must be released).

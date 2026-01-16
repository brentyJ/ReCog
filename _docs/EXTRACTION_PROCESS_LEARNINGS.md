# Extraction Process Learnings

**Date:** 2026-01-16
**Context:** Instagram export extraction with run versioning

This document captures issues encountered and solutions applied during the extraction process, to inform future parser development and avoid repeating mistakes.

---

## Issues Encountered & Solutions

### 1. Content Not Stored in Database

**Issue:** Original extraction was done on-the-fly; parsed content wasn't stored in `ingested_documents` or `document_chunks` tables. Made re-extraction difficult.

**Solution:** Re-parsed source data directly from export folder.

**Future Fix:** Store parsed content in `document_chunks` table during initial ingestion, or at minimum store source path for re-parsing.

**Files affected:** `ingested_documents` schema lacks content column.

---

### 2. Parser Returns Different Object Than Expected

**Issue:** Script expected `result.success` and `result.data`, but `InstagramHTMLParser.parse()` returns `ParsedContent` object with `text` and `metadata` attributes.

**Solution:** Changed to `parsed.metadata.get('messages', [])`.

**Future Fix:** Standardize parser return types across all parsers. Consider:
```python
@dataclass
class ParseResult:
    success: bool
    data: Optional[ParsedContent] = None
    error: Optional[str] = None
```

**Files affected:** All parsers in `ingestion/parsers/`

---

### 3. Path Type Mismatch

**Issue:** `parser.parse(str(path))` failed because parser expected `Path` object, but received string.

**Solution:** Pass `Path` object directly: `parser.parse(INSTAGRAM_EXPORT_PATH)`.

**Future Fix:** Parsers should accept both `str` and `Path`, converting internally:
```python
def parse(self, path: Union[str, Path]) -> ParsedContent:
    path = Path(path) if isinstance(path, str) else path
```

**Files affected:** `instagram.py:691` - uses `/` operator on path

---

### 4. Provider Initialization Requires API Key

**Issue:** `AnthropicProvider()` raised `TypeError: missing 1 required positional argument: 'api_key'`.

**Solution:** Load from environment: `os.environ.get('ANTHROPIC_API_KEY')`.

**Future Fix:** Consider factory pattern or config loader:
```python
def get_provider(name: str = "anthropic") -> LLMProvider:
    # Auto-loads config from environment
```

**Files affected:** `core/providers/anthropic_provider.py`

---

### 5. Module Import Paths

**Issue:** `from recog_engine.core.providers.anthropic import AnthropicProvider` failed - file is `anthropic_provider.py`.

**Solution:** Use correct filename: `from recog_engine.core.providers.anthropic_provider import AnthropicProvider`.

**Future Fix:** Create `__init__.py` exports for cleaner imports:
```python
# core/providers/__init__.py
from .anthropic_provider import AnthropicProvider
```

---

### 6. Missing Dependencies

**Issue:** `from dotenv import load_dotenv` raised `ModuleNotFoundError`.

**Solution:** Manual .env parsing instead of depending on python-dotenv.

**Future Fix:** Either:
- Add python-dotenv to requirements.txt, OR
- Create standardized config loading that doesn't require external packages

---

### 7. Synth Engine Requires Specific Insight Status

**Issue:** SynthEngine's `run_synthesis()` only processes insights with `status='raw'`.

**Solution:** Update insight status before synthesis:
```python
cursor.execute("UPDATE insights SET status = 'raw' WHERE run_id = ?", (run_id,))
```

**Future Fix:** Document this requirement clearly, or make it configurable.

---

### 8. SMS Parser Uses Different Field Name Than Instagram

**Issue:** SMS messages showing as "empty" despite 841 messages loaded. Chunks were skipped with "(empty)" message.

**Root Cause:** SMS parser stores message content in `text` field, while Instagram parser uses `content` field.

**Solution:** Check both fields:
```python
content = msg.get('text') or msg.get('content', '')
```

**Future Fix:** Standardize field names across all message parsers:
```python
# All message parsers should use:
{
    "content": "message text",  # Standardize on 'content'
    "sender": "name",
    "timestamp": "ISO8601",
    "direction": "sent|received"  # Optional
}
```

**Files affected:** `ingestion/parsers/messages.py`, all extraction scripts

---

### 9. API Cost Management - Hybrid Extraction Mode

**Issue:** Running Tier 1-3 extraction via API scripts consumes API credits (pay-per-token). For personal use, this adds up quickly.

**Solution:** Implemented `--prepare-only` mode that:
1. Parses and chunks data (free, local processing)
2. Exports chunks to JSON files in `_data/chunks/<run_id>/`
3. User does extraction in Claude Code conversation (uses Max plan, no API cost)
4. Saves insights to database via conversation

**When to use each mode:**
- **API mode:** Production use, other users with API keys, automation
- **Prepare-only:** Personal use, cost-conscious, fine-tuning extraction prompts

**Files affected:** `run_sms_extraction.py`, `run_extraction_with_context.py`

---

### 10. Timestamp-Based Chunking with Small Chunk Merging

**Issue:** Character-based chunking (splitting every N characters) loses temporal context. Messages from 2017 might be grouped with 2022 messages if they happen to fall in the same character range.

**Solution:** Chunk by time period (e.g., 6-month windows) using actual message timestamps.

**Additional issue:** Sparse early data creates very small chunks that get skipped.

**Solution:** Merge small chunks (< N messages) with the next chunk:
```python
if len(chunk_msgs) < min_messages and i < len(raw_chunks) - 1:
    carry_over = chunk_msgs  # Merge with next
```

**Result:** Run 4 achieved 100% date coverage vs 0% in baseline.

**Files affected:** `run_extraction_with_context.py`, `run_sms_extraction.py`

---

## Architectural Recommendations

### For New Parsers

1. **Consistent return type:** All parsers should return same `ParseResult` type
2. **Path handling:** Accept both `str` and `Path` in `parse()` method
3. **Store raw content:** Save parsed text to database for re-extraction
4. **Metadata structure:** Standardize metadata keys across parsers:
   ```python
   metadata = {
       "format": "parser_name",
       "messages": [...],  # If chat/messaging data
       "items": [...],     # Generic list
       "statistics": {...},
       "parsed_at": datetime.now().isoformat()
   }
   ```

### For Extraction Scripts

1. **Provider factory:** Create utility to instantiate providers with config
2. **Run management:** Always create run before extraction, complete after
3. **Context injection:** Standardize context building (age, life events)
4. **Progress tracking:** Log chunk progress for long-running extractions

### For Run Versioning

1. **Always link to run:** Every insight/pattern should have `run_id`
2. **Record context config:** Store what context was injected in run metadata
3. **Parent runs:** Set parent_run_id for comparison tracking
4. **Delta recording:** Log specific changes between runs

---

## Checklist for Future Extractions

### Pre-Extraction
- [ ] Verify source data path exists
- [ ] Check parser field names (`text` vs `content` for messages)
- [ ] Decide: API mode or prepare-only (hybrid) mode

### Run Setup
- [ ] Create extraction_run record before starting
- [ ] Load user_profile.json for DOB context
- [ ] Load life_context for timeline injection

### Chunking
- [ ] Use timestamp-based chunking (not character-based)
- [ ] Set appropriate chunk period (default: 6 months)
- [ ] Enable small chunk merging (min 15-20 messages)
- [ ] Tag insights with actual date ranges from chunks

### Extraction
- [ ] **API mode:** Run extraction, save insights with run_id
- [ ] **Hybrid mode:** Export chunks, do extraction in-conversation

### Post-Extraction
- [ ] Update insight status for synthesis
- [ ] Run synthesis and link patterns to run
- [ ] Complete run with final counts
- [ ] Generate comparison report if parent run exists

## Hybrid Workflow Checklist

For cost-effective personal extraction using Claude Code (Max plan):

1. **Prepare:**
   ```bash
   python run_sms_extraction.py <path> --prepare-only
   # or
   python run_extraction_with_context.py --prepare-only
   ```

2. **In Claude Code conversation:**
   - Read manifest: `_data/chunks/<run_id>/manifest.json`
   - Read each chunk file
   - Extract insights in-conversation
   - Save to database via SQL

3. **Benefits:**
   - Uses flat-rate Max plan (already paid)
   - No API credits consumed
   - Can fine-tune extraction approach interactively

---

## Code Snippets for Reuse

### Load Environment Safely
```python
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())
```

### Get Provider with Config
```python
api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('RECOG_ANTHROPIC_API_KEY')
if not api_key:
    raise ValueError("No API key found")
provider = AnthropicProvider(api_key=api_key)
```

### Build Life Context for Date Range
```python
def build_life_context_for_period(start_year: int, end_year: int, db_path: Path) -> str:
    from recog_engine.run_store import get_life_context_for_date
    mid_date = f"{(start_year + end_year) // 2}-06-15"
    contexts = get_life_context_for_date(mid_date, db_path)
    # ... format and return
```

### Handle Different Message Field Names
```python
def format_messages_for_extraction(messages: List[Dict]) -> str:
    """Format messages, handling different parser field names."""
    lines = []
    for msg in messages:
        sender = msg.get('sender', 'Unknown')
        # SMS uses 'text', Instagram uses 'content'
        content = msg.get('text') or msg.get('content', '')
        timestamp = msg.get('timestamp', '')
        if content:
            date_str = timestamp[:10] if timestamp else ''
            lines.append(f"[{date_str}] {sender}: {content}")
    return "\n".join(lines)
```

### Timestamp-Based Chunking with Merging
```python
def chunk_messages_by_time(messages, chunk_months=6, min_messages=20):
    """Chunk by time period, merging small chunks."""
    # Sort by timestamp
    valid = sorted([m for m in messages if m.get('timestamp')],
                   key=lambda m: m['timestamp'])

    # Create chunks at time boundaries
    # Merge small chunks (<min_messages) with next chunk
    # See run_sms_extraction.py for full implementation
```

---

*This document should be updated as new issues are encountered and solved.*

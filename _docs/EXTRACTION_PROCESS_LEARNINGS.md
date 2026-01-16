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

- [ ] Verify source data path exists
- [ ] Create extraction_run record before starting
- [ ] Load user_profile.json for DOB context
- [ ] Load life_context for timeline injection
- [ ] Chunk content appropriately (~100k chars)
- [ ] Map chunk index to approximate date range
- [ ] Save insights with run_id
- [ ] Update insight status for synthesis
- [ ] Run synthesis and link patterns to run
- [ ] Complete run with final counts
- [ ] Generate comparison report if parent run exists

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

---

*This document should be updated as new issues are encountered and solved.*

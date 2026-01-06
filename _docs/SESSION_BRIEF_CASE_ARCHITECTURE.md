# ReCog Case Architecture - Session Brief for Claude Code

**Date:** 2026-01-05  
**Context:** Major architectural addition to ReCog system  
**Status:** Planning complete, ready for implementation  
**Next:** Backend schema + API implementation

---

## What We Accomplished Today

### 1. UI Consolidation
- Archived 3 old/duplicate front ends
- Established `C:\EhkoDev\recog-ui` as single source of truth
- Cleaned up ReCog vault structure

### 2. Case Architecture Design
Designed complete "Case" system to transform ReCog from analysis tool → document intelligence platform.

---

## Core Decisions (Locked In)

### Terminology
- **"Case"** - organizational container (not "project", "investigation", "vault")
- **"Findings"** - validated insights (promoted from raw insights)
- **"Timeline"** - auto-generated chronicle of case evolution

### Philosophy
1. ✅ **Closed corpus** - analyze documents you HAVE, not web search
2. ✅ **Context injection** - guide analysis upfront via case context
3. ✅ **Trust the system** - engineer out hallucinations, not post-hoc review
4. ✅ **Simple validation** - verified/needs_verification flags, not complex workflows
5. ✅ **Document intelligence** - not a research assistant

### What We're NOT Building (Yet)
- ❌ Chat interface (Phase 2)
- ❌ Export functionality
- ❌ Web search integration
- ❌ Hypothesis tracking system
- ❌ Complex validation workflows

---

## Architecture: Case System

```
CASE
│
├── Manifest
│   ├── Title: "Q3 Sales Analysis"
│   ├── Context: "Revenue dropped 15%, investigating causes"
│   ├── Focus Areas: [pricing, competition, market conditions]
│   ├── Created: Jan 5, 2026
│   └── Status: active/archived
│
├── Documents (chronological)
│   ├── financial_report_q3.pdf (added: Jan 5)
│   ├── customer_survey.xlsx (added: Jan 8)
│   └── competitor_analysis.docx (added: Jan 10)
│
├── Findings (validated insights)
│   ├── Status: verified | needs_verification | rejected
│   ├── Confidence: high | medium | low
│   ├── Tags: auto-generated from content
│   ├── Source citations: [doc, page, excerpt]
│   └── Added date, Validated date
│
├── Patterns (cross-document synthesis)
│   └── Links multiple findings
│
└── Timeline (auto-generated)
    ├── Jan 5: Case created, 2 docs added
    ├── Jan 5: 18 findings extracted
    ├── Jan 8: New doc added, 12 findings
    └── (Human can annotate: "This contradicted hypothesis X")
```

---

## Database Schema (New Tables)

### 1. cases
```sql
CREATE TABLE cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    context TEXT,              -- Initial question/assignment
    focus_areas JSON,          -- Array of strings ["pricing", "competition"]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived'))
);
```

### 2. case_documents
```sql
CREATE TABLE case_documents (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    document_id TEXT NOT NULL,  -- Links to existing document tracking
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    impact_notes TEXT,          -- Human annotations about this doc's impact
    findings_count INTEGER DEFAULT 0,
    entities_count INTEGER DEFAULT 0,
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);
```

### 3. findings
```sql
CREATE TABLE findings (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    insight_id TEXT NOT NULL,   -- Links to insights table
    status TEXT DEFAULT 'needs_verification' 
        CHECK(status IN ('verified', 'needs_verification', 'rejected')),
    verified_at TIMESTAMP,
    tags JSON,                  -- Array of strings
    user_notes TEXT,            -- Optional human annotation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
    FOREIGN KEY (insight_id) REFERENCES insights(id) ON DELETE CASCADE,
    UNIQUE(case_id, insight_id) -- Prevent duplicate promotions
);
```

### 4. case_timeline
```sql
CREATE TABLE case_timeline (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    event_type TEXT NOT NULL 
        CHECK(event_type IN ('case_created', 'doc_added', 'finding_verified', 
                             'finding_rejected', 'pattern_found', 'note_added')),
    event_data JSON,            -- Flexible payload {doc_id, count, etc}
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    human_annotation TEXT,      -- Optional user notes
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);
```

### Modified Existing Tables

Add `case_id` foreign key to:
- `insights` - which case does this insight belong to?
- `patterns` - which case is this pattern from?
- `preflight_sessions` - associate upload session with case

```sql
ALTER TABLE insights ADD COLUMN case_id TEXT REFERENCES cases(id);
ALTER TABLE patterns ADD COLUMN case_id TEXT REFERENCES cases(id);
ALTER TABLE preflight_sessions ADD COLUMN case_id TEXT REFERENCES cases(id);
```

---

## Context Injection Strategy

**Critical: This prevents hallucination/manipulation**

When processing documents for a case, inject case context into extraction prompts:

```python
# In extraction.py, modify build_extraction_prompt()

def build_extraction_prompt(text, case_context=None):
    system_prompt = """You are analyzing documents to extract factual insights."""
    
    if case_context:
        system_prompt += f"""
        
CASE CONTEXT:
Title: {case_context['title']}
Context: {case_context['context']}
Focus Areas: {', '.join(case_context.get('focus_areas', []))}

Extract insights that are:
1. Directly supported by text (cite excerpts)
2. Relevant to the case context above
3. Factual observations, not speculation

Do NOT infer causation without explicit evidence.
"""
    
    # ... rest of prompt
```

---

## API Endpoints (New)

### Case Management
```
POST   /api/cases                    - Create new case
GET    /api/cases                    - List all cases (with filters)
GET    /api/cases/<id>               - Get case details
PATCH  /api/cases/<id>               - Update case (title, context, status)
DELETE /api/cases/<id>               - Delete case (cascade)

GET    /api/cases/<id>/documents     - List documents in case
GET    /api/cases/<id>/findings      - List findings (with status filters)
GET    /api/cases/<id>/patterns      - List patterns for case
GET    /api/cases/<id>/timeline      - Get timeline events
POST   /api/cases/<id>/timeline      - Add human annotation to timeline
GET    /api/cases/<id>/stats         - Statistics (doc count, findings, etc)
```

### Findings Management
```
POST   /api/findings                 - Promote insight to finding
PATCH  /api/findings/<id>            - Update status (verified/rejected)
DELETE /api/findings/<id>            - Remove finding
POST   /api/findings/<id>/note       - Add user annotation
```

### Modified Endpoints
```
POST /api/upload
  - Add optional case_id parameter
  - Store case_id in preflight_sessions

POST /api/preflight/<id>/confirm
  - If session has case_id, inject case context into extraction
  - Auto-create timeline event: "doc_added"

POST /api/extract
  - Add optional case_id parameter
  - If provided, inject case context into prompts
```

---

## User Flow (End to End)

### Day 1: Create Case & Add Initial Documents
```
1. User clicks "New Case"
2. Form:
   - Title: "Q3 Sales Investigation"
   - Context: "Revenue dropped 15%, need root cause"
   - Focus areas: pricing, competition, market
3. System creates case
4. User uploads 3 documents
5. Preflight review (existing flow)
6. Confirm → Process WITH case context injected
7. System extracts insights → Auto-promote high-confidence to Findings
8. Timeline: "Case created, 3 docs added, 24 findings extracted"
```

### Day 5: Add More Documents
```
1. User opens existing case
2. "Add Documents" button → Upload flow
3. New docs processed WITH original case context
4. System cross-references new insights against existing findings
5. Timeline: "Jan 10: customer_survey.xlsx added, 8 new findings"
```

### Day 7: Review & Verify Findings
```
1. User views Findings page (filtered by case)
2. Reviews findings with source citations
3. Marks some as "verified" (checkbox)
4. Flags others as "needs verification"
5. Adds annotations: "This contradicts Finding #12"
```

---

## Implementation Order

### Session 1-2: Backend Schema ← START HERE
1. Create migration script for 4 new tables
2. Add case_id FK to insights, patterns, preflight_sessions
3. Write CaseStore class (similar to InsightStore)
4. Write FindingsStore class
5. Write TimelineStore class

### Session 3-4: API Endpoints
1. Implement case CRUD endpoints
2. Implement findings endpoints
3. Modify upload/preflight/extract to accept case_id
4. Add context injection to extraction prompts
5. Auto-generate timeline events

### Session 5-6: UI Foundation
1. Cases dashboard page (list, create)
2. Case detail page (manifest, docs, findings count)
3. Case creation modal
4. Wire preflight → case flow
5. Update navigation

### Session 7-8: Polish
1. Timeline visualization
2. Findings page with status filters
3. Status badges/indicators
4. Context injection testing
5. Verification workflow

---

## Files to Reference

**Read these first for context:**
- `C:\EhkoVaults\ReCog\README.md` - Current system overview
- `C:\EhkoVaults\ReCog\_docs\ROADMAP.md` - Development phases
- `C:\EhkoVaults\ReCog\RECOG_INSTRUCTIONS.md` - Claude operating instructions

**Backend files to modify:**
- `C:\EhkoVaults\ReCog\_scripts\db.py` - Database utilities
- `C:\EhkoVaults\ReCog\_scripts\recog_engine\insight_store.py` - Model for CaseStore
- `C:\EhkoVaults\ReCog\_scripts\recog_engine\extraction.py` - Context injection point
- `C:\EhkoVaults\ReCog\_scripts\server.py` - Add new endpoints

**Frontend files (later):**
- `C:\EhkoVaults\ReCog\_ui\src\lib\api.js` - API client
- `C:\EhkoVaults\ReCog\_ui\src\components\pages\` - Page components

---

## Current System State

**Backend (Flask Server):**
- ✅ Running at localhost:5100
- ✅ 15+ database tables
- ✅ Complete processing pipeline (Tier 0-3)
- ✅ Entity graph, synthesis, critique layers
- ✅ Preflight workflow
- ✅ Multi-provider LLM (OpenAI, Anthropic)

**Frontend (React UI):**
- ✅ Located at `C:\EhkoVaults\ReCog\_ui`
- ✅ 6 pages (Signal, Upload, Preflight, Entities, Insights, Patterns)
- ✅ shadcn/ui component library
- ✅ Holographic theme
- ⚠️ Needs Case-centric redesign

**Database:**
- ✅ SQLite at `C:\EhkoVaults\ReCog\_data\recog.db`
- ⚠️ Needs 4 new tables + FK additions

---

## Key Constraints

1. **Repository Separation:** ReCog backend is in `C:\EhkoVaults\ReCog`, UI is in `C:\EhkoVaults\ReCog\_ui`
2. **AGPLv3 licensed** - open source
3. **Port allocation:** Backend=5100, Frontend=3100
4. **No breaking changes** to existing extraction/synthesis logic - extend, don't replace

---

## Success Criteria (Phase 1)

User can:
- ✅ Create a case with context and focus areas
- ✅ Upload documents to that case
- ✅ See findings extracted with case context applied
- ✅ Mark findings as verified/needs verification
- ✅ View timeline of case evolution
- ✅ Filter findings by status
- ✅ Add documents days/weeks later with context preserved

System can:
- ✅ Inject case context into extraction prompts
- ✅ Auto-promote high-confidence insights to findings
- ✅ Cross-reference new findings against existing
- ✅ Generate timeline events automatically
- ✅ Maintain referential integrity (cascading deletes)

---

## What Claude Code Should Do

**Immediate actions:**
1. Read this brief and RECOG_INSTRUCTIONS.md
2. Review existing database schema (`db.py`, `insight_store.py`)
3. Create migration script for new tables
4. Implement CaseStore class
5. Implement FindingsStore class
6. Implement TimelineStore class
7. Add case endpoints to server.py
8. Test with the server

**Don't do yet:**
- ❌ UI changes (backend first)
- ❌ Chat interface
- ❌ Export functionality
- ❌ Pattern modifications (comes after findings work)

---

**Start with:** Create migration script + CaseStore implementation

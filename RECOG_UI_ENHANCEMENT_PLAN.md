# ReCog UI Enhancement Plan - Session Brief for Claude Code CLI

**Date:** 2026-01-06  
**Context:** Add virtualization, document viewing, and analytics foundation  
**Status:** Ready for implementation  
**Target:** `C:\EhkoVaults\ReCog\_ui\`

---

## What We're Building

Add three critical UI enhancements to ReCog:
1. **React Virtuoso** - High-performance list rendering for 1000+ items
2. **CodeMirror** - Professional document text viewer with syntax highlighting
3. **Recharts Foundation** - Prepare analytics dashboard structure

---

## Current State

### ✅ Completed (Backend)
- Case Architecture implemented
- Cases, Findings, Timeline stores operational
- API endpoints functional
- Database fully migrated

### 📊 Current UI Stack
```json
{
  "framework": "React 18.3.1 + Vite",
  "components": "shadcn/ui (Radix UI primitives)",
  "styling": "Tailwind CSS + tailwindcss-animate",
  "icons": "Lucide React",
  "theme": "Terminal/Holographic (deep void bg, orange/blue accents)"
}
```

### 📁 Current Pages (8)
```
src/components/pages/
├── CasesPage.jsx          ← VIRTUALIZE (grid → list)
├── InsightsPage.jsx       ← VIRTUALIZE (cards)
├── EntitiesPage.jsx       ← VIRTUALIZE (table → list)
├── PatternsPage.jsx       ← VIRTUALIZE (cards)
├── PreflightPage.jsx      ← VIRTUALIZE (review items)
├── UploadPage.jsx         ← No change
├── SignalExtraction.jsx   ← No change
└── (CaseDetail inline)    ← VIRTUALIZE findings/timeline
```

### ⚠️ Problems to Solve
1. **Performance:** Lists with 100+ items cause scroll jank
2. **Reference:** No way to view original document text for citations
3. **Analytics:** No visual dashboard for case metrics

---

## Architecture Decisions (Locked In)

### 1. **Virtualization Strategy**
- ✅ Use **React Virtuoso** (not react-window/TanStack)
  - **Why:** Handles variable-height items automatically
  - **Size:** 15kb (minimal impact)
  - **Pattern:** Wrap existing Card components (no refactor needed)

### 2. **Document Viewing Strategy**
- ✅ Use **CodeMirror 6** (not Lexical)
  - **Why:** Read-only display, syntax highlighting, line numbers
  - **Size:** ~50kb with extensions
  - **Pattern:** New `DocumentViewerPage.jsx` + modal viewer

### 3. **Analytics Strategy**
- ✅ Use **Recharts** (already familiar from Claude artifacts)
  - **Size:** ~80kb
  - **Pattern:** New `DashboardPage.jsx` (Phase 2)

### 4. **Data Fetching Strategy**
**Document Text Retrieval:**
- Currently: No endpoint exists to fetch document text
- **Solution:** Add `/api/documents/:doc_id/text` endpoint on backend
- **Fallback:** If document not found, show metadata only

---

## Implementation Order

### **Phase 1: React Virtuoso (Priority 1) - 2-3 hours**
Virtualize all lists for immediate performance gain.

### **Phase 2: Document Backend (Priority 2) - 1 hour**
Add document text retrieval endpoint.

### **Phase 3: CodeMirror Viewer (Priority 3) - 2 hours**
Implement document viewing UI.

### **Phase 4: Recharts Foundation (Priority 4) - 1 hour**
Prep dashboard structure (charts in later session).

---

# PHASE 1: React Virtuoso Implementation

## 1.1 Install Dependencies

```bash
cd C:\EhkoVaults\ReCog\_ui
npm install react-virtuoso
```

**Expected changes:**
- `package.json` - adds `react-virtuoso: ^4.7.1`
- `package-lock.json` - updates

---

## 1.2 Create Virtualization Utilities

**File:** `src/lib/virtualization.js` (NEW)

```javascript
/**
 * Virtualization utilities for ReCog UI
 * 
 * Consistent configs for Virtuoso across all pages
 */

// Standard viewport overscan (pre-render buffer)
export const VIRTUOSO_CONFIG = {
  // How much extra to render above/below viewport
  increaseViewportBy: { top: 200, bottom: 200 },
  
  // Enable smooth scroll behavior
  scrollBehavior: 'smooth',
}

// For grouped lists (timeline with date headers)
export const GROUPED_VIRTUOSO_CONFIG = {
  ...VIRTUOSO_CONFIG,
  
  // Keep headers sticky
  groupHeaderHeight: 48,
}

// Scroll restoration helper
export function saveScrollPosition(key, position) {
  sessionStorage.setItem(`scroll_${key}`, JSON.stringify(position))
}

export function loadScrollPosition(key) {
  const saved = sessionStorage.getItem(`scroll_${key}`)
  return saved ? JSON.parse(saved) : null
}
```

---

## 1.3 Update CasesPage.jsx

**Current:** Grid layout with `.map()`  
**New:** Virtuoso with responsive grid

**File:** `src/components/pages/CasesPage.jsx`

### Changes:

1. **Import Virtuoso**
```javascript
import { Virtuoso } from 'react-virtuoso'
import { VIRTUOSO_CONFIG } from '../../lib/virtualization'
```

2. **Replace Grid Rendering**

**BEFORE:**
```javascript
{!loading && cases.length > 0 && (
  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
    {cases.map((c) => (
      <CaseCard
        key={c.id}
        caseData={c}
        onSelect={setSelectedCase}
        onDelete={handleDeleteCase}
      />
    ))}
  </div>
)}
```

**AFTER:**
```javascript
{!loading && cases.length > 0 && (
  <div style={{ height: 'calc(100vh - 280px)' }}>
    <Virtuoso
      data={cases}
      {...VIRTUOSO_CONFIG}
      itemContent={(index, caseData) => (
        <div className="pb-4">
          <CaseCard
            caseData={caseData}
            onSelect={setSelectedCase}
            onDelete={handleDeleteCase}
          />
        </div>
      )}
      components={{
        List: React.forwardRef((props, ref) => (
          <div 
            ref={ref} 
            {...props} 
            className="space-y-4"
          />
        )),
      }}
    />
  </div>
)}
```

**Notes:**
- Virtuoso requires explicit height
- Grid → vertical list (easier to virtualize)
- Keep existing CaseCard component unchanged

---

## 1.4 Update InsightsPage.jsx

**Current:** Cards with `.map()`  
**New:** Virtuoso list

**File:** `src/components/pages/InsightsPage.jsx`

### Changes:

1. **Import Virtuoso**
```javascript
import { Virtuoso } from 'react-virtuoso'
import { VIRTUOSO_CONFIG } from '../../lib/virtualization'
```

2. **Replace Insights Rendering**

**Find this section (~line 250):**
```javascript
<div className="space-y-3">
  {insights.map((insight) => {
    // ... existing card rendering
  })}
</div>
```

**Replace with:**
```javascript
<div style={{ height: 'calc(100vh - 320px)' }}>
  <Virtuoso
    data={insights}
    {...VIRTUOSO_CONFIG}
    itemContent={(index, insight) => {
      const sigBadge = getSignificanceBadge(insight.significance_score)
      const finding = findings[insight.id]
      const isPromoting = promoting[insight.id]
      
      return (
        <div className="pb-3">
          <Card 
            className={`
              hover:bg-muted/30 transition-colors
              ${finding ? 'border-[#5fb3a1]/50 bg-[#5fb3a1]/5' : ''}
            `}
          >
            <CardContent className="pt-6">
              {/* KEEP EXISTING CARD CONTENT - just indent it here */}
              <div className="flex items-start gap-4">
                {/* ... existing insight card content ... */}
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }}
  />
</div>
```

**Notes:**
- Move all card rendering logic inside `itemContent`
- Keep all existing UI/logic (badges, promote button, etc.)
- Only change the outer mapping structure

---

## 1.5 Update EntitiesPage.jsx

**Current:** Table rows with `.map()`  
**New:** Virtuoso table (using TableVirtuoso)

**File:** `src/components/pages/EntitiesPage.jsx`

### Changes:

1. **Import TableVirtuoso**
```javascript
import { TableVirtuoso } from 'react-virtuoso'
import { VIRTUOSO_CONFIG } from '../../lib/virtualization'
```

2. **Find existing table rendering** (search for `<table>` or entity mapping)

3. **Replace with TableVirtuoso**

```javascript
<div style={{ height: 'calc(100vh - 280px)' }}>
  <TableVirtuoso
    data={entities}
    {...VIRTUOSO_CONFIG}
    components={{
      Table: (props) => (
        <table 
          {...props} 
          className="w-full border-collapse"
        />
      ),
      TableHead: React.forwardRef((props, ref) => (
        <thead 
          ref={ref} 
          {...props}
          className="bg-card border-b border-border sticky top-0 z-10"
        />
      )),
      TableRow: (props) => (
        <tr 
          {...props}
          className="border-b border-border hover:bg-muted/30 transition-colors"
        />
      ),
    }}
    fixedHeaderContent={() => (
      <tr>
        <th className="text-left p-3 text-sm font-medium text-muted-foreground">Entity</th>
        <th className="text-left p-3 text-sm font-medium text-muted-foreground">Type</th>
        <th className="text-left p-3 text-sm font-medium text-muted-foreground">Count</th>
        <th className="text-left p-3 text-sm font-medium text-muted-foreground">Status</th>
        <th className="text-right p-3 text-sm font-medium text-muted-foreground">Actions</th>
      </tr>
    )}
    itemContent={(index, entity) => (
      <>
        <td className="p-3 text-sm font-medium">{entity.text}</td>
        <td className="p-3 text-sm">
          <Badge variant="outline">{entity.type}</Badge>
        </td>
        <td className="p-3 text-sm text-muted-foreground">{entity.mention_count}</td>
        <td className="p-3 text-sm">
          <StatusBadge status={entity.status} />
        </td>
        <td className="p-3 text-sm text-right">
          {/* Existing action buttons */}
        </td>
      </>
    )}
  />
</div>
```

**Notes:**
- TableVirtuoso handles sticky headers automatically
- Keep existing cell content/actions
- Table must have explicit height

---

## 1.6 Update PatternsPage.jsx

**Current:** Pattern cards with `.map()`  
**New:** Virtuoso list

**File:** `src/components/pages/PatternsPage.jsx`

### Changes:

Same pattern as InsightsPage - wrap existing pattern cards in Virtuoso.

```javascript
import { Virtuoso } from 'react-virtuoso'
import { VIRTUOSO_CONFIG } from '../../lib/virtualization'

// In render, replace:
// patterns.map((pattern) => <PatternCard ... />)

// With:
<div style={{ height: 'calc(100vh - 280px)' }}>
  <Virtuoso
    data={patterns}
    {...VIRTUOSO_CONFIG}
    itemContent={(index, pattern) => (
      <div className="pb-4">
        {/* Existing PatternCard component */}
      </div>
    )}
  />
</div>
```

---

## 1.7 Update PreflightPage.jsx

**Current:** Review items with `.map()`  
**New:** Virtuoso with checkboxes

**File:** `src/components/pages/PreflightPage.jsx`

### Changes:

```javascript
import { Virtuoso } from 'react-virtuoso'
import { VIRTUOSO_CONFIG } from '../../lib/virtualization'

// Replace items rendering:
<div style={{ height: 'calc(100vh - 320px)' }}>
  <Virtuoso
    data={items}
    {...VIRTUOSO_CONFIG}
    itemContent={(index, item) => (
      <div className="pb-2">
        {/* Existing item card with checkbox */}
      </div>
    )}
  />
</div>
```

**Special consideration:** Maintain checkbox state during virtualization.

---

## 1.8 Add Case Detail Virtualization

**Location:** Inside `CasesPage.jsx` - the `<CaseDetail>` component

### Two lists to virtualize:

#### A. Findings List
```javascript
// In CaseDetail component, replace findings.map() with:

<Virtuoso
  data={findings}
  {...VIRTUOSO_CONFIG}
  itemContent={(index, finding) => (
    <div className="pb-3">
      {/* Existing FindingCard */}
    </div>
  )}
/>
```

#### B. Timeline (Grouped by Date)
```javascript
import { GroupedVirtuoso } from 'react-virtuoso'
import { GROUPED_VIRTUOSO_CONFIG } from '../../lib/virtualization'

// Group timeline events by date first:
const groupedTimeline = groupEventsByDate(timelineEvents)

<GroupedVirtuoso
  groupCounts={groupedTimeline.map(g => g.events.length)}
  {...GROUPED_VIRTUOSO_CONFIG}
  groupContent={(index) => {
    const group = groupedTimeline[index]
    return (
      <div className="sticky top-0 bg-background/95 backdrop-blur-sm py-2 px-4 border-b border-border z-10">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Clock className="w-4 h-4" />
          {group.date}
        </div>
      </div>
    )
  }}
  itemContent={(index) => {
    const event = groupedTimeline.flatMap(g => g.events)[index]
    return (
      <div className="py-2 px-4">
        {/* Existing timeline event card */}
      </div>
    )
  }}
/>
```

**Helper function to add:**
```javascript
function groupEventsByDate(events) {
  const groups = {}
  events.forEach(event => {
    const date = new Date(event.timestamp).toLocaleDateString()
    if (!groups[date]) {
      groups[date] = { date, events: [] }
    }
    groups[date].events.push(event)
  })
  return Object.values(groups)
}
```

---

## 1.9 Testing Checklist for Phase 1

After implementing all Virtuoso changes:

```bash
# 1. Start dev server
npm run dev

# 2. Test each page:
```

**Cases Page:**
- [ ] Create 50+ mock cases (use browser console)
- [ ] Scroll smoothly through list
- [ ] Click case → detail view loads
- [ ] Delete case → list updates

**Insights Page:**
- [ ] Filter by status (should maintain scroll)
- [ ] Promote insight → finding badge appears
- [ ] Search/filter updates list without scroll jump

**Entities Page:**
- [ ] Sticky header stays visible during scroll
- [ ] Click entity → actions work
- [ ] Sorting maintains virtualization

**Patterns Page:**
- [ ] Pattern cards render correctly
- [ ] Variable heights handled automatically

**Preflight Page:**
- [ ] Checkboxes maintain state during scroll
- [ ] Exclude/include items work
- [ ] Confirm button processes correctly

**Case Detail:**
- [ ] Findings list scrolls smoothly
- [ ] Timeline grouped headers stay sticky
- [ ] Add finding → list updates

---

## Phase 1 Complete Criteria

✅ All list pages use Virtuoso  
✅ Scroll performance with 500+ items  
✅ Existing functionality preserved  
✅ No visual regressions  
✅ Bundle size <200kb total  

---

# PHASE 2: Document Text Endpoint (Backend)

## 2.1 Problem Statement

**Current state:** Users see insights/findings but can't reference original document text.

**Needed:** API endpoint to fetch document text for citation verification.

---

## 2.2 Backend Implementation

**File:** `C:\EhkoVaults\ReCog\_scripts\server.py`

### Add new endpoint:

```python
@app.route('/api/documents/<doc_id>/text', methods=['GET'])
@handle_errors
def get_document_text(doc_id):
    """
    Get the original text of an uploaded document.
    
    For uploaded files, retrieves text from:
    - Preflight sessions (recently uploaded)
    - Processed documents (stored text)
    - Original files (fallback)
    
    Returns:
        {
            "document_id": str,
            "filename": str,
            "text": str,
            "format": str,  # "txt", "markdown", "json", etc.
            "line_count": int,
            "char_count": int
        }
    """
    # Check preflight session first (most recent uploads)
    session = preflight_manager.get_session_by_doc_id(doc_id)
    
    if session:
        # Document is in preflight - return raw text
        doc_data = session.get('document_data', {})
        return jsonify({
            "document_id": doc_id,
            "filename": doc_data.get('filename', 'unknown'),
            "text": doc_data.get('raw_text', ''),
            "format": doc_data.get('format', 'txt'),
            "line_count": doc_data.get('raw_text', '').count('\n') + 1,
            "char_count": len(doc_data.get('raw_text', ''))
        })
    
    # Check processed documents in database
    conn = sqlite3.connect(str(app.config['DB_PATH']))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT filename, raw_text, format 
        FROM documents 
        WHERE id = ?
    """, (doc_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        filename, raw_text, format_type = row
        return jsonify({
            "document_id": doc_id,
            "filename": filename,
            "text": raw_text or '',
            "format": format_type or 'txt',
            "line_count": (raw_text or '').count('\n') + 1,
            "char_count": len(raw_text or '')
        })
    
    # Document not found
    return jsonify({
        "error": "Document not found",
        "document_id": doc_id
    }), 404
```

### Add to PreflightManager (if needed):

**File:** `C:\EhkoVaults\ReCog\_scripts\recog_engine\preflight.py`

```python
def get_session_by_doc_id(self, doc_id: str) -> Optional[dict]:
    """Find preflight session containing a specific document ID."""
    conn = sqlite3.connect(str(self.db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT session_id, document_data 
        FROM preflight_sessions 
        WHERE document_id = ?
    """, (doc_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        session_id, doc_data_json = row
        return {
            "session_id": session_id,
            "document_data": json.loads(doc_data_json) if doc_data_json else {}
        }
    
    return None
```

---

## 2.3 Frontend API Client

**File:** `src/lib/api.js`

Add new function:

```javascript
// Document Text Retrieval
export async function getDocumentText(documentId) {
  return fetchAPI(`/documents/${documentId}/text`)
}
```

---

## 2.4 Testing Backend

```bash
# Start ReCog server
python C:\EhkoVaults\ReCog\_scripts\server.py

# Test endpoint (use actual doc ID from your DB)
curl http://localhost:5100/api/documents/abc123/text
```

**Expected response:**
```json
{
  "document_id": "abc123",
  "filename": "report.txt",
  "text": "This is the document content...",
  "format": "txt",
  "line_count": 42,
  "char_count": 1337
}
```

---

## Phase 2 Complete Criteria

✅ Backend endpoint returns document text  
✅ Handles missing documents gracefully  
✅ Frontend API client updated  
✅ Tested with real document IDs  

---

# PHASE 3: CodeMirror Document Viewer

## 3.1 Install Dependencies

```bash
cd C:\EhkoVaults\ReCog\_ui
npm install codemirror @codemirror/view @codemirror/state @codemirror/lang-markdown @codemirror/lang-javascript @codemirror/lang-json @codemirror/search
```

---

## 3.2 Create DocumentViewer Component

**File:** `src/components/ui/document-viewer.jsx` (NEW)

```javascript
import React, { useEffect, useRef } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import { EditorState } from '@codemirror/state'
import { markdown } from '@codemirror/lang-markdown'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { search, highlightSelectionMatches } from '@codemirror/search'

// ReCog terminal theme
const recogTheme = EditorView.theme({
  "&": {
    backgroundColor: "#0a0e1a",
    color: "#e6e8eb",
    height: "100%",
  },
  ".cm-content": {
    caretColor: "#ff6b35",
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    fontSize: "13px",
    lineHeight: "1.6",
  },
  ".cm-gutters": {
    backgroundColor: "#0f1420",
    color: "#6b7280",
    border: "none",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "#1a1f2e",
    color: "#ff6b35",
  },
  ".cm-activeLine": {
    backgroundColor: "#1a1f2e44",
  },
  ".cm-selectionBackground": {
    backgroundColor: "#5fb3a144 !important",
  },
  ".cm-searchMatch": {
    backgroundColor: "#ff6b3544",
    outline: "1px solid #ff6b35",
  },
  ".cm-searchMatch-selected": {
    backgroundColor: "#ff6b3588",
  },
  "&.cm-focused .cm-cursor": {
    borderLeftColor: "#ff6b35",
  },
})

const languageMap = {
  'txt': [],
  'md': [markdown()],
  'markdown': [markdown()],
  'js': [javascript()],
  'javascript': [javascript()],
  'json': [json()],
  'jsx': [javascript({ jsx: true })],
}

export function DocumentViewer({ text, format = 'txt', filename = '', highlights = [] }) {
  const editorRef = useRef(null)
  const viewRef = useRef(null)

  useEffect(() => {
    if (!editorRef.current) return

    // Get language extensions
    const langExtensions = languageMap[format] || []

    // Create editor state
    const state = EditorState.create({
      doc: text,
      extensions: [
        basicSetup,
        recogTheme,
        EditorView.editable.of(false), // Read-only
        EditorView.lineWrapping,
        search({ top: true }),
        highlightSelectionMatches(),
        ...langExtensions,
      ],
    })

    // Create editor view
    const view = new EditorView({
      state,
      parent: editorRef.current,
    })

    viewRef.current = view

    // Apply highlights if provided
    if (highlights.length > 0) {
      applyHighlights(view, highlights)
    }

    // Cleanup
    return () => {
      view.destroy()
    }
  }, [text, format, highlights])

  return (
    <div className="h-full w-full border border-border rounded-md overflow-hidden">
      <div ref={editorRef} className="h-full" />
    </div>
  )
}

function applyHighlights(view, highlights) {
  // TODO: Implement highlight decoration
  // highlights = [{ from: number, to: number, class: string }]
}
```

---

## 3.3 Create DocumentViewerPage

**File:** `src/components/pages/DocumentViewerPage.jsx` (NEW)

```javascript
import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { 
  FileText, 
  Download, 
  Search, 
  Copy, 
  Check,
  ArrowLeft,
  Loader2 
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DocumentViewer } from '@/components/ui/document-viewer'
import { LoadingState } from '@/components/ui/loading-state'
import { getDocumentText } from '@/lib/api'

export function DocumentViewerPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const documentId = searchParams.get('id')
  
  const [document, setDocument] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (documentId) {
      loadDocument()
    }
  }, [documentId])

  async function loadDocument() {
    setLoading(true)
    setError(null)
    try {
      const data = await getDocumentText(documentId)
      setDocument(data.data || data)
    } catch (err) {
      setError(err.message || 'Failed to load document')
    } finally {
      setLoading(false)
    }
  }

  async function handleCopy() {
    if (document?.text) {
      await navigator.clipboard.writeText(document.text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  function handleDownload() {
    if (!document?.text) return
    
    const blob = new Blob([document.text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = window.document.createElement('a')
    a.href = url
    a.download = document.filename || 'document.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return <LoadingState message="Loading document..." size="lg" />
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <FileText className="w-16 h-16 text-muted-foreground" />
        <div className="text-center">
          <h3 className="text-lg font-semibold text-foreground mb-2">Document Not Found</h3>
          <p className="text-sm text-muted-foreground mb-4">{error}</p>
          <Button onClick={() => navigate(-1)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Go Back
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card/50">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-2 hover:bg-muted rounded-md transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              {document?.filename || 'Document'}
            </h2>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span>{document?.line_count || 0} lines</span>
              <span>•</span>
              <span>{document?.char_count || 0} characters</span>
              <span>•</span>
              <span className="px-1.5 py-0.5 bg-orange-mid/10 text-orange-light rounded border border-orange-mid/20">
                {document?.format || 'txt'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 w-64"
            />
          </div>

          {/* Copy */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            disabled={copied}
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 mr-2" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 mr-2" />
                Copy
              </>
            )}
          </Button>

          {/* Download */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownload}
          >
            <Download className="w-4 h-4 mr-2" />
            Download
          </Button>
        </div>
      </div>

      {/* Document Viewer */}
      <div className="flex-1 p-4">
        <DocumentViewer
          text={document?.text || ''}
          format={document?.format || 'txt'}
          filename={document?.filename || ''}
        />
      </div>
    </div>
  )
}
```

---

## 3.4 Add Document Viewer Modal

**File:** `src/components/ui/document-viewer-modal.jsx` (NEW)

For inline viewing within Findings/Insights pages:

```javascript
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DocumentViewer } from './document-viewer'
import { Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getDocumentText } from '@/lib/api'

export function DocumentViewerModal({ documentId, isOpen, onClose, highlightText = null }) {
  const [document, setDocument] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isOpen && documentId) {
      loadDocument()
    }
  }, [isOpen, documentId])

  async function loadDocument() {
    setLoading(true)
    try {
      const data = await getDocumentText(documentId)
      setDocument(data.data || data)
    } catch (err) {
      console.error('Failed to load document:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl h-[80vh]">
        <DialogHeader>
          <DialogTitle>{document?.filename || 'Document'}</DialogTitle>
        </DialogHeader>
        
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : document ? (
          <div className="flex-1 overflow-hidden">
            <DocumentViewer
              text={document.text}
              format={document.format}
              filename={document.filename}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            Failed to load document
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
```

---

## 3.5 Integrate into Findings/Insights

**In `InsightsPage.jsx` and `FindingsPage` (within CaseDetail):**

Add "View Source" button to each card:

```javascript
import { DocumentViewerModal } from '@/components/ui/document-viewer-modal'

// In component state:
const [viewingDoc, setViewingDoc] = useState(null)

// In insight/finding card, add button:
<Button
  variant="ghost"
  size="sm"
  onClick={() => setViewingDoc(insight.document_id)}
>
  <FileText className="w-4 h-4 mr-2" />
  View Source
</Button>

// At bottom of component:
<DocumentViewerModal
  documentId={viewingDoc}
  isOpen={!!viewingDoc}
  onClose={() => setViewingDoc(null)}
  highlightText={insight.excerpt}
/>
```

---

## 3.6 Update App Routing

**File:** `src/App.jsx`

Add route for standalone document viewer:

```javascript
import { DocumentViewerPage } from './components/pages/DocumentViewerPage'

// In routes:
<Route path="/documents" element={<DocumentViewerPage />} />
```

---

## Phase 3 Complete Criteria

✅ Document viewer displays text with syntax highlighting  
✅ Search within document works  
✅ Copy/download functions work  
✅ Modal viewer opens from Findings/Insights  
✅ Line numbers and gutters visible  
✅ Terminal theme matches ReCog aesthetic  

---

# PHASE 4: Recharts Foundation

## 4.1 Install Dependencies

```bash
cd C:\EhkoVaults\ReCog\_ui
npm install recharts
```

---

## 4.2 Create Dashboard Structure

**File:** `src/components/pages/DashboardPage.jsx` (NEW)

```javascript
import { useState, useEffect } from 'react'
import { BarChart, LineChart, PieChart } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { StatCard, StatGrid } from '@/components/ui/stat-card'
import { LoadingState } from '@/components/ui/loading-state'

export function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    loadDashboardData()
  }, [])

  async function loadDashboardData() {
    setLoading(true)
    try {
      // TODO: Fetch aggregate stats across all cases
      // const data = await getCaseStats()
      
      // Mock data for now
      setStats({
        totalCases: 12,
        activeCases: 8,
        totalDocuments: 156,
        totalFindings: 342,
        verifiedFindings: 245,
        pendingFindings: 89,
        rejectedFindings: 8,
      })
    } catch (err) {
      console.error('Failed to load dashboard:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <LoadingState message="Loading dashboard..." size="lg" />
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-foreground">Dashboard</h2>
        <p className="text-muted-foreground">Overview of your document intelligence operations</p>
      </div>

      {/* Stats Grid */}
      <StatGrid>
        <StatCard
          title="Total Cases"
          value={stats.totalCases}
          icon={BarChart}
          trend={{ value: 12, isPositive: true }}
        />
        <StatCard
          title="Active Cases"
          value={stats.activeCases}
          icon={LineChart}
        />
        <StatCard
          title="Documents Processed"
          value={stats.totalDocuments}
          icon={PieChart}
          trend={{ value: 8, isPositive: true }}
        />
        <StatCard
          title="Verified Findings"
          value={stats.verifiedFindings}
          icon={PieChart}
        />
      </StatGrid>

      {/* Chart Placeholders */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Processing Activity</CardTitle>
            <CardDescription>Documents processed over time</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64 flex items-center justify-center border border-dashed border-border rounded-md">
              <p className="text-sm text-muted-foreground">
                Line chart coming soon (Recharts)
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Finding Status Distribution</CardTitle>
            <CardDescription>Breakdown by verification status</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64 flex items-center justify-center border border-dashed border-border rounded-md">
              <p className="text-sm text-muted-foreground">
                Pie chart coming soon (Recharts)
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Case Activity Table */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Case Activity</CardTitle>
          <CardDescription>Latest updates across active cases</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-64 flex items-center justify-center border border-dashed border-border rounded-md">
            <p className="text-sm text-muted-foreground">
              Activity timeline coming soon
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## 4.3 Add Dashboard Route

**File:** `src/App.jsx`

```javascript
import { DashboardPage } from './components/pages/DashboardPage'

// In routes (add as first item):
<Route path="/" element={<DashboardPage />} />
<Route path="/dashboard" element={<DashboardPage />} />
```

---

## 4.4 Update Navigation

**File:** `src/App.jsx`

Update navigation links to include Dashboard:

```javascript
const navigation = [
  { name: 'Dashboard', path: '/', icon: BarChart },
  { name: 'Cases', path: '/cases', icon: FolderOpen },
  { name: 'Insights', path: '/insights', icon: Lightbulb },
  // ... rest of nav
]
```

---

## 4.5 Create Chart Components (Stubs)

**File:** `src/components/charts/ActivityChart.jsx` (NEW)

```javascript
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export function ActivityChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <XAxis 
          dataKey="date" 
          stroke="#6b7280"
          style={{ fontSize: '12px' }}
        />
        <YAxis 
          stroke="#6b7280"
          style={{ fontSize: '12px' }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#0f1420',
            border: '1px solid #1e293b',
            borderRadius: '6px',
          }}
          labelStyle={{ color: '#e6e8eb' }}
        />
        <Line 
          type="monotone" 
          dataKey="findings" 
          stroke="#ff6b35" 
          strokeWidth={2}
        />
        <Line 
          type="monotone" 
          dataKey="documents" 
          stroke="#5fb3a1" 
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

**File:** `src/components/charts/FindingsDistribution.jsx` (NEW)

```javascript
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'

const COLORS = {
  verified: '#5fb3a1',
  pending: '#ff6b35',
  rejected: '#ef4444',
}

export function FindingsDistribution({ data }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          outerRadius={80}
          fill="#8884d8"
          dataKey="value"
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[entry.status]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: '#0f1420',
            border: '1px solid #1e293b',
            borderRadius: '6px',
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: '12px' }}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
```

---

## Phase 4 Complete Criteria

✅ Dashboard page structure created  
✅ Recharts installed and imported  
✅ Chart component stubs ready  
✅ Navigation includes Dashboard  
✅ Placeholder charts render  

**Note:** Actual chart implementations will be done in a separate polishing session after Phase 1-3 are complete and tested.

---

# Implementation Execution Plan for Claude Code CLI

## Session 1: Virtualization (2-3 hours)

```bash
# Commands to run:
cd C:\EhkoVaults\ReCog\_ui

# 1. Install Virtuoso
npm install react-virtuoso

# 2. Create utilities file
# Create src/lib/virtualization.js with configs

# 3. Update each page component:
# - CasesPage.jsx
# - InsightsPage.jsx
# - EntitiesPage.jsx
# - PatternsPage.jsx
# - PreflightPage.jsx
# - Case detail views (findings, timeline)

# 4. Test
npm run dev
# Manually test each page
```

---

## Session 2: Document Backend (30-60 min)

```bash
# Backend changes:
cd C:\EhkoVaults\ReCog\_scripts

# 1. Add endpoint to server.py
# Add /api/documents/<doc_id>/text route

# 2. Update PreflightManager if needed
# Add get_session_by_doc_id method

# 3. Test backend
python server.py
# curl test the endpoint

# 4. Update frontend API
cd C:\EhkoVaults\ReCog\_ui\src\lib
# Add getDocumentText() to api.js
```

---

## Session 3: CodeMirror Viewer (2 hours)

```bash
cd C:\EhkoVaults\ReCog\_ui

# 1. Install CodeMirror
npm install codemirror @codemirror/view @codemirror/state @codemirror/lang-markdown @codemirror/lang-javascript @codemirror/lang-json @codemirror/search

# 2. Create components:
# - src/components/ui/document-viewer.jsx
# - src/components/ui/document-viewer-modal.jsx
# - src/components/pages/DocumentViewerPage.jsx

# 3. Update existing pages:
# - InsightsPage.jsx (add "View Source" button)
# - CaseDetail findings (add "View Source" button)

# 4. Update routing
# Add /documents route to App.jsx

# 5. Test
npm run dev
```

---

## Session 4: Recharts Foundation (1 hour)

```bash
cd C:\EhkoVaults\ReCog\_ui

# 1. Install Recharts
npm install recharts

# 2. Create components:
# - src/components/pages/DashboardPage.jsx
# - src/components/charts/ActivityChart.jsx
# - src/components/charts/FindingsDistribution.jsx

# 3. Update routing & navigation
# Add Dashboard to App.jsx routes and nav

# 4. Test
npm run dev
# Verify dashboard page loads with placeholders
```

---

# Testing Strategy

## Automated Tests (Optional - Future Work)

```javascript
// tests/virtualization.test.jsx
describe('Virtuoso Lists', () => {
  it('renders 1000 items without lag', () => {
    // Performance test
  })
  
  it('maintains scroll position on filter', () => {
    // State management test
  })
})
```

## Manual Testing Checklist

### Phase 1 (Virtuoso):
- [ ] Create 100+ mock cases, scroll smoothly
- [ ] Filter insights, scroll position maintained
- [ ] Click entity, detail loads correctly
- [ ] Preflight checkboxes work during scroll
- [ ] Timeline groups stay sticky

### Phase 2 (Document Backend):
- [ ] Endpoint returns document text
- [ ] 404 for missing documents
- [ ] Various formats handled (txt, md, json)

### Phase 3 (CodeMirror):
- [ ] Document viewer displays text
- [ ] Syntax highlighting works
- [ ] Search highlights matches
- [ ] Copy/download functions work
- [ ] Modal opens from findings

### Phase 4 (Recharts):
- [ ] Dashboard page loads
- [ ] Chart placeholders visible
- [ ] Navigation works

---

# Performance Targets

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| List scroll FPS | ~30fps (100+ items) | 60fps | Virtuoso |
| Initial page load | ~2s | <3s | Code splitting |
| Bundle size | 150kb | <250kb | Tree-shaking |
| Document load time | N/A | <1s | Backend caching |

---

# Rollback Plan

If any phase fails:

```bash
# Revert git changes
cd C:\EhkoVaults\ReCog\_ui
git status
git diff
git checkout -- .

# Or revert specific file
git checkout HEAD -- src/components/pages/CasesPage.jsx

# Reinstall clean deps
rm -rf node_modules package-lock.json
npm install
```

---

# Post-Implementation Tasks

## Phase 1 Complete:
- [ ] Commit: "feat: Add React Virtuoso to all list pages"
- [ ] Test with real data (500+ findings)
- [ ] Update documentation

## Phase 2 Complete:
- [ ] Commit: "feat: Add document text retrieval endpoint"
- [ ] Test with various document formats
- [ ] Update API docs

## Phase 3 Complete:
- [ ] Commit: "feat: Add CodeMirror document viewer"
- [ ] Test syntax highlighting for all formats
- [ ] Update user guide

## Phase 4 Complete:
- [ ] Commit: "feat: Add dashboard structure and Recharts foundation"
- [ ] Plan chart implementations for next session
- [ ] Update roadmap

---

# Known Issues & Limitations

## Phase 1 (Virtuoso):
- **Grid layouts:** Cases page changes from grid to list (easier to virtualize)
- **Checkbox state:** Preflight may need extra care to maintain selection during scroll
- **Height calculation:** Initial render may be slow for very complex cards

## Phase 2 (Document Backend):
- **Storage:** Documents must be retained in DB/filesystem (currently may be cleaned after processing)
- **Large files:** 50MB+ documents may cause memory issues
- **Formats:** Some binary formats (PDF, DOCX) may need text extraction

## Phase 3 (CodeMirror):
- **Large documents:** 10,000+ lines may cause initial render delay
- **Search performance:** Regex searches on large docs can lag
- **Mobile:** Touch scrolling in modal may conflict with page scroll

## Phase 4 (Recharts):
- **Data aggregation:** Need backend endpoints for dashboard stats
- **Real-time:** Charts are static, not live-updating
- **Customization:** ReCog theme colors need manual application

---

# Future Enhancements (Phase 5+)

## Advanced Virtualization:
- [ ] Virtual scrolling in modal dialogs
- [ ] Virtualized entity graph (for large networks)
- [ ] Infinite scroll on insights (load more on scroll)

## Document Viewer:
- [ ] Highlight specific excerpts from findings
- [ ] Side-by-side comparison of document versions
- [ ] Annotate documents (add comments inline)
- [ ] Export with highlights

## Charts & Analytics:
- [ ] Real-time activity chart (WebSocket updates)
- [ ] Case comparison dashboard
- [ ] Entity relationship visualizations
- [ ] Pattern emergence timeline
- [ ] Export dashboard as PDF report

---

# Success Metrics

## Phase 1 Success:
- ✅ All lists render 1000+ items at 60fps
- ✅ Bundle size increase <20kb
- ✅ Zero functional regressions
- ✅ Scroll position maintained on filter

## Phase 2 Success:
- ✅ Document text retrieved in <500ms
- ✅ All uploaded formats supported
- ✅ Graceful handling of missing docs

## Phase 3 Success:
- ✅ Document viewer loads in <1s
- ✅ Syntax highlighting works for 5+ formats
- ✅ Search finds matches in <100ms
- ✅ Terminal theme matches ReCog aesthetic

## Phase 4 Success:
- ✅ Dashboard page structure complete
- ✅ Chart components ready for data
- ✅ Navigation includes Dashboard link

---

# Claude Code CLI Commands

## To start implementation:

```bash
# Phase 1: Virtualization
claude code "Implement React Virtuoso for ReCog UI. Follow the plan in RECOG_UI_ENHANCEMENT_PLAN.md Phase 1. Install dependencies, create virtualization.js utilities, and update all 6 list pages (CasesPage, InsightsPage, EntitiesPage, PatternsPage, PreflightPage, and CaseDetail views). Preserve existing functionality and styling."

# Phase 2: Document Backend
claude code "Add document text retrieval endpoint to ReCog backend. Follow Phase 2 plan. Add /api/documents/<doc_id>/text route to server.py, update PreflightManager if needed, and add getDocumentText() to frontend API client."

# Phase 3: CodeMirror Viewer
claude code "Implement CodeMirror document viewer for ReCog. Follow Phase 3 plan. Install dependencies, create DocumentViewer component with ReCog terminal theme, add DocumentViewerPage and modal components, integrate 'View Source' buttons into InsightsPage and CaseDetail, update routing."

# Phase 4: Recharts Foundation
claude code "Set up Recharts dashboard foundation for ReCog. Follow Phase 4 plan. Install Recharts, create DashboardPage with stat cards and chart placeholders, add chart component stubs, update navigation and routing."
```

---

# End of Implementation Plan

This plan provides Claude Code CLI with:
✅ Clear phase separation  
✅ Specific file paths and code snippets  
✅ Testing checklists  
✅ Success criteria  
✅ Rollback procedures  
✅ Performance targets  

**Next Steps:**
1. Review this plan
2. Confirm approach
3. Execute Phase 1 with Claude Code CLI
4. Test and validate
5. Proceed to Phase 2

Good luck! 🚀

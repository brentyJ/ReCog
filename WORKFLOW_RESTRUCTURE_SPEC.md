# ReCog Workflow Restructure - Implementation Spec

**Date:** 2026-01-10  
**Status:** Ready for Implementation  
**Priority:** HIGH (Core UX Evolution)  
**Estimated Time:** 8-12 hours across 3 phases

---

## Executive Summary

### What We're Building

Transform ReCog from a **multi-stage wizard** into a **conversational, auto-progressing analysis engine**. Users drop files and Cypher guides them through clarification, then the system runs to completion while streaming insights in real-time.

### Why This Matters

**Current Problem:**
- Too many decision gates (Upload → Preflight → Review → Extract → Synthesize)
- Users abandon workflow before seeing synthesis results
- Implementation details (Tiers) exposed to users unnecessarily
- Segmented flow prevents dopamine hits from rapid insight discovery

**Solution:**
- **One-button flow**: Drop files → Clarify context → Watch insights appear
- **Real-time feedback**: Terminal-style monitor streams discoveries as they happen
- **Cypher-guided**: Assistant Mode provides tutorial-level guidance
- **Auto-progression**: System runs to completion without manual gates

### Core Principles

1. **Pipeline stays the same** - Tier 0 → Extract → Synthesize logic unchanged
2. **Execution becomes automatic** - No manual progression between stages
3. **Cypher becomes the UI** - Conversation + contextual buttons drive workflow
4. **Real-time visibility** - Stream insights as discovered (dopamine feedback loop)
5. **Professional polish** - Remove "Free" language, optimize for AI-first UX

---

## Architecture Overview

### State Machine

Cases now have explicit states tracking pipeline progress:

```
UPLOADING → SCANNING → CLARIFYING → PROCESSING → COMPLETE
              ↓                          ↓
         (Tier 0)              (Extract + Synthesize)
         
Optional: COMPLETE → WATCHING (background monitor)
```

### Data Flow

```
1. User drops files → Case created (state: UPLOADING)
2. System triggers Tier 0 → (state: SCANNING)
3. Tier 0 completes → (state: CLARIFYING) if entities unknown
4. User clarifies via Cypher → System shows cost estimate → User confirms
5. System starts extraction → (state: PROCESSING)
6. Insights stream to terminal in real-time
7. Synthesis runs automatically → (state: COMPLETE)
8. Results displayed in terminal + Case detail
```

### Key Components

| Component | Change | Purpose |
|-----------|--------|---------|
| `cases` table | Add 7 new fields | Track state, costs, settings |
| State machine | New module | Auto-advance logic |
| Terminal monitor | New UI component | Real-time insight streaming |
| Cypher assistant mode | Enhanced prompts | Tutorial guidance |
| Worker process | Modified | Stream progress updates |

---

## Database Schema Changes

### New Fields in `cases` Table

```sql
-- Migration: migration_v0_8_workflow_restructure.sql

ALTER TABLE cases ADD COLUMN state TEXT DEFAULT 'uploading' 
    CHECK(state IN ('uploading', 'scanning', 'clarifying', 'processing', 'complete', 'watching'));
    
ALTER TABLE cases ADD COLUMN estimated_cost REAL DEFAULT 0.0;
ALTER TABLE cases ADD COLUMN actual_cost REAL DEFAULT 0.0;
ALTER TABLE cases ADD COLUMN assistant_mode BOOLEAN DEFAULT FALSE;
ALTER TABLE cases ADD COLUMN auto_process BOOLEAN DEFAULT TRUE;
ALTER TABLE cases ADD COLUMN monitor_directory BOOLEAN DEFAULT FALSE;
ALTER TABLE cases ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE cases ADD COLUMN processing_started_at TIMESTAMP;
ALTER TABLE cases ADD COLUMN processing_completed_at TIMESTAMP;

-- Index for active case queries
CREATE INDEX idx_cases_state ON cases(state);
CREATE INDEX idx_cases_last_activity ON cases(last_activity);
```

### New Table: `case_progress`

Track fine-grained progress within processing state:

```sql
CREATE TABLE case_progress (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    stage TEXT NOT NULL,  -- 'tier0', 'extraction', 'synthesis', 'critique'
    status TEXT NOT NULL,  -- 'pending', 'running', 'complete', 'failed'
    progress REAL DEFAULT 0.0,  -- 0.0 to 1.0
    current_item TEXT,  -- e.g., "Processing email_042.txt"
    total_items INTEGER,
    completed_items INTEGER,
    recent_insight TEXT,  -- Latest discovery for terminal display
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

CREATE INDEX idx_case_progress_case_id ON case_progress(case_id);
```

---

## Phase 1: Auto-Progression Core (Backend)

**Goal:** Cases advance through pipeline automatically without user intervention

**Estimated Time:** 3-4 hours

### 1.1 State Machine Module

**New file:** `_scripts/recog_engine/state_machine.py`

```python
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone

class CaseState(Enum):
    UPLOADING = "uploading"
    SCANNING = "scanning"
    CLARIFYING = "clarifying"
    PROCESSING = "processing"
    COMPLETE = "complete"
    WATCHING = "watching"

class StateTransition:
    """Defines valid state transitions and their conditions"""
    
    TRANSITIONS = {
        'uploading': ['scanning'],
        'scanning': ['clarifying', 'processing'],  # Skip clarifying if no unknowns
        'clarifying': ['processing'],
        'processing': ['complete'],
        'complete': ['watching', 'processing'],  # Can reprocess or watch
    }
    
    @staticmethod
    def can_transition(from_state: str, to_state: str) -> bool:
        """Check if transition is valid"""
        return to_state in StateTransition.TRANSITIONS.get(from_state, [])
    
    @staticmethod
    def next_state(current_state: str, context: Dict[str, Any]) -> Optional[str]:
        """Determine next state based on context"""
        
        if current_state == 'uploading':
            if context.get('files_uploaded'):
                return 'scanning'
        
        elif current_state == 'scanning':
            if context.get('unknown_entities'):
                return 'clarifying'
            elif context.get('tier0_complete'):
                return 'processing'
        
        elif current_state == 'clarifying':
            if context.get('entities_clarified'):
                return 'processing'
        
        elif current_state == 'processing':
            if context.get('synthesis_complete'):
                return 'complete'
        
        return None

class CaseStateMachine:
    """Manages case state transitions and auto-progression"""
    
    def __init__(self, db, case_store, timeline_store):
        self.db = db
        self.case_store = case_store
        self.timeline_store = timeline_store
    
    def advance_case(self, case_id: str, context: Dict[str, Any] = None) -> bool:
        """Try to advance case to next state"""
        context = context or {}
        
        case = self.case_store.get_case(case_id)
        if not case:
            return False
        
        current_state = case.state
        next_state = StateTransition.next_state(current_state, context)
        
        if next_state and StateTransition.can_transition(current_state, next_state):
            self.transition_to(case_id, next_state)
            return True
        
        return False
    
    def transition_to(self, case_id: str, new_state: str):
        """Execute state transition"""
        
        # Update case state
        self.db.execute("""
            UPDATE cases 
            SET state = ?, last_activity = ?
            WHERE id = ?
        """, (new_state, datetime.now(timezone.utc), case_id))
        
        # Log timeline event
        self.timeline_store.add_event(
            case_id=case_id,
            event_type='state_changed',
            event_data={'new_state': new_state}
        )
        
        # Trigger next action
        self._trigger_action(case_id, new_state)
    
    def _trigger_action(self, case_id: str, state: str):
        """Trigger appropriate action for new state"""
        
        if state == 'scanning':
            # Queue Tier 0 processing
            from .queue import queue_tier0
            queue_tier0(case_id)
        
        elif state == 'processing':
            # Queue extraction + synthesis
            from .queue import queue_extraction
            queue_extraction(case_id)
        
        elif state == 'watching':
            # Start background monitor
            from .monitor import start_monitoring
            start_monitoring(case_id)
    
    def get_progress(self, case_id: str) -> Dict[str, Any]:
        """Get detailed progress for case"""
        
        progress = self.db.execute("""
            SELECT * FROM case_progress 
            WHERE case_id = ? 
            ORDER BY updated_at DESC 
            LIMIT 1
        """, (case_id,)).fetchone()
        
        if progress:
            return dict(progress)
        
        return {
            'stage': 'unknown',
            'status': 'pending',
            'progress': 0.0
        }
```

### 1.2 Modify Upload Endpoint

**File:** `_scripts/server.py`

```python
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload files and auto-start Tier 0"""
    
    # ... existing upload logic ...
    
    # Create case if not exists
    case_id = request.form.get('case_id')
    if not case_id:
        case = case_store.create_case(
            title=f"Analysis {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            context="",
            auto_process=True  # Enable auto-progression
        )
        case_id = case.id
    
    # Store files
    session_id = create_preflight_session(files, case_id)
    
    # TRIGGER TIER 0 IMMEDIATELY
    state_machine.transition_to(case_id, 'scanning')
    
    return api_response(success=True, data={
        'case_id': case_id,
        'session_id': session_id,
        'state': 'scanning',
        'message': 'Files uploaded. Starting initial scan...'
    })
```

### 1.3 Auto-Progression Worker

**File:** `_scripts/recog_engine/auto_progress.py`

```python
"""Background worker that auto-advances cases"""

import time
from datetime import datetime, timedelta, timezone
from .state_machine import CaseStateMachine, CaseState

def run_auto_progress_worker(db, case_store, timeline_store, interval=10):
    """Poll for cases that can be advanced"""
    
    state_machine = CaseStateMachine(db, case_store, timeline_store)
    
    print("[AUTO-PROGRESS] Worker started")
    
    while True:
        try:
            # Find cases in clarifying state with all entities identified
            clarifying_cases = db.execute("""
                SELECT id FROM cases 
                WHERE state = 'clarifying' 
                AND last_activity > ?
            """, (datetime.now(timezone.utc) - timedelta(hours=24),)).fetchall()
            
            for row in clarifying_cases:
                case_id = row['id']
                
                # Check if entities are clarified
                unknown_count = db.execute("""
                    SELECT COUNT(*) as count FROM entities 
                    WHERE case_id = ? AND confirmed = FALSE
                """, (case_id,)).fetchone()['count']
                
                if unknown_count == 0:
                    # All clarified - advance to processing
                    state_machine.advance_case(case_id, {
                        'entities_clarified': True
                    })
                    print(f"[AUTO-PROGRESS] Advanced case {case_id} to processing")
            
            # Find cases in scanning state with Tier 0 complete
            scanning_cases = db.execute("""
                SELECT id FROM cases 
                WHERE state = 'scanning'
            """, ()).fetchall()
            
            for row in scanning_cases:
                case_id = row['id']
                
                # Check if Tier 0 is done
                progress = db.execute("""
                    SELECT status FROM case_progress 
                    WHERE case_id = ? AND stage = 'tier0'
                    ORDER BY updated_at DESC LIMIT 1
                """, (case_id,)).fetchone()
                
                if progress and progress['status'] == 'complete':
                    # Check for unknown entities
                    unknown_count = db.execute("""
                        SELECT COUNT(*) as count FROM entities 
                        WHERE case_id = ? AND confirmed = FALSE
                    """, (case_id,)).fetchone()['count']
                    
                    if unknown_count > 0:
                        state_machine.advance_case(case_id, {'unknown_entities': True})
                    else:
                        state_machine.advance_case(case_id, {'tier0_complete': True})
                    
                    print(f"[AUTO-PROGRESS] Advanced case {case_id} from scanning")
            
        except Exception as e:
            print(f"[AUTO-PROGRESS] Error: {e}")
        
        time.sleep(interval)
```

### 1.4 Cost Estimation

**File:** `_scripts/recog_engine/cost_estimator.py`

```python
"""Estimate API costs before extraction"""

from typing import Dict, Any

class CostEstimator:
    """Estimate token costs for case processing"""
    
    # Token costs per 1M tokens
    COSTS = {
        'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
        'claude-sonnet-4.5': {'input': 3.00, 'output': 15.00},
        'claude-haiku-4.5': {'input': 0.80, 'output': 4.00},
    }
    
    @staticmethod
    def estimate_extraction_cost(case_id: str, db) -> Dict[str, Any]:
        """Estimate cost for extracting insights from case documents"""
        
        # Get total word count from preflight items
        result = db.execute("""
            SELECT SUM(word_count) as total_words
            FROM preflight_items pi
            JOIN preflight_sessions ps ON pi.session_id = ps.id
            WHERE ps.case_id = ? AND pi.excluded = FALSE
        """, (case_id,)).fetchone()
        
        total_words = result['total_words'] or 0
        
        # Rough conversion: words to tokens (~1.3 tokens per word)
        estimated_tokens = int(total_words * 1.3)
        
        # Estimate extraction tokens (input + output)
        # Each document: input tokens + ~500 output tokens for insights
        doc_count = db.execute("""
            SELECT COUNT(*) as count FROM preflight_items pi
            JOIN preflight_sessions ps ON pi.session_id = ps.id
            WHERE ps.case_id = ? AND pi.excluded = FALSE
        """, (case_id,)).fetchone()['count']
        
        input_tokens = estimated_tokens + (doc_count * 1000)  # System prompt per doc
        output_tokens = doc_count * 500  # Insights per doc
        
        # Calculate cost (using gpt-4o-mini as default)
        model_costs = CostEstimator.COSTS['gpt-4o-mini']
        input_cost = (input_tokens / 1_000_000) * model_costs['input']
        output_cost = (output_tokens / 1_000_000) * model_costs['output']
        
        total_cost = input_cost + output_cost
        
        return {
            'estimated_tokens': input_tokens + output_tokens,
            'estimated_cost_usd': round(total_cost, 2),
            'document_count': doc_count,
            'model': 'gpt-4o-mini'
        }
```

### 1.5 Modified Queue Worker

**File:** `_scripts/worker.py` (modify existing)

```python
def process_extraction_job(job_id, session_id, case_id):
    """Process extraction with progress updates"""
    
    # Update case state
    db.execute("UPDATE cases SET processing_started_at = ? WHERE id = ?", 
               (datetime.now(timezone.utc), case_id))
    
    # Create progress tracker
    progress_id = str(uuid.uuid4())
    db.execute("""
        INSERT INTO case_progress (id, case_id, stage, status, total_items)
        VALUES (?, ?, 'extraction', 'running', ?)
    """, (progress_id, case_id, item_count))
    
    # Process items
    for idx, item in enumerate(items):
        # Extract insights
        insights = extract_insights(item['text'])
        
        # Update progress with recent discovery
        if insights:
            db.execute("""
                UPDATE case_progress 
                SET completed_items = ?, 
                    progress = ?,
                    recent_insight = ?,
                    current_item = ?,
                    updated_at = ?
                WHERE id = ?
            """, (idx + 1, (idx + 1) / item_count, 
                  insights[0].content[:100], item['file_name'],
                  datetime.now(timezone.utc), progress_id))
        
        time.sleep(0.1)  # Allow polling to catch updates
    
    # Mark extraction complete
    db.execute("""
        UPDATE case_progress 
        SET status = 'complete', progress = 1.0 
        WHERE id = ?
    """, (progress_id,))
    
    # Start synthesis automatically
    run_synthesis(case_id)
```

---

## Phase 2: Real-Time Terminal Display (Frontend)

**Goal:** Split-screen Case view with live insight streaming

**Estimated Time:** 3-4 hours

### 2.1 Terminal Monitor Component

**New file:** `_ui/src/components/case/CaseTerminal.jsx`

```jsx
import { useState, useEffect, useRef } from 'react'
import { Terminal, Zap, TrendingUp, AlertCircle } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export default function CaseTerminal({ caseId }) {
  const [logs, setLogs] = useState([])
  const [topInsights, setTopInsights] = useState([])
  const [progress, setProgress] = useState(null)
  const terminalRef = useRef(null)
  const pollInterval = useRef(null)
  
  useEffect(() => {
    if (!caseId) return
    
    // Start polling for progress
    pollInterval.current = setInterval(pollProgress, 2000)
    
    return () => clearInterval(pollInterval.current)
  }, [caseId])
  
  const pollProgress = async () => {
    try {
      const response = await fetch(`/api/cases/${caseId}/progress`)
      const data = await response.json()
      
      if (data.success) {
        setProgress(data.data)
        
        // Add new log if insight discovered
        if (data.data.recent_insight) {
          addLog({
            type: 'insight',
            content: data.data.recent_insight,
            timestamp: new Date()
          })
        }
        
        // Update top insights
        if (data.data.top_insights) {
          setTopInsights(data.data.top_insights)
        }
        
        // Stop polling if complete
        if (data.data.status === 'complete') {
          clearInterval(pollInterval.current)
        }
      }
    } catch (error) {
      console.error('Polling error:', error)
    }
  }
  
  const addLog = (log) => {
    setLogs(prev => [...prev, log])
    
    // Auto-scroll to bottom
    setTimeout(() => {
      if (terminalRef.current) {
        terminalRef.current.scrollTop = terminalRef.current.scrollHeight
      }
    }, 100)
  }
  
  const getLogIcon = (type) => {
    switch(type) {
      case 'insight': return <Zap className="text-yellow-400" size={16} />
      case 'pattern': return <TrendingUp className="text-teal-400" size={16} />
      case 'warning': return <AlertCircle className="text-orange-400" size={16} />
      default: return <Terminal className="text-gray-400" size={16} />
    }
  }
  
  return (
    <div className="h-full flex flex-col bg-black/90 rounded-lg border border-teal-500/30">
      {/* Terminal Header */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-teal-500/30 bg-teal-950/50">
        <Terminal size={16} className="text-teal-400" />
        <span className="font-mono text-sm text-teal-400">ANALYSIS MONITOR</span>
        
        {progress && (
          <Badge variant="secondary" className="ml-auto font-mono text-xs">
            {progress.stage.toUpperCase()} {Math.round(progress.progress * 100)}%
          </Badge>
        )}
      </div>
      
      {/* Top Insights Panel */}
      {topInsights.length > 0 && (
        <div className="p-4 border-b border-teal-500/30 bg-teal-950/20 space-y-2">
          <div className="text-xs text-teal-400 font-mono uppercase mb-2">
            Top Findings
          </div>
          {topInsights.slice(0, 3).map((insight, i) => (
            <div 
              key={i}
              className="flex items-start gap-2 text-sm p-2 rounded bg-black/50 
                         border border-teal-500/20 hover:border-teal-500/50 
                         cursor-pointer transition-all group"
            >
              <Zap size={14} className="text-yellow-400 mt-1 flex-shrink-0" />
              <div className="flex-1 font-mono text-xs text-gray-300 group-hover:text-white">
                {insight.content}
              </div>
              <Badge variant="outline" className="text-xs">
                {insight.significance.toUpperCase()}
              </Badge>
            </div>
          ))}
        </div>
      )}
      
      {/* Log Stream */}
      <div 
        ref={terminalRef}
        className="flex-1 overflow-y-auto p-4 space-y-1 font-mono text-xs"
      >
        {logs.length === 0 && (
          <div className="text-gray-500 text-center py-8">
            Waiting for analysis to begin...
          </div>
        )}
        
        {logs.map((log, i) => (
          <div key={i} className="flex items-start gap-2 text-gray-300">
            <span className="text-gray-600">
              {log.timestamp.toLocaleTimeString()}
            </span>
            {getLogIcon(log.type)}
            <span className="flex-1">{log.content}</span>
          </div>
        ))}
      </div>
      
      {/* Progress Bar */}
      {progress && progress.status === 'running' && (
        <div className="px-4 py-2 border-t border-teal-500/30 bg-teal-950/20">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-teal-400 font-mono">
              {progress.current_item || 'Processing...'}
            </span>
            <span className="text-xs text-gray-500 ml-auto">
              {progress.completed_items}/{progress.total_items}
            </span>
          </div>
          <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-teal-500 to-yellow-400 transition-all duration-500"
              style={{ width: `${progress.progress * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
```

### 2.2 Split-Screen Case Detail

**Modify:** `_ui/src/components/pages/CaseDetail.jsx`

```jsx
import CaseTerminal from '@/components/case/CaseTerminal'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export default function CaseDetail({ caseId }) {
  const [caseData, setCaseData] = useState(null)
  
  useEffect(() => {
    loadCase()
  }, [caseId])
  
  const loadCase = async () => {
    const response = await fetch(`/api/cases/${caseId}`)
    const data = await response.json()
    if (data.success) setCaseData(data.data)
  }
  
  if (!caseData) return <LoadingState />
  
  return (
    <div className="h-screen flex flex-col p-6">
      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl font-bold">{caseData.title}</h1>
          <Badge>{caseData.state.toUpperCase()}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">{caseData.context}</p>
      </div>
      
      {/* Split View */}
      <div className="flex-1 grid grid-cols-2 gap-4">
        {/* Left: Terminal Monitor */}
        <CaseTerminal caseId={caseId} />
        
        {/* Right: Case Details */}
        <div className="space-y-4 overflow-y-auto">
          {/* Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <StatItem label="Documents" value={caseData.document_count} />
              <StatItem label="Insights" value={caseData.insight_count} />
              <StatItem label="Patterns" value={caseData.pattern_count} />
              <StatItem label="Findings" value={caseData.finding_count} />
            </CardContent>
          </Card>
          
          {/* Timeline */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              {/* Timeline events */}
            </CardContent>
          </Card>
          
          {/* Documents */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Documents</CardTitle>
            </CardHeader>
            <CardContent>
              {/* Document list */}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function StatItem({ label, value }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-lg font-bold">{value}</span>
    </div>
  )
}
```

### 2.3 Progress API Endpoint

**File:** `_scripts/server.py`

```python
@app.route('/api/cases/<case_id>/progress', methods=['GET'])
def get_case_progress(case_id):
    """Get real-time progress for case"""
    
    # Get current progress
    progress = db.execute("""
        SELECT * FROM case_progress 
        WHERE case_id = ? 
        ORDER BY updated_at DESC 
        LIMIT 1
    """, (case_id,)).fetchone()
    
    if not progress:
        return api_response(success=True, data={
            'stage': 'idle',
            'status': 'pending',
            'progress': 0.0
        })
    
    # Get top insights (highest significance)
    top_insights = db.execute("""
        SELECT content, significance 
        FROM insights 
        WHERE case_id = ? 
        ORDER BY significance DESC 
        LIMIT 5
    """, (case_id,)).fetchall()
    
    return api_response(success=True, data={
        'stage': progress['stage'],
        'status': progress['status'],
        'progress': progress['progress'],
        'current_item': progress['current_item'],
        'completed_items': progress['completed_items'],
        'total_items': progress['total_items'],
        'recent_insight': progress['recent_insight'],
        'top_insights': [dict(i) for i in top_insights]
    })
```

---

## Phase 3: Assistant Mode (Cypher Enhancement)

**Goal:** Tutorial-level guidance with color change and state-aware prompts

**Estimated Time:** 2-3 hours

### 3.1 Assistant Mode Toggle

**Modify:** `_ui/src/contexts/CypherContext.jsx`

```jsx
export function CypherProvider({ children, caseId }) {
  const [assistantMode, setAssistantMode] = useState(false)
  const [caseState, setCaseState] = useState(null)
  
  // Poll case state to inform Cypher
  useEffect(() => {
    if (!caseId) return
    
    const pollState = async () => {
      const response = await fetch(`/api/cases/${caseId}`)
      const data = await response.json()
      if (data.success) {
        setCaseState(data.data.state)
      }
    }
    
    pollState()
    const interval = setInterval(pollState, 5000)
    return () => clearInterval(interval)
  }, [caseId])
  
  const toggleAssistantMode = () => {
    setAssistantMode(prev => !prev)
  }
  
  const value = {
    // ... existing context values
    assistantMode,
    toggleAssistantMode,
    caseState
  }
  
  return (
    <CypherContext.Provider value={value}>
      {children}
    </CypherContext.Provider>
  )
}
```

### 3.2 Color Theme Switch

**Modify:** `_ui/src/components/cypher/Cypher.jsx`

```jsx
export default function Cypher({ caseId }) {
  const { assistantMode, toggleAssistantMode } = useCypher()
  
  const accentColor = assistantMode ? 'amber' : 'teal'
  const accentClass = assistantMode ? 'text-amber-400' : 'text-teal-400'
  const borderClass = assistantMode ? 'border-amber-500/30' : 'border-teal-500/30'
  
  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" className="font-mono">
          <span className={accentClass}>⟨⟩</span>
          Cypher
          {assistantMode && (
            <Badge variant="secondary" className="ml-2 bg-amber-500/20">
              ASSIST
            </Badge>
          )}
        </Button>
      </SheetTrigger>
      
      <SheetContent side="right" className={`w-[500px] ${borderClass}`}>
        {/* Header with toggle */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <span className={`text-2xl ${accentClass}`}>⟨⟩</span>
            <div>
              <div className="font-mono font-bold">Cypher</div>
              <div className="text-xs text-muted-foreground">
                {assistantMode ? 'Assistant Mode' : 'Terminal Scribe'}
              </div>
            </div>
          </div>
          
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleAssistantMode}
            className="font-mono text-xs"
          >
            {assistantMode ? '🔥 ASSIST' : '🤖 BASIC'}
          </Button>
        </div>
        
        {/* Rest of component */}
      </SheetContent>
    </Sheet>
  )
}
```

### 3.3 Enhanced System Prompt

**Modify:** `_scripts/recog_engine/cypher/prompts.py`

```python
def load_cypher_system_prompt(context, assistant_mode=False):
    """Load appropriate system prompt based on mode"""
    
    base_prompt = CYPHER_BASE_PROMPT  # Existing prompt
    
    if assistant_mode:
        base_prompt += """

ASSISTANT MODE ACTIVE - Tutorial Guidance Enabled

You are now in Assistant Mode. This means:

1. **Explain Everything**: Don't assume user knows the process
   - "We're at entity clarification - this helps me understand who's who"
   - "Deep scan will analyze relationships between documents"
   
2. **Proactive Teaching**: Point out features and capabilities
   - "Tip: You can click on any insight to see its sources"
   - "I can watch this folder for new files if you want"
   
3. **Guide Through Workflow**: Tell user what's happening and why
   - "I'm running Tier 0 first - this is a quick scan that finds names, dates, emotions"
   - "Now I'll do deep analysis - this uses AI to extract insights and costs ~$0.50"
   
4. **Ask Clarifying Questions**: Help user provide better context
   - "What's this case about? The more context you give, the better my analysis"
   - "These emails mention 'Project Mercury' - is that a product or initiative?"
   
5. **Suggest Next Steps**: Don't wait for user to ask
   - "Want me to look for communication gaps in the timeline?"
   - "I found a pattern - should I investigate further?"

Remember: Assistant Mode burns more tokens but provides much better guidance.
When user gains confidence, they can switch back to Basic Mode.
"""
    
    # Inject case state
    if context.get('case_state'):
        base_prompt += f"""

CURRENT CASE STATE: {context['case_state'].upper()}

State Meanings:
- UPLOADING: Files being added
- SCANNING: Running Tier 0 (free analysis)
- CLARIFYING: Need user input (entity identification)
- PROCESSING: Running deep analysis (extraction + synthesis)
- COMPLETE: Analysis finished, results available

Your response should be appropriate for this state.
"""
    
    return base_prompt
```

### 3.4 State-Aware Response Generation

**Modify:** `_scripts/recog_engine/cypher/response_formatter.py`

```python
def format_cypher_response(intent, result, context):
    """Format response with state awareness"""
    
    # Check if assistant mode
    assistant_mode = context.get('assistant_mode', False)
    case_state = context.get('case_state')
    
    # Add contextual guidance in assistant mode
    if assistant_mode and case_state:
        if case_state == 'clarifying':
            result['reply'] += "\n\nℹ️ We're at entity clarification. Tell me who these people are and I'll tag them properly in the analysis."
        
        elif case_state == 'processing':
            result['reply'] += "\n\n⚡ Deep analysis running. Watch the terminal for insights as they're discovered."
        
        elif case_state == 'complete':
            result['reply'] += "\n\n✅ Analysis complete! Check the top findings in the terminal or ask me to explain patterns."
    
    return result
```

### 3.5 Cost Warning Dialog

**New component:** `_ui/src/components/case/CostWarningDialog.jsx`

```jsx
import { AlertCircle, DollarSign } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

export default function CostWarningDialog({ open, onConfirm, onCancel, estimate }) {
  return (
    <Dialog open={open} onOpenChange={onCancel}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <AlertCircle className="text-yellow-400" size={24} />
            <DialogTitle>Ready for Deep Scan</DialogTitle>
          </div>
          <DialogDescription>
            We're about to run AI-powered analysis on your documents
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          <div className="flex items-center justify-between p-3 bg-muted rounded">
            <span className="text-sm">Documents</span>
            <span className="font-bold">{estimate.document_count}</span>
          </div>
          
          <div className="flex items-center justify-between p-3 bg-muted rounded">
            <span className="text-sm">Estimated Tokens</span>
            <span className="font-mono text-sm">{estimate.estimated_tokens.toLocaleString()}</span>
          </div>
          
          <div className="flex items-center justify-between p-3 bg-yellow-500/10 border border-yellow-500/30 rounded">
            <div className="flex items-center gap-2">
              <DollarSign size={16} className="text-yellow-400" />
              <span className="text-sm font-medium">Estimated Cost</span>
            </div>
            <span className="font-bold text-lg">${estimate.estimated_cost_usd}</span>
          </div>
          
          <p className="text-xs text-muted-foreground">
            This will extract insights, identify patterns, and generate synthesis. 
            Progress will be shown in real-time on the terminal monitor.
          </p>
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm} className="bg-yellow-500 hover:bg-yellow-600">
            Start Deep Scan
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

---

## Implementation Notes

### Database Migration Order

1. Run `migration_v0_8_workflow_restructure.sql` to add new fields
2. Migrate existing cases to 'complete' state (they've already been processed)
3. Initialize `case_progress` table (empty)

### Worker Process Changes

The auto-progress worker can run as:
- **Separate process**: `python auto_progress.py` (recommended)
- **Thread in worker.py**: Add to existing worker
- **Cron job**: Run every minute via system scheduler

### Cost Tracking

After each extraction/synthesis:
```python
# Update actual cost
db.execute("""
    UPDATE cases 
    SET actual_cost = actual_cost + ?
    WHERE id = ?
""", (cost_usd, case_id))
```

### Terminal Performance

- Polling every 2 seconds during processing
- Switch to 5-second intervals when idle
- Stop polling when state is 'complete'
- Cap log entries at 1000 (truncate older)

### Removing "Free" Language

Search and replace in all files:
- "FREE" → "Signal Extraction"
- "Free analysis" → "Initial scan"
- "No cost" → "Quick analysis"

---

## Success Criteria

### Phase 1 Complete When:
- ✅ Upload triggers Tier 0 automatically
- ✅ Cases advance from scanning → clarifying → processing without clicks
- ✅ Cost estimate shown before extraction
- ✅ Synthesis runs automatically after extraction

### Phase 2 Complete When:
- ✅ Terminal monitor displays on Case detail page
- ✅ Insights stream in real-time during extraction
- ✅ Top 3 findings always visible at top
- ✅ Progress bar shows current document
- ✅ Split-screen layout works on all resolutions

### Phase 3 Complete When:
- ✅ Assistant Mode toggle changes color (teal → amber)
- ✅ Cypher explains process steps in assistant mode
- ✅ State-aware responses guide user through workflow
- ✅ Tutorial prompts appear at appropriate times
- ✅ User can complete full workflow via conversation

### Overall Success:
- ✅ User can drop files and see synthesis without clicking through stages
- ✅ Dopamine hits from watching insights appear
- ✅ Professional AI-first UX (no "free" language)
- ✅ Cypher can guide novice user through entire process

---

## Testing Checklist

### Phase 1 Testing
```
1. Upload 5 test documents without case selected
2. Verify Tier 0 runs automatically
3. Check case state transitions to 'clarifying'
4. Identify all entities
5. Verify auto-advance to 'processing'
6. Confirm cost estimate dialog appears
7. Start extraction
8. Verify synthesis runs after extraction completes
9. Check case state transitions to 'complete'
```

### Phase 2 Testing
```
1. Open case in 'processing' state
2. Verify terminal monitor displays on left
3. Watch insights stream during extraction
4. Check progress bar updates correctly
5. Verify top findings populate
6. Click on insight in terminal (future: opens detail)
7. Test on small (1920x1080) and large (2560x1440) screens
```

### Phase 3 Testing
```
1. Toggle Assistant Mode on
2. Verify color changes teal → amber
3. Ask "Where am I?" in each state
4. Verify state-aware responses
5. Check tutorial prompts appear
6. Complete full workflow in assistant mode
7. Toggle off, verify basic mode works
```

---

## File Changes Summary

### New Files (9)
```
_scripts/recog_engine/state_machine.py
_scripts/recog_engine/auto_progress.py
_scripts/recog_engine/cost_estimator.py
_scripts/migrations/migration_v0_8_workflow_restructure.sql
_ui/src/components/case/CaseTerminal.jsx
_ui/src/components/case/CostWarningDialog.jsx
```

### Modified Files (8)
```
_scripts/server.py               - Upload endpoint, progress endpoint
_scripts/worker.py               - Progress updates during extraction
_scripts/recog_engine/cypher/prompts.py           - Assistant mode prompt
_scripts/recog_engine/cypher/response_formatter.py - State-aware responses
_ui/src/contexts/CypherContext.jsx - Assistant mode state
_ui/src/components/cypher/Cypher.jsx - Color switching
_ui/src/components/pages/CaseDetail.jsx - Split-screen layout
_ui/src/lib/api.js               - Progress polling function
```

---

## Next Steps for CC (Claude Code)

1. **Review this spec** - Ask any clarifications
2. **Phase 1 first** - Backend state machine + auto-progression
3. **Test Phase 1** - Verify auto-advance works before frontend
4. **Phase 2** - Terminal monitor + real-time display
5. **Phase 3** - Assistant mode enhancements
6. **Polish** - Remove "free" language, test full flow

**Estimated total time:** 8-12 hours across 3 phases

---

**Ready for CC execution.** 🚀

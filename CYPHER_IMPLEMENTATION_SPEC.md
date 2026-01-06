# Cypher Implementation Specification
**ReCog Conversational Analysis Interface**

**Date:** 2026-01-06  
**Status:** Ready for Implementation (Updated for CC)  
**Priority:** High (Core UX Enhancement)  
**Estimated Time:** 8-12 hours

---

## ⚡ CC's Implementation Questions - ANSWERED

### Q1: Hash Routing vs React Router?
**A: Use hash-based routing (current ReCog standard)**

Current ReCog uses `#dashboard`, `#cases`, `#preflight/123` format. Cypher will adapt to this:

```javascript
// In CypherContext.jsx - Track current view via hash
const [currentView, setCurrentView] = useState(
  window.location.hash.replace('#', '').split('/')[0] || 'dashboard'
)

// Listen for hash changes
useEffect(() => {
  const handleHashChange = () => {
    const newView = window.location.hash.replace('#', '').split('/')[0]
    setCurrentView(newView)
  }
  
  window.addEventListener('hashchange', handleHashChange)
  return () => window.removeEventListener('hashchange', handleHashChange)
}, [])
```

```javascript
// In useCypherActions.js - Navigation via hash
const executeAction = async (actionType, params = {}) => {
  const handlers = {
    navigate_entities: () => { window.location.hash = '#entities' },
    navigate_findings: () => { window.location.hash = '#findings' },
    navigate_timeline: () => { window.location.hash = '#timeline' },
    navigate_insights: () => { window.location.hash = '#insights' },
    navigate_preflight: () => { window.location.hash = '#preflight' },
    // ... other handlers
  }
  // ...
}
```

### Q2: Backend Directory Structure?
**A: Put Cypher inside recog_engine (not sibling to it)**

```
C:\EhkoVaults\ReCog\_scripts\
├── recog_engine\
│   ├── cypher\                    # ← NEW: Cypher modules here
│   │   ├── __init__.py
│   │   ├── intent_classifier.py
│   │   ├── action_router.py
│   │   ├── response_formatter.py
│   │   └── prompts.py
│   ├── core\
│   ├── tier0.py
│   ├── insight_store.py
│   └── ...
└── server.py
```

**Why:** Cypher is part of ReCog's intelligence layer, can easily import existing stores (entity_registry, insight_store, case_store), follows established module pattern.

**Import pattern:**
```python
# In server.py
from recog_engine.cypher.intent_classifier import classify_intent
from recog_engine.cypher.action_router import CypherActionRouter
from recog_engine.cypher.prompts import load_cypher_system_prompt
```

### Q3: Start with Phase 1 Backend?
**A: Yes - correct approach**

Build API and action routing first, then wire up UI. Start with simplest action (entity correction) to prove the pipeline works, then add other handlers incrementally.

**Phase 1 execution order:**
1. Create `recog_engine/cypher/` directory structure
2. Implement `prompts.py` (system prompt strings)
3. Implement `intent_classifier.py` (pattern matching + LLM fallback)
4. Implement `action_router.py` (handle entity corrections first)
5. Implement `response_formatter.py` (ensure Cypher voice)
6. Add `/api/cypher/message` endpoint in `server.py`
7. Test with curl/Postman before touching frontend

---

## Executive Summary

### What We're Building
**Cypher** - A conversational analysis companion that replaces the fragmented Upload → Preflight → Dashboard workflow with a natural language interface that guides users through document analysis, learns from corrections, and proactively suggests insights.

### Why We're Building It
Current ReCog workflow has poor UX:
- ❌ "Preflight" is confusing developer jargon
- ❌ Multi-page workflow with unclear progression
- ❌ No real-time feedback during extraction
- ❌ No way to correct entities or provide feedback inline
- ❌ User has to manually check if processing is complete

### What Cypher Solves
- ✅ Natural language interface for all case operations
- ✅ Real-time processing narration and progress updates
- ✅ Inline corrections ("Webb isn't a person - it's our intranet")
- ✅ Proactive pattern detection and suggestions
- ✅ Contextual awareness of current page and case state
- ✅ Action routing (user intent → backend operations)

### Core Philosophy
**Cypher is a witness, not an interpreter.** It observes, documents, and reports patterns without judgment. It speaks in precise, economical language with a terminal aesthetic.

---

## Cypher's Identity

### Visual Identity
```
Name: Cypher (with 'y')
Subtitle: "terminal scribe"
Icon: ⟨⟩ (angle brackets, suggests code/cipher)
Color: Teal (#5fb3a1) - ReCog accent color
Font: JetBrains Mono (monospace, terminal feel)
Trigger: Button in top-right of every page
```

### Personality Traits
- **Analytical** - Speaks in facts, patterns, signals (not emotions)
- **Economical** - No fluff, direct communication, terminal-style brevity
- **Observant** - "I'm noticing...", "Pattern detected:", "Observation:"
- **Proactive** - Suggests next steps without being asked
- **Non-judgmental** - Reports findings, doesn't interpret motives
- **Precise** - Uses numbers, timestamps, concrete details

### Voice Examples

**✅ Good (Cypher-style):**
```
"Processing 8/23 documents. Found pattern: email thread."
"Webb appears 47 times. Not a person?"
"3 protocol deviations detected. Priority: high."
"Timeline gap: April 8-22. No communications logged."
"Suggestion: Review entities before proceeding."
"Noted. Webb excluded from future analysis."
```

**❌ Bad (Not Cypher):**
```
"I'm so sorry, I couldn't find that entity!"
"Hey! I'm super excited to analyze your docs! 🎉"
"Hmm, I'm not sure what you mean by that..."
"Great question! Let me think about that..."
"I'd be happy to help you with that request!"
```

### Communication Pattern
```
[Observation/Status] + [Data/Evidence] + [Optional: Suggestion/Question]

Examples:
"Extracted 74 insights. 12 require validation. Begin review?"
└─ What happened    └─ The numbers   └─ Next action

"Entity 'Meridian' tagged as person. Project name?"
└─ Current state         └─ The issue    └─ Clarification

"Processing complete. 28 entities identified. 6 need confirmation."
└─ Status           └─ Result           └─ Action needed
```

---

## Technical Architecture

### High-Level Flow
```
User types/drops files → Frontend (Cypher.jsx)
                              ↓
                    POST /api/cypher/message
                              ↓
                    Backend (server.py)
                    ├─ Classify intent
                    ├─ Route to action handler
                    ├─ Execute backend operations
                    ├─ Format response (Cypher voice)
                    └─ Return: { reply, actions, suggestions }
                              ↓
                    Frontend receives response
                    ├─ Display Cypher's reply
                    ├─ Execute UI actions (hash navigation)
                    ├─ Refresh affected components
                    └─ Show contextual buttons
```

### State Management Strategy

**Use React Context for Cypher state:**
```javascript
CypherContext provides:
- messages: Message[]          // Chat history
- isProcessing: boolean        // Cypher is thinking
- extractionStatus: Object     // Live processing updates
- currentCase: Object          // Active case context
- currentView: string          // Page user is on (from hash)
- addMessage()                 // Add to history
- sendMessage()                // Send to backend
- clearHistory()               // Reset chat
```

**Why Context?**
- Cypher needs to be accessible from any page
- Multiple components need extraction status (progress bars, badges)
- Avoids prop drilling through entire app

### Component Structure
```
C:\EhkoDev\recog-ui\src\
├── components\
│   ├── cypher\
│   │   ├── Cypher.jsx                 // Main Sheet component
│   │   ├── CypherTrigger.jsx          // Trigger button
│   │   ├── CypherMessage.jsx          // Individual message
│   │   ├── CypherSuggestions.jsx      // Action buttons
│   │   ├── CypherProgress.jsx         // Live processing UI
│   │   └── CypherTyping.jsx           // Typing indicator
│   └── ...
├── contexts\
│   └── CypherContext.jsx              // State management
├── hooks\
│   ├── useCypher.js                   // Access Cypher context
│   ├── useExtractionStatus.js         // Poll processing status
│   └── useCypherActions.js            // Execute UI actions
└── lib\
    ├── cypher-prompts.js              // System prompt definitions
    └── cypher-actions.js              // Action execution logic
```

---

## Backend Implementation

### Directory Structure (Updated)

```
C:\EhkoVaults\ReCog\_scripts\
├── recog_engine\
│   ├── cypher\                    # ← NEW MODULE
│   │   ├── __init__.py
│   │   ├── intent_classifier.py   # Intent classification (regex + LLM)
│   │   ├── action_router.py       # CypherActionRouter class
│   │   ├── response_formatter.py  # Cypher voice enforcement
│   │   └── prompts.py             # System prompts
│   ├── core\
│   ├── tier0.py
│   ├── insight_store.py
│   ├── entity_registry.py
│   └── ...
└── server.py                       # Add /api/cypher/message endpoint
```

### New API Endpoint: /api/cypher/message

**Request:**
```json
{
  "message": "Webb isn't a person, it's our intranet",
  "case_id": "d72938f2-0060-4622-b100-8cafa628fa77",
  "context": {
    "current_view": "entities",           // Page user is on (from hash)
    "processing_status": "complete",      // or "processing", "idle"
    "extraction_progress": {              // If processing
      "current": 8,
      "total": 23,
      "current_doc": "interview_seattle.txt"
    },
    "last_action": "extraction",          // User's last action
    "visible_entities": ["Webb", "..."]   // If on entities page
  }
}
```

**Response:**
```json
{
  "reply": "Acknowledged. Webb removed from entity registry. Added to technical systems blocklist. Future documents will reflect this classification.",
  "actions": [
    {
      "type": "entity_remove",
      "entity_id": "uuid-here",
      "entity_name": "Webb"
    },
    {
      "type": "blocklist_add",
      "term": "Webb",
      "category": "technical_term"
    }
  ],
  "ui_updates": {
    "refresh": ["entities_page", "entity_stats"],
    "navigate": null,
    "highlight": null
  },
  "suggestions": [
    {
      "text": "Review other entities",
      "action": "navigate_entities",
      "icon": "Users"
    },
    {
      "text": "Continue to findings",
      "action": "navigate_findings",
      "icon": "Lightbulb"
    }
  ],
  "metadata": {
    "intent": "entity_correction",
    "confidence": 0.95,
    "processing_time_ms": 234
  }
}
```

### Intent Classification System

**Intent Categories:**
```python
INTENTS = {
    "entity_correction": "Remove/reclassify entity",
    "filter_request": "Show subset of data",
    "navigation": "Go to specific page/view",
    "analysis_query": "Answer question about data",
    "processing_control": "Start/stop/pause extraction",
    "clarification": "Explain something",
    "file_upload": "Add documents to case",
    "pattern_feedback": "Confirm/reject suggested pattern"
}
```

**Classification Strategy: Hybrid (Patterns + LLM)**

```python
# recog_engine/cypher/intent_classifier.py

import re
import json
from anthropic import Anthropic

# Step 1: Try regex patterns (fast, free)
INTENT_PATTERNS = {
    "entity_correction": [
        r"(\w+) (isn't|is not|ain't) (a |an )?(person|name|entity)",
        r"(\w+) is (our|a|an|the) (intranet|system|tool|company|project)",
        r"remove (\w+) from entities",
        r"(\w+) should be (a |an )?(location|organization|system)",
    ],
    "filter_request": [
        r"(focus on|show|filter by) (\w+)",
        r"(only|just) show (me )?(\w+)",
        r"(documents|insights|entities) (about|from|related to) (\w+)",
    ],
    "navigation": [
        r"(show|open|go to) (me )?(the )?(\w+) (page|view|tab)",
        r"(take me to|navigate to) (\w+)",
        r"(view|see) (the )?(timeline|findings|entities|insights)",
    ],
    "analysis_query": [
        r"(are there|show me|find) .*(gaps|patterns|anomalies)",
        r"what (happened|occurred|changed) (in|on|during) (\w+)",
        r"who (is|was) (involved|mentioned|responsible)",
        r"how many (\w+)",
    ],
    "file_upload": [
        r"(analyze|process|upload|add) (these |the )?documents",
        r"(start|begin) (analysis|processing|extraction)",
    ],
}

def extract_entities_from_pattern(pattern, message):
    """Extract named entities from regex match"""
    match = re.search(pattern, message, re.IGNORECASE)
    if not match:
        return {}
    
    groups = match.groups()
    # First group is usually the entity name
    return {"name": groups[0] if groups else None}

def classify_intent(message, context, anthropic_client=None):
    """
    Classify user intent using hybrid approach:
    1. Try pattern matching first (fast, free)
    2. Fallback to LLM for ambiguous cases
    """
    # Try pattern matching first
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message, re.IGNORECASE):
                entities = extract_entities_from_pattern(pattern, message)
                return intent, entities, 1.0  # High confidence
    
    # Fallback to LLM classification
    if anthropic_client:
        return llm_classify_intent(message, context, anthropic_client)
    
    # No LLM available, return unknown
    return "clarification", {}, 0.0

def llm_classify_intent(message, context, anthropic_client):
    """Use Anthropic API to classify ambiguous intents"""
    prompt = f"""Classify this user message into one of these intents:
    {', '.join(INTENTS.keys())}
    
    User message: "{message}"
    Current context: {json.dumps(context)}
    
    Respond with JSON only: {{"intent": "...", "entities": {{...}}, "confidence": 0.0-1.0}}
    """
    
    # Call Anthropic API (use Haiku for cost efficiency)
    response = anthropic_client.messages.create(
        model="claude-haiku-4.5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse response
    try:
        result = json.loads(response.content[0].text)
        return result["intent"], result.get("entities", {}), result.get("confidence", 0.5)
    except (json.JSONDecodeError, KeyError) as e:
        # Fallback to clarification if parsing fails
        return "clarification", {}, 0.0
```

### Action Router

```python
# recog_engine/cypher/action_router.py

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CypherActionRouter:
    """Routes classified intents to backend operations"""
    
    def __init__(self, db, entity_registry, insight_store, case_store):
        self.db = db
        self.entity_registry = entity_registry
        self.insight_store = insight_store
        self.case_store = case_store
    
    async def execute(self, intent, entities, context):
        """Main routing function"""
        handlers = {
            "entity_correction": self.handle_entity_correction,
            "filter_request": self.handle_filter,
            "navigation": self.handle_navigation,
            "analysis_query": self.handle_query,
            "file_upload": self.handle_file_upload,
            "pattern_feedback": self.handle_pattern_feedback,
        }
        
        handler = handlers.get(intent)
        if not handler:
            return self.handle_unknown(intent, entities, context)
        
        try:
            return await handler(entities, context)
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return {
                "reply": "Operation failed. System error logged.",
                "actions": [],
                "suggestions": []
            }
    
    async def handle_entity_correction(self, entities, context):
        """
        User: "Webb isn't a person"
        Entities: {"name": "Webb", "negation": True}
        """
        entity_name = entities.get("name")
        correction_type = entities.get("correction_type", "not_a_person")
        
        if not entity_name:
            return {
                "reply": "Entity name not detected. Rephrase?",
                "actions": [],
                "suggestions": [
                    {"text": "View all entities", "action": "navigate_entities"}
                ]
            }
        
        # Find entity in registry
        entity = self.entity_registry.find_by_name(entity_name)
        
        if not entity:
            return {
                "reply": f"Entity '{entity_name}' not found in registry. Already removed?",
                "actions": [],
                "suggestions": [
                    {"text": "View all entities", "action": "navigate_entities"}
                ]
            }
        
        # Remove from registry
        self.entity_registry.remove(entity["id"])
        
        # Add to blocklist
        self.entity_registry.add_to_blocklist(
            term=entity_name,
            category="user_correction",
            reason=f"User stated: {correction_type}"
        )
        
        # Log correction for learning
        self.db.execute("""
            INSERT INTO user_corrections (entity_name, correction_type, timestamp)
            VALUES (?, ?, ?)
        """, (entity_name, correction_type, datetime.now()))
        
        return {
            "reply": f"Acknowledged. {entity_name} removed from entity registry. "
                    f"Added to blocklist. Future documents will reflect this.",
            "actions": [
                {"type": "entity_remove", "entity_id": entity["id"], "entity_name": entity_name},
                {"type": "blocklist_add", "term": entity_name}
            ],
            "ui_updates": {
                "refresh": ["entities_page", "entity_stats"],
                "navigate": None
            },
            "suggestions": [
                {"text": "Review other entities", "action": "navigate_entities", "icon": "Users"},
                {"text": "Continue to findings", "action": "navigate_findings", "icon": "Lightbulb"}
            ]
        }
    
    async def handle_filter(self, entities, context):
        """
        User: "Focus on Seattle documents"
        Entities: {"focus": "Seattle", "type": "location"}
        """
        focus_term = entities.get("focus")
        filter_type = entities.get("type", "any")
        
        # Build filter parameters
        filters = {"query": focus_term}
        if filter_type in ["location", "person", "organization"]:
            filters["entity_type"] = filter_type
        
        # Get filtered results
        insights = self.insight_store.search(filters)
        
        return {
            "reply": f"Filtered to {len(insights)} insights related to '{focus_term}'. "
                    f"Displaying results.",
            "actions": [
                {"type": "apply_filter", "filters": filters}
            ],
            "ui_updates": {
                "navigate": "insights",
                "highlight": focus_term
            },
            "suggestions": [
                {"text": "Clear filter", "action": "clear_filter"},
                {"text": "Export results", "action": "export_filtered"}
            ]
        }
    
    async def handle_navigation(self, entities, context):
        """Simple navigation handler"""
        target = entities.get("target", "").lower()
        
        nav_map = {
            "entities": "entities",
            "insights": "insights",
            "findings": "findings",
            "timeline": "timeline",
            "dashboard": "dashboard"
        }
        
        view = nav_map.get(target)
        if not view:
            return {
                "reply": f"Navigation target '{target}' not recognized.",
                "actions": [],
                "suggestions": []
            }
        
        return {
            "reply": f"Displaying {view} view.",
            "actions": [],
            "ui_updates": {
                "navigate": view
            },
            "suggestions": []
        }
    
    async def handle_unknown(self, intent, entities, context):
        """Fallback for unknown intents"""
        return {
            "reply": "Intent unclear. Rephrase?",
            "actions": [],
            "suggestions": [
                {"text": "View entities", "action": "navigate_entities"},
                {"text": "View insights", "action": "navigate_insights"}
            ]
        }
```

### Response Formatter (Cypher Voice)

```python
# recog_engine/cypher/response_formatter.py

from anthropic import Anthropic
import json

def is_cypher_style(text):
    """
    Check if response already follows Cypher's pattern
    Simple heuristic: short, no apologies, no questions
    """
    bad_patterns = [
        "sorry", "i'm ", "i am ", "i'd be", "i would",
        "great question", "let me think", "hmm"
    ]
    return not any(pattern in text.lower() for pattern in bad_patterns)

def format_cypher_response(intent, result, context, anthropic_client=None):
    """
    Ensures all responses match Cypher's voice/personality
    Uses LLM to rewrite responses if needed
    """
    
    # If response already follows Cypher pattern, return as-is
    if is_cypher_style(result["reply"]):
        return result
    
    # No LLM available, return as-is
    if not anthropic_client:
        return result
    
    # Otherwise, rewrite using Cypher system prompt
    from .prompts import load_cypher_system_prompt
    cypher_prompt = load_cypher_system_prompt(context)
    
    rewrite_request = f"""Rewrite this response in Cypher's voice:

Original: {result["reply"]}

Context: {json.dumps(context)}

Remember Cypher's pattern: [Observation] + [Data] + [Optional: Suggestion]
Be precise, economical, terminal-style.
"""
    
    response = anthropic_client.messages.create(
        model="claude-sonnet-4.5-20250929",
        max_tokens=300,
        system=cypher_prompt,
        messages=[{"role": "user", "content": rewrite_request}]
    )
    
    result["reply"] = response.content[0].text
    return result
```

### Cypher System Prompt

```python
# recog_engine/cypher/prompts.py

CYPHER_SYSTEM_PROMPT = """You are Cypher, the terminal scribe for ReCog document intelligence platform.

IDENTITY:
You are an analytical observer who documents and decodes information from documents. You witness patterns without judgment. You are precise, economical, and speak in terminal-style language.

CORE PRINCIPLES:
1. Witness, don't interpret - Report facts and patterns, not motives or feelings
2. Data-driven communication - Lead with numbers, timestamps, concrete evidence
3. Terminal aesthetic - Brief, precise, technical vocabulary
4. Proactive guidance - Suggest next steps when obvious
5. Clarity over courtesy - "Entity removed." not "I've successfully removed the entity for you!"

COMMUNICATION PATTERN:
[Observation/Status] + [Data/Evidence] + [Optional: Question/Suggestion]

Structure every response like this:
- Start with what happened or current state
- Provide specific numbers or evidence
- End with a question or suggested action (only if relevant)

EXAMPLES OF GOOD RESPONSES:
✓ "74 insights extracted. 18 flagged high priority. Review now?"
✓ "Entity 'Project' appears 308 times. Generic term. Exclude?"
✓ "Timeline gap detected: April 8-22. No documents. Investigate?"
✓ "Processing: 15/23 documents. Current: interview_seattle.txt"
✓ "Pattern identified: Email thread spanning 6 documents. Extract?"
✓ "Acknowledged. Webb removed. Added to blocklist."

EXAMPLES OF BAD RESPONSES:
✗ "I'm excited to help you analyze these documents!"
✗ "Sorry, I couldn't find what you were looking for :("
✗ "That's a great question! Let me think about it..."
✗ "I'd be happy to help you with that request!"
✗ "Just a moment while I process that for you..."

VOCABULARY GUIDELINES:
Use: detected, identified, extracted, flagged, processed, observed, noted
Avoid: found, discovered, realized, understood, think, feel, believe

Use: high priority, flagged, requires attention, anomaly detected
Avoid: important, concerning, worrying, interesting, fascinating

Use numbers and percentages: "74 insights", "18 high priority (24%)", "6-day gap"
Avoid vague terms: "many insights", "some priorities", "a gap"

HANDLING USER CORRECTIONS:
When user corrects entities or provides feedback:
- Acknowledge briefly: "Noted." or "Acknowledged."
- State what action was taken: "Webb removed from registry."
- State future impact: "Future documents will reflect this."
- NO apologies, NO excessive confirmation

Example:
User: "Webb isn't a person - it's our intranet"
Good: "Acknowledged. Webb removed from entity registry. Added to technical systems blocklist. Future documents will reflect this classification."
Bad: "Oh I'm so sorry for the confusion! I've now removed Webb from the entities list and made sure it won't appear again. Is there anything else I can help with?"

CONTEXTUAL AWARENESS:
You have access to:
- Case title and description
- Current processing status (idle/processing/complete)
- What page the user is viewing
- Recent actions taken
- Extraction progress (if processing)

Use this context to make responses relevant:
- If on entities page: Reference entity counts, suggest reviews
- If processing: Provide live updates, estimated completion
- If on timeline: Reference dates, gaps, patterns

CAPABILITIES YOU CAN EXECUTE:
1. Entity corrections (remove, reclassify, add to blocklist)
2. Apply filters (by person, location, date, term)
3. Navigate to pages (insights, entities, timeline, findings)
4. Highlight patterns (flag anomalies, gaps, clusters)
5. Create findings (promote insights to verified findings)
6. Timeline analysis (identify gaps, correlations)
7. Start/monitor document processing

WHEN UNCERTAIN:
If user request is ambiguous, ask for clarification directly:
"Clarify: Remove 'Torres' or 'Torres Lab'?"
"Which Seattle document? 3 available."

Don't say: "I'm not quite sure what you mean, could you please provide more details?"

PROCESSING NARRATION:
During document extraction, provide live updates:
"Doc 8/23: interview_seattle.txt"
"• 3 insights extracted"
"• Entity detected: Dr. Sarah Chen (HIGH confidence)"
"• Pattern match: data handling +1"

Keep updates brief. One line per significant event.

CURRENT SESSION CONTEXT:
Case: {case_title}
Description: {case_context}
Status: {processing_status}
Current View: {current_view}
Documents: {document_count}

Remember: You are Cypher - precise, observant, economical. Terminal scribe, not chatbot.
"""

def load_cypher_system_prompt(context):
    """Inject session context into system prompt"""
    return CYPHER_SYSTEM_PROMPT.format(
        case_title=context.get("case_title", "Unknown"),
        case_context=context.get("case_context", "No description"),
        processing_status=context.get("processing_status", "idle"),
        current_view=context.get("current_view", "dashboard"),
        document_count=context.get("document_count", 0)
    )
```

### Server Endpoint Implementation

```python
# In C:\EhkoVaults\ReCog\_scripts\server.py

from recog_engine.cypher.intent_classifier import classify_intent
from recog_engine.cypher.action_router import CypherActionRouter
from recog_engine.cypher.response_formatter import format_cypher_response
from anthropic import Anthropic

# Initialize Anthropic client for LLM fallback
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

@app.route('/api/cypher/message', methods=['POST'])
async def cypher_message():
    """Handle Cypher conversational interface messages"""
    try:
        data = request.json
        message = data.get("message", "")
        case_id = data.get("case_id")
        context = data.get("context", {})
        
        # Classify intent
        intent, entities, confidence = classify_intent(
            message, 
            context, 
            anthropic_client
        )
        
        # Route to action handler
        router = CypherActionRouter(
            db=get_db(),
            entity_registry=entity_registry,
            insight_store=insight_store,
            case_store=case_store
        )
        
        result = await router.execute(intent, entities, context)
        
        # Format response in Cypher voice
        result = format_cypher_response(
            intent, 
            result, 
            context, 
            anthropic_client
        )
        
        # Add metadata
        result["metadata"] = {
            "intent": intent,
            "confidence": confidence,
            "processing_time_ms": 0  # TODO: track timing
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Cypher message failed: {e}")
        return jsonify({
            "reply": "Communication error. System malfunction logged.",
            "actions": [],
            "suggestions": []
        }), 500

@app.route('/api/extraction/status/<case_id>', methods=['GET'])
def extraction_status(case_id):
    """Poll extraction processing status for real-time updates"""
    try:
        # Query current processing state
        status = get_case_processing_status(case_id)
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Status poll failed: {e}")
        return jsonify({"status": "unknown"}), 500
```

---

## Frontend Implementation

### Context: CypherContext.jsx (Updated for Hash Routing)

```jsx
// C:\EhkoDev\recog-ui\src\contexts\CypherContext.jsx

import { createContext, useContext, useState, useEffect } from 'react'
import { sendCypherMessage, getExtractionStatus } from '@/lib/api'

const CypherContext = createContext(null)

export function CypherProvider({ children, caseId }) {
  const [messages, setMessages] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [extractionStatus, setExtractionStatus] = useState(null)
  const [isOpen, setIsOpen] = useState(false)
  
  // Track current view from hash (updated for hash routing)
  const [currentView, setCurrentView] = useState(
    window.location.hash.replace('#', '').split('/')[0] || 'dashboard'
  )
  
  // Listen for hash changes
  useEffect(() => {
    const handleHashChange = () => {
      const newView = window.location.hash.replace('#', '').split('/')[0]
      setCurrentView(newView)
    }
    
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])
  
  // Poll extraction status if processing
  useEffect(() => {
    if (!caseId) return
    
    const pollInterval = setInterval(async () => {
      try {
        const status = await getExtractionStatus(caseId)
        setExtractionStatus(status)
        
        // If extraction completed, add Cypher notification
        if (status.status === 'complete' && extractionStatus?.status === 'processing') {
          addCypherMessage(
            `Processing complete. ${status.insights_extracted} insights extracted. ` +
            `${status.entities_identified} entities identified. Review findings?`,
            [
              { text: 'View findings', action: 'navigate_findings', icon: 'Lightbulb' },
              { text: 'Review entities', action: 'navigate_entities', icon: 'Users' }
            ]
          )
        }
      } catch (error) {
        console.error('Failed to poll extraction status:', error)
      }
    }, 2000) // Poll every 2 seconds
    
    return () => clearInterval(pollInterval)
  }, [caseId, extractionStatus?.status])
  
  const addUserMessage = (content) => {
    setMessages(prev => [...prev, {
      role: 'user',
      content,
      timestamp: Date.now()
    }])
  }
  
  const addCypherMessage = (content, suggestions = []) => {
    setMessages(prev => [...prev, {
      role: 'assistant',
      content,
      suggestions,
      timestamp: Date.now()
    }])
  }
  
  const sendMessage = async (text) => {
    if (!text.trim()) return
    
    addUserMessage(text)
    setIsProcessing(true)
    
    try {
      const context = {
        current_view: currentView,
        processing_status: extractionStatus?.status || 'idle',
        extraction_progress: extractionStatus,
        case_id: caseId
      }
      
      const response = await sendCypherMessage(text, caseId, context)
      
      addCypherMessage(response.reply, response.suggestions)
      
      // Execute UI actions
      if (response.actions) {
        // Actions are executed via UI updates or direct API calls
        response.actions.forEach(action => {
          if (action.type === 'entity_remove') {
            window.dispatchEvent(new CustomEvent('refresh-entities'))
          }
        })
      }
      
      // Refresh UI components
      if (response.ui_updates?.refresh) {
        response.ui_updates.refresh.forEach(component => {
          window.dispatchEvent(new CustomEvent(`refresh-${component}`))
        })
      }
      
      // Navigate if requested (hash-based)
      if (response.ui_updates?.navigate) {
        window.location.hash = `#${response.ui_updates.navigate}`
      }
      
    } catch (error) {
      console.error('Cypher message failed:', error)
      addCypherMessage(
        'Communication error. Request failed to process.',
        [{ text: 'Retry', action: 'retry_last' }]
      )
    } finally {
      setIsProcessing(false)
    }
  }
  
  const clearHistory = () => {
    setMessages([])
  }
  
  const value = {
    messages,
    isProcessing,
    extractionStatus,
    sendMessage,
    clearHistory,
    isOpen,
    setIsOpen,
    currentView
  }
  
  return (
    <CypherContext.Provider value={value}>
      {children}
    </CypherContext.Provider>
  )
}

export function useCypher() {
  const context = useContext(CypherContext)
  if (!context) {
    throw new Error('useCypher must be used within CypherProvider')
  }
  return context
}
```

### Hook: useCypherActions.js (Updated for Hash Routing)

```jsx
// C:\EhkoDev\recog-ui\src\hooks\useCypherActions.js

import { useToast } from '@/components/ui/use-toast'

export function useCypherActions() {
  const { toast } = useToast()
  
  const executeAction = async (actionType, params = {}) => {
    const handlers = {
      // Hash-based navigation
      navigate_findings: () => { window.location.hash = '#findings' },
      navigate_entities: () => { window.location.hash = '#entities' },
      navigate_timeline: () => { window.location.hash = '#timeline' },
      navigate_insights: () => { window.location.hash = '#insights' },
      navigate_preflight: () => { window.location.hash = '#preflight' },
      navigate_dashboard: () => { window.location.hash = '#dashboard' },
      
      apply_filter: (params) => {
        // Set filter in hash with query params
        const filterQuery = encodeURIComponent(params.filters.query)
        window.location.hash = `#insights?filter=${filterQuery}`
      },
      
      clear_filter: () => {
        window.location.hash = '#insights'
      },
      
      confirm_preflight: async (params) => {
        // Trigger preflight confirmation
        // await confirmPreflight(params.session_id)
        toast({
          title: "Processing started",
          description: "Cypher will notify you when complete."
        })
      },
      
      entity_remove: async (params) => {
        // Already handled by backend, just refresh UI
        window.dispatchEvent(new CustomEvent('refresh-entities'))
      },
      
      highlight_timeline_gaps: (params) => {
        window.location.hash = '#timeline'
        // Store gaps in state to highlight them
        window.dispatchEvent(new CustomEvent('highlight-gaps', {
          detail: params.gaps
        }))
      }
    }
    
    const handler = handlers[actionType]
    if (!handler) {
      console.warn(`Unknown action type: ${actionType}`)
      return
    }
    
    await handler(params)
  }
  
  const refreshComponents = (componentNames) => {
    componentNames.forEach(name => {
      window.dispatchEvent(new CustomEvent(`refresh-${name}`))
    })
  }
  
  return { executeAction, refreshComponents }
}
```

### API Client Update

```javascript
// C:\EhkoDev\recog-ui\src\lib\api.js

// Add these functions to existing api.js

export async function sendCypherMessage(message, caseId, context) {
  const response = await fetch('/api/cypher/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      case_id: caseId,
      context
    })
  })
  
  if (!response.ok) {
    throw new Error('Cypher message failed')
  }
  
  return response.json()
}

export async function getExtractionStatus(caseId) {
  const response = await fetch(`/api/extraction/status/${caseId}`)
  
  if (!response.ok) {
    throw new Error('Status poll failed')
  }
  
  return response.json()
}
```

---

## Implementation Phases

### Phase 1: Backend Foundation (3-4 hours) ← START HERE
**Goal:** Get Cypher API working with basic intent classification

**Tasks:**
1. Create `C:\EhkoVaults\ReCog\_scripts\recog_engine\cypher\` directory
2. Create `__init__.py`, `prompts.py`, `intent_classifier.py`, `action_router.py`, `response_formatter.py`
3. Implement `/api/cypher/message` endpoint in `server.py`
4. Implement `/api/extraction/status/<case_id>` endpoint
5. Test via curl/Postman:
   ```bash
   curl -X POST http://localhost:5100/api/cypher/message \
     -H "Content-Type: application/json" \
     -d '{"message": "Webb isn'\''t a person", "case_id": "test", "context": {}}'
   ```

**Acceptance Criteria:**
- ✅ Directory structure created
- ✅ Endpoint returns proper JSON structure
- ✅ Intent classification works for "Webb isn't a person"
- ✅ Entity corrections execute (check logs/database)
- ✅ Response follows Cypher voice

### Phase 2: Frontend Core (2-3 hours)
**Goal:** Get Cypher UI displaying and sending messages

**Tasks:**
1. Create `C:\EhkoDev\recog-ui\src\contexts\CypherContext.jsx`
2. Create `C:\EhkoDev\recog-ui\src\components\cypher\` directory
3. Create Cypher.jsx, CypherMessage.jsx, CypherTyping.jsx
4. Create useCypher.js, useCypherActions.js hooks
5. Update api.js with sendCypherMessage(), getExtractionStatus()
6. Add Cypher trigger button to navigation
7. Test basic chat flow

**Acceptance Criteria:**
- ✅ Cypher Sheet opens from trigger button
- ✅ Messages display correctly (user vs Cypher)
- ✅ Input sends to backend
- ✅ Typing indicator shows
- ✅ Terminal aesthetic matches ReCog theme

### Phase 3: Action Execution (2-3 hours)
**Goal:** Cypher actions work (navigate, filter, update UI)

**Tasks:**
1. Wire up action execution in CypherContext
2. Create CypherSuggestions.jsx
3. Implement hash-based navigation
4. Test entity corrections refresh UI
5. Test filters apply correctly

**Acceptance Criteria:**
- ✅ Hash navigation works (#entities, #insights)
- ✅ Entity corrections refresh UI
- ✅ Suggestion buttons execute actions
- ✅ No JavaScript errors

### Phase 4: Live Processing (2-3 hours)
**Goal:** Cypher narrates extraction in real-time

**Tasks:**
1. Create CypherProgress.jsx
2. Implement extraction status polling
3. Add live updates during processing
4. Add completion notification
5. Test full upload → process → complete flow

**Acceptance Criteria:**
- ✅ Progress bar updates live
- ✅ Current document displays
- ✅ Completion notification triggers
- ✅ Badge shows "8/23" count

### Phase 5: Polish (1-2 hours)
**Goal:** Handle errors and edge cases

**Tasks:**
1. Add error handling
2. Add retry functionality
3. Add keyboard shortcuts
4. Add empty states
5. Test edge cases

**Acceptance Criteria:**
- ✅ Errors display gracefully
- ✅ Retry works
- ✅ Keyboard shortcuts work
- ✅ No console errors

---

## Files Reference

### Files to Create

**Backend:**
```
C:\EhkoVaults\ReCog\_scripts\recog_engine\cypher\
├── __init__.py
├── intent_classifier.py       # Intent classification logic
├── action_router.py            # CypherActionRouter class
├── response_formatter.py       # Cypher voice formatting
└── prompts.py                  # System prompts
```

**Frontend:**
```
C:\EhkoDev\recog-ui\src\
├── components\cypher\
│   ├── Cypher.jsx                  # Main Sheet component
│   ├── CypherMessage.jsx           # Individual message
│   ├── CypherSuggestions.jsx       # Action buttons
│   ├── CypherProgress.jsx          # Live progress UI
│   └── CypherTyping.jsx            # Typing indicator
├── contexts\
│   └── CypherContext.jsx           # State management
└── hooks\
    ├── useCypher.js                # Access context
    └── useCypherActions.js         # Execute actions
```

### Files to Modify

**Backend:**
```
C:\EhkoVaults\ReCog\_scripts\server.py
- Add POST /api/cypher/message endpoint
- Add GET /api/extraction/status/<case_id> endpoint
```

**Frontend:**
```
C:\EhkoDev\recog-ui\src\
├── App.jsx
│   └── Wrap in <CypherProvider>
│   └── Add <Cypher /> trigger button
├── lib\api.js
│   └── Add sendCypherMessage()
│   └── Add getExtractionStatus()
└── components\pages\
    └── EntitiesPage.jsx            # Add refresh event listener
```

---

## Success Criteria

**Cypher is successful when:**

1. ✅ User can correct entities naturally ("Webb isn't a person")
2. ✅ User gets real-time processing feedback
3. ✅ User can navigate via natural language ("Show me the timeline")
4. ✅ User gets proactive suggestions
5. ✅ Terminal aesthetic is consistent (monospace, teal, brief)
6. ✅ Performance is smooth (instant messages, no lag)

---

## Testing Checklist

**Manual Tests:**
1. Entity correction: "Webb isn't a person" → Entity removed
2. Navigation: "Show me entities" → Hash changes to #entities
3. Filter: "Focus on Seattle" → Insights filtered
4. Processing: Upload docs → Progress bar → Completion notification
5. Edge cases: No case, API timeout, invalid input

---

## Handoff to CC

**Start with Phase 1 (Backend Foundation):**
1. Create `recog_engine/cypher/` directory structure
2. Implement `prompts.py` first (just strings)
3. Implement `intent_classifier.py` (regex patterns)
4. Implement `action_router.py` (entity_correction handler)
5. Add `/api/cypher/message` endpoint in `server.py`
6. Test with curl before moving to frontend

**Ready to begin Phase 1!** 🚀⟨⟩

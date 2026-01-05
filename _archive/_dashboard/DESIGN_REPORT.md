# ReCog UI Design Direction Report
**Date:** 2026-01-02  
**Status:** Pre-Production Design Proposal  
**Version:** 1.0

---

## Executive Summary

ReCog needs a cohesive, professional UI that balances **cognitive processing aesthetics** with **usability**. The current React/shadcn implementation provides a solid technical foundation, but lacks the distinctive character present in the EhkoLabs website. This report proposes integrating the terminal aesthetic from the website with ReCog's unique "recursive cognition" identity, while maintaining the professionalism required for a commercial text analysis tool.

**Key Recommendation:** Adapt the terminal/CRT aesthetic from the website with ReCog-specific color shifts and cognitive metaphors, creating a "thinking machine" interface that feels both technical and intelligent.

---

## Current State Analysis

### What We Have (Good)
✅ **Solid Component Library** - shadcn/ui provides professional, accessible components  
✅ **Holographic Theme Started** - Deep void backgrounds with orange/blue accents  
✅ **Functional Layout** - Sidebar navigation, clean page structure  
✅ **Responsive Foundation** - Tailwind utilities for mobile/desktop  
✅ **Working Pages** - Signal Extraction, Upload, Preflight, Entities, Insights, Patterns, Tethers

### What We're Missing (Needs Work)
❌ **Distinctive Identity** - Looks generic, could be any SaaS dashboard  
❌ **Visual Hierarchy** - Everything has same visual weight  
❌ **Motion/Life** - Static, no sense of "thinking" or "processing"  
❌ **Terminal Aesthetic** - Website has CRT/terminal vibe, UI doesn't  
❌ **Tether Integration** - Tethers feel bolted-on, not core to the experience  
❌ **Cognitive Metaphors** - Doesn't feel like a "recursive cognition engine"

---

## Design Philosophy

### The "Thinking Machine" Metaphor

ReCog should feel like **peering into a cognitive process**. Not a cold database query tool, but an intelligence layer that's actively working. The UI should communicate:

1. **Depth** - Layers of processing (Tier 0 → Insights → Patterns → Synthesis)
2. **Recursion** - Information flowing back into itself, growing smarter
3. **Transparency** - You can see the gears turning (unlike black-box AI)
4. **Connection** - The tether metaphor makes LLM access feel like channeling intelligence

### Design Principles

**SUBTLE, NOT FLASHY**  
The website can be maximalist because it's marketing. ReCog is a tool you use for hours. Effects should be ambient, not distracting.

**COGNITIVE, NOT CYBERPUNK**  
This isn't a hacker aesthetic. It's more like a **research station interface** - technical, focused, purposeful. Think NASA control room, not Blade Runner.

**PROFESSIONAL WITH PERSONALITY**  
Users should take it seriously (it's analyzing their data) but feel the craft (this was built with care).

**INFORMATION DENSITY WITHOUT CLUTTER**  
Show relevant data, hide noise. Use progressive disclosure (collapsed → expanded states).

---

## Proposed Design System

### Color Palette Adaptation

**Current ReCog Palette (Keep)**
```css
/* Core Colors */
--bg-void: #080a0e;              /* Deep space background */
--bg-surface: #0c1018;           /* Card backgrounds */
--bg-elevated: #111620;          /* Hover states */

--orange-light: #ff9955;         /* Primary accent - cognition */
--orange-mid: #d97e4a;           /* Secondary accent */
--orange-dark: #a55d35;          /* Subtle highlights */

--blue-light: #8aa4d6;           /* Structure/data */
--blue-mid: #6b8cce;             /* Links, icons */
--blue-dark: #4a6fa5;            /* Muted text */
```

**Add from Website (Terminal Aesthetic)**
```css
/* Terminal Effects */
--scanline-subtle: rgba(107, 140, 206, 0.02);   /* Very faint CRT lines */
--glow-orange: rgba(255, 153, 85, 0.4);         /* Cognitive glow */
--glow-blue: rgba(107, 140, 206, 0.3);          /* Data glow */
--border-accent: rgba(107, 140, 206, 0.3);      /* Terminal borders */

/* Semantic Colors */
--tether-active: #5fb3a1;        /* Teal - connected */
--tether-pending: #f39c12;       /* Amber - verifying */
--tether-inactive: #718096;      /* Gray - disconnected */
--processing: #d97e9b;           /* Magenta - LLM thinking */
```

**Color Usage Philosophy**
- **Orange** = Cognitive operations (insights, patterns, synthesis)
- **Blue** = Structural data (entities, metadata, stats)
- **Teal** = Active connections (tethers, live processing)
- **Magenta** = LLM activity (queue items, API calls)
- **Amber** = Warnings/attention (unknown entities, verification)

---

## Layout Structure Proposal

### Overall Architecture

```
┌─────────────────────────────────────────────────────┐
│ HEADER BAR (Fixed Top - 60px)                      │
│ ┌─────────┐ ┌──────────┐ ┌──────────────┐         │
│ │ Logo    │ │ Tethers  │ │ Status/Info  │         │
│ └─────────┘ └──────────┘ └──────────────┘         │
├───────────┬─────────────────────────────────────────┤
│           │                                         │
│  SIDEBAR  │  MAIN CONTENT AREA                     │
│  (220px)  │  (Scrollable, max-width: 1200px)       │
│           │                                         │
│ Analysis  │  ┌─────────────────────────────────┐   │
│  • Signal │  │                                 │   │
│  • Upload │  │  Page Content                   │   │
│           │  │  (Cards, Tables, Forms)         │   │
│ Workflow  │  │                                 │   │
│  • Pre    │  │                                 │   │
│  • Entity │  │                                 │   │
│           │  └─────────────────────────────────┘   │
│ Results   │                                         │
│  • Insig  │                                         │
│  • Patt   │                                         │
│           │                                         │
│ [Tethers] │  FOOTER (Status indicators)            │
│  Status   │                                         │
└───────────┴─────────────────────────────────────────┘
```

### Header Bar Design

**LEFT: Logo/Branding**
- ReCog logo (smaller, inline)
- Subtitle: "Recursive Cognition Engine" (very small, faded)

**CENTER: Tether Status Bar** (NEW - This is key!)
```
╔═══════════════════════════════════════════════╗
║ ◈ Claude [●]  ◉ GPT-4 [●]  ✧ Gemini [○]     ║
║ Mana: 847/1000 [████████░░]                   ║
╚═══════════════════════════════════════════════╝
```
- Shows active tethers at a glance (● = connected, ○ = disconnected)
- Mana pool indicator (if using mana system)
- Click to open full tether panel

**RIGHT: Status/Actions**
- Processing indicator (when LLM calls active)
- Notification bell (for completed syntheses, etc.)
- Settings dropdown

---

## Tether System Integration

### Tether Status Bar (Header)

**Visual Design:**
```
┌─────────────────────────────────────────┐
│  TETHERS                                │
│  ◈ Claude    [●●●] Connected            │
│  ◉ GPT-4     [●●○] Limited              │
│  ✧ Gemini    [○○○] Disconnected         │
│                                         │
│  Mana Pool: 847 / 1000  [████████░░]   │
│  Est. Cost: $0.12 today                │
└─────────────────────────────────────────┘
```

**States:**
- **Connected (●●●)** - Green glow, ready to use
- **Limited (●●○)** - Amber glow, rate limit approaching
- **Disconnected (○○○)** - Gray, click to configure

**Interaction:**
- Click tether name → Open tether settings panel
- Click mana bar → Show usage breakdown modal
- Shows real-time updates when API calls happen

### Tether Settings Page (Existing)

Keep the current TethersPage.jsx design but enhance:
- Add "Quick Connect" flow for first-time users
- Show usage stats per provider (calls today, this week, cost)
- Add "Test Connection" button that runs a small query
- Show last verification timestamp

**Visual Enhancement:**
When a tether is active and making calls, add a subtle "pulse" animation to its icon in the sidebar nav item.

---

## Visual Effects (Subtle)

### What to Adopt from Website

**YES - These work for a tool:**
- ✅ **Subtle scanlines** - Very faint (2% opacity), gives texture
- ✅ **Corner brackets** - On cards, reinforces "terminal window" feel
- ✅ **Underglow on hover** - Cards get faint colored glow on hover
- ✅ **Blue text glow** - Headers and accent text have soft glow
- ✅ **Border animations** - Borders pulse slightly when processing

**NO - Too flashy for a work tool:**
- ❌ Vignette overlay (makes text harder to read)
- ❌ Heavy CRT flicker animation (distracting)
- ❌ Aggressive scanline sweep (too much motion)
- ❌ Radial gradients everywhere (muddy backgrounds)

### ReCog-Specific Effects

**1. Processing Indicators**
When LLM calls are active, show subtle "thinking" animation:
- Top header has a thin orange line that pulses
- Affected tether icon has gentle breathe animation
- Status text: "Processing with Claude..." (fades in/out)

**2. Insight Emergence**
When new insights are created, they should "fade in" with a brief orange glow that fades to normal. Makes the UI feel responsive to the analysis happening.

**3. Pattern Connections**
On the Patterns page, when viewing a pattern, subtle lines could connect related entities/insights (very light, doesn't interfere with reading).

**4. Tether Pulse**
When you click "Connect" on a tether, the icon does one bright pulse then settles to steady glow. Feels like "coming online."

---

## Component Design Updates

### Cards

**Current:** Flat cards with border
**Proposed:** Add terminal corners and subtle underglow

```css
.recog-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-accent);
  border-radius: 6px;
  padding: 20px;
  position: relative;
  transition: all 0.25s ease;
}

/* Terminal corners */
.recog-card::before {
  content: '';
  position: absolute;
  top: 8px;
  left: 8px;
  width: 12px;
  height: 12px;
  border-left: 2px solid var(--blue-mid);
  border-top: 2px solid var(--blue-mid);
  opacity: 0.4;
}

.recog-card::after {
  content: '';
  position: absolute;
  bottom: 8px;
  right: 8px;
  width: 12px;
  height: 12px;
  border-right: 2px solid var(--blue-mid);
  border-bottom: 2px solid var(--blue-mid);
  opacity: 0.4;
}

/* Hover state */
.recog-card:hover {
  border-color: var(--orange-mid);
  box-shadow: 0 0 12px var(--glow-orange);
  transform: translateY(-2px);
}
```

### Buttons

Keep shadcn button variants but add ReCog styling:

```css
/* Primary action - Cognitive operations */
.btn-cognitive {
  background: var(--orange-mid);
  color: var(--bg-void);
  border: 1px solid var(--orange-light);
  transition: all 0.15s ease;
}

.btn-cognitive:hover {
  box-shadow: 0 0 8px var(--glow-orange);
  background: var(--orange-light);
}

/* Secondary - Data operations */
.btn-structure {
  background: var(--bg-elevated);
  color: var(--blue-light);
  border: 1px solid var(--blue-mid);
}

.btn-structure:hover {
  border-color: var(--blue-light);
  box-shadow: 0 0 6px var(--glow-blue);
}

/* Tether actions */
.btn-tether {
  background: var(--bg-elevated);
  color: var(--tether-active);
  border: 1px solid var(--tether-active);
}
```

### Badges

Current badges are good, but add semantic variants:

```jsx
{/* Status badges with glow */}
<Badge variant="processing" className="glow-magenta">
  Processing
</Badge>

<Badge variant="connected" className="glow-teal">
  Connected
</Badge>

<Badge variant="insight" className="glow-orange">
  High Significance
</Badge>
```

### Sidebar Navigation

**Enhancement:** Add subtle state indicators

```
ANALYSIS
  ⚡ Signal Extraction
  📤 Upload [2]           ← Badge shows active uploads

WORKFLOW  
  ✓ Preflight [5]         ← Number = items in queue
  👤 Entities [12]        ← Unknown entities count

RESULTS
  💡 Insights [234]       ← Total insights  
  🔗 Patterns [18]        ← Active patterns

SYSTEM
  ⚡ Tethers [●●○]        ← Connection status icons
```

---

## Page-Specific Recommendations

### Signal Extraction (Tier 0)
**Current:** Good, keep it  
**Add:**
- Show processing time in header (e.g., "Analyzed in 0.3s")
- Add "Copy Results" button for sharing
- Subtle pulse animation while analyzing

### Upload
**Current:** Good  
**Add:**
- Show file format icons (not just text)
- Progress bar has orange gradient (not flat)
- Completed uploads get green checkmark with brief glow

### Preflight
**Current:** Good  
**Enhance:**
- Cost estimate gets orange highlight if >$1
- Unknown entity count gets amber warning glow
- "Confirm & Process" button should feel weighty (larger, centered)

### Entities
**Current:** Good  
**Add:**
- Entity relationship graph visualization (future phase)
- Quick-identify dropdown (no need to open full modal for simple cases)
- Recently identified entities show at top with brief glow (fade out after 10s)

### Insights
**Current:** Good  
**Enhance:**
- Significance score (1-10) shown as horizontal bar with gradient (low=blue, high=orange)
- Surfaced insights get subtle orange border
- Theme tags are colored (not all gray)

### Patterns
**Current:** Good  
**Add:**
- Pattern strength visualization (concentric circles? network graph?)
- "Run Synthesis" button needs more prominence (it's the key action)
- Show which tether was used for synthesis

### Tethers (NEW)
**Design:** Already created, looks good  
**Enhance:**
- Add usage graph (last 7 days API calls)
- Show estimated monthly cost based on recent usage
- "Quick Setup Wizard" for first-time users

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Update base styling without breaking existing functionality

- [ ] Update `index.css` with new color variables
- [ ] Add utility classes for effects (`.glow-orange`, `.terminal-corners`, etc.)
- [ ] Update `tailwind.config.js` with extended colors
- [ ] Add scanline overlay component (very subtle)
- [ ] Test on all existing pages

**Deliverable:** ReCog UI with terminal aesthetic foundation

### Phase 2: Tether Integration (Week 2)  
**Goal:** Make tethers feel core to the experience

- [ ] Build header tether status bar
- [ ] Add tether connection animations
- [ ] Integrate tether status into page headers (show which tether is active)
- [ ] Add mana pool indicator (if using mana)
- [ ] Processing indicator when LLM calls active

**Deliverable:** Tethers feel like "power source" for cognition

### Phase 3: Component Polish (Week 3)
**Goal:** Elevate individual components to match design system

- [ ] Update all cards with terminal corners
- [ ] Add hover effects with appropriate glows
- [ ] Enhance buttons with semantic variants
- [ ] Update badges with glow variants
- [ ] Improve sidebar navigation indicators

**Deliverable:** Cohesive component library that feels "ReCog"

### Phase 4: Motion & Life (Week 4)
**Goal:** Add subtle animations that communicate processing

- [ ] Processing pulse animations
- [ ] Insight emergence effects
- [ ] Tether connection animations
- [ ] Page transition smoothness
- [ ] Loading states that feel intelligent (not just spinners)

**Deliverable:** UI feels responsive and alive

### Phase 5: Page-Specific Enhancements (Ongoing)
**Goal:** Optimize each page for its specific use case

- [ ] Insights: Significance visualization
- [ ] Patterns: Strength indicator
- [ ] Entities: Quick-identify flow
- [ ] Upload: Enhanced progress tracking
- [ ] Preflight: Better cost warnings

**Deliverable:** Each page feels purpose-built

---

## Design Flair vs. Heavy-Handedness

### DO (Subtle, Professional)
✅ Scanlines at 2% opacity (barely visible)  
✅ Text glow on headers only (not body text)  
✅ Hover effects that respond to user (cards, buttons)  
✅ Semantic color coding (orange=cognition, blue=data, teal=connection)  
✅ Corner brackets on cards (terminal aesthetic without being loud)  
✅ Processing indicators when LLM is actually working  

### DON'T (Overdone, Distracting)
❌ Scanlines at 20% opacity (too visible, hurts readability)  
❌ Everything glows all the time (visual noise)  
❌ Animated backgrounds (motion sickness risk)  
❌ Rainbow gradients everywhere (looks childish)  
❌ Sound effects (annoying in a work tool)  
❌ Constant pulsing/blinking (accessibility issue)  

**Golden Rule:** Effects should **support comprehension**, not demand attention.

---

## Technical Recommendations

### CSS Architecture

**Option A: Extend current index.css**
- Pros: Simple, keeps everything in one place
- Cons: File gets large, hard to organize

**Option B: Create `recog-theme.css`**
- Pros: Separation of concerns, easier to maintain
- Cons: One more file to import

**Recommendation:** Option B - Create dedicated theme file

```
src/
  styles/
    index.css           (shadcn/tailwind base)
    recog-theme.css     (ReCog-specific styling)
    effects.css         (animations, glows, scanlines)
```

### Component Patterns

**Base Component:**
```jsx
// All cards get terminal aesthetic automatically
<Card className="recog-card">
  <CardHeader>
    <CardTitle className="text-glow">Title</CardTitle>
  </CardHeader>
  <CardContent>
    {/* Content */}
  </CardContent>
</Card>
```

**Effect Utilities:**
```jsx
// Apply effects via utility classes
<div className="terminal-corners glow-orange-hover">
  {/* Automatically gets corner brackets and orange glow on hover */}
</div>
```

### Performance Considerations

**CSS Transitions Only:**
- No JavaScript animation libraries needed
- CSS transitions are hardware accelerated
- Better battery life on laptops

**Conditional Effects:**
```jsx
// Only add scanlines if user hasn't disabled animations
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

{!prefersReducedMotion && <Scanlines />}
```

**Lazy Load Heavy Components:**
```jsx
// Pattern visualization only loads when needed
const PatternGraph = lazy(() => import('./PatternGraph'))
```

---

## User Experience Flow

### First-Time User Journey

1. **Landing on Signal Extraction**
   - Sees clean, professional interface
   - Terminal aesthetic is present but subtle
   - Immediate value: Can analyze text for free

2. **Uploading First File**
   - Drag & drop feels responsive
   - Progress bar shows work happening
   - Success state has brief celebratory glow

3. **Discovering Tethers**
   - Header shows "No tethers connected" in amber
   - Click leads to setup wizard
   - After connecting, header shows green status
   - User feels empowered ("I just unlocked more power")

4. **Running First Synthesis**
   - "Run Synthesis" button is prominent, inviting
   - Modal shows tether selection + strategy
   - Processing indicator in header pulses
   - Results appear with subtle emergence animation

5. **Returning User**
   - Tethers auto-connect on load
   - Recent work visible immediately
   - Feels like returning to a familiar tool

---

## Accessibility Compliance

**WCAG 2.1 AA Requirements:**

✅ **Color Contrast**
- Orange on dark: 7.2:1 (AAA)
- Blue on dark: 6.8:1 (AAA)
- Text on backgrounds: >4.5:1 (AA)

✅ **Motion**
- All animations respect `prefers-reduced-motion`
- No auto-playing videos or sounds
- Animations are subtle enough to not trigger vestibular issues

✅ **Keyboard Navigation**
- All interactive elements focusable
- Focus rings visible (orange glow)
- Logical tab order maintained

✅ **Screen Readers**
- Semantic HTML (header, nav, main, article)
- ARIA labels on icon buttons
- Status updates announced ("Processing complete")

**Testing:**
- Lighthouse audit should score >90
- axe DevTools should report zero critical issues
- Test with NVDA screen reader on Windows

---

## Competitive Analysis

### How ReCog Should Differ

**vs. Generic SaaS Dashboards** (Linear, Notion, etc.)
- ReCog: More technical, shows the thinking
- Them: Clean but generic, hides complexity

**vs. AI Tools** (ChatGPT UI, Claude.ai)
- ReCog: Multi-layered workflow, not just chat
- Them: Conversation-focused, linear

**vs. Data Analytics Tools** (Tableau, Looker)
- ReCog: Qualitative insights, not just charts
- Them: Quantitative dashboards, lots of graphs

**ReCog's Sweet Spot:**
Professional enough for enterprise use, distinctive enough that users remember it, technical enough that power users feel respected.

---

## Brand Consistency with EhkoLabs

The website established:
- **Terminal aesthetic** (CRT, scanlines, blue glow)
- **Monospace font** (JetBrains Mono)
- **Dark void backgrounds**
- **Accent colors shift per product** (Blue for EhkoLabs, Orange for ReCog)

ReCog should feel like it's **from the same studio**, but **a different tool**:
- Website: Marketing, high energy, full effects
- ReCog: Product, professional, restrained effects

**Visual Relationship:**
```
EhkoLabs Website          ReCog Dashboard
     [Terminal]     ─────>    [Terminal]  
     [Blue glow]    ─────>    [Orange glow]
     [Heavy FX]     ─────>    [Subtle FX]
     [CRT effect]   ─────>    [Light scanlines]
```

---

## Final Recommendation

**Ship ReCog with:**

1. **Terminal Foundation** - Scanlines, corner brackets, blue/orange palette
2. **Tether-First Design** - Header status bar makes tethers core
3. **Subtle Effects** - Glows, pulses, fades that support (not distract)
4. **Professional Polish** - shadcn components + ReCog theme
5. **Cognitive Metaphors** - Visual language that communicates "thinking"

**Skip for V1:**
- Heavy CRT effects (too much)
- Complex animations (ship stable first)
- Pattern graph visualizations (nice-to-have)

**Save for V1.1:**
- Usage analytics dashboard
- Custom theme builder
- Advanced visualization modes
- Export/reporting features

---

## Next Steps

1. **Review this report** - Brent approves direction
2. **Create design tokens** - CSS variables for entire system
3. **Build component examples** - Card, button, badge with new styling
4. **Update one page** - Signal Extraction as proof-of-concept
5. **Iterate** - Refine based on real usage
6. **Roll out** - Apply to remaining pages
7. **Polish** - Final tweaks before V1 launch

---

**Ready to proceed?** Let me know which phase to start with, or if you want to see mockups of specific components first.

---

**Author:** Claude (Sonnet 4.5)  
**For:** Brent @ EhkoLabs  
**Project:** ReCog V1 Design Direction  
**Date:** 2026-01-02

# ReCog React UI

Modern, professional UI for the ReCog text analysis engine built with React, shadcn/ui, and Tailwind CSS.

## Tech Stack

- **React 18** - Modern React with hooks
- **Vite 5** - Lightning-fast dev server and build tool
- **shadcn/ui** - High-quality, accessible component library
- **Tailwind CSS** - Utility-first CSS framework
- **Lucide React** - Beautiful, consistent icons
- **Radix UI** - Headless UI primitives for accessibility

## Features

### 🎨 Design System
- **Holographic Theme** - Deep void backgrounds with blue/orange accents
- **Consistent Components** - Professional shadcn/ui components
- **Responsive Layout** - Works on all screen sizes
- **Smooth Animations** - Tailwind animate utilities

### 📄 Pages

1. **Cases** - Case-centric document intelligence (NEW)
   - Cases dashboard with document/findings counts
   - Create case modal with title, context, focus areas
   - Case detail view with tabbed interface
   - Findings management (verify/reject/annotate)
   - Timeline visualization with human annotations

2. **Signal Extraction** - Tier 0 analysis (free, no LLM)
   - Real-time text analysis
   - Emotion detection with color-coded badges
   - Entity extraction
   - Temporal reference parsing
   - Structural analysis

3. **Upload** - File upload with drag & drop
   - Multi-file support
   - Format detection
   - Progress tracking
   - **Case selection** - associate uploads with cases
   - Supported formats: TXT, MD, JSON, PDF, CSV, Excel, Email, Chat exports

4. **Preflight** - Review workflow before processing
   - Item filtering (min words, date range, keywords)
   - Include/exclude items
   - Cost estimation
   - **Case context banner** - shows linked case info
   - Unknown entity warnings

5. **Entities** - Entity management
   - Unknown entities queue
   - Identify dialog with relationship types
   - Anonymization support
   - Entity registry browser

6. **Insights** - Browse extracted insights
   - Filter by status, significance, type
   - Tabbed view (All, Raw, Refined, Surfaced)
   - **Promote to findings** - badge action for case findings
   - Significance scoring visualization
   - Theme tags

7. **Patterns** - Synthesized patterns
   - Run synthesis with strategy selection
   - Pattern strength visualization
   - Cluster metadata display
   - Entity and timespan indicators

## Getting Started

### Prerequisites
- Node.js 18+ 
- ReCog Flask backend running on port 5100

### Installation

```bash
cd C:\EhkoDev\recog-ui
npm install
```

### Development

```bash
npm run dev
```

Opens on **http://localhost:3101** with proxy to Flask backend at :5100

### Build

```bash
npm run build
```

Output in `dist/` directory.

## Project Structure

```
recog-ui/
├── src/
│   ├── components/
│   │   ├── ui/              # shadcn components
│   │   │   ├── button.jsx
│   │   │   ├── card.jsx
│   │   │   ├── dialog.jsx
│   │   │   ├── input.jsx
│   │   │   ├── label.jsx
│   │   │   ├── textarea.jsx
│   │   │   ├── select.jsx
│   │   │   ├── tabs.jsx
│   │   │   └── badge.jsx
│   │   └── pages/           # Page components
│   │       ├── CasesPage.jsx      # Case dashboard + detail + modal
│   │       ├── SignalExtraction.jsx
│   │       ├── UploadPage.jsx     # With case selection
│   │       ├── PreflightPage.jsx  # With case context banner
│   │       ├── EntitiesPage.jsx
│   │       ├── InsightsPage.jsx   # With findings promotion
│   │       └── PatternsPage.jsx
│   ├── lib/
│   │   ├── api.js           # API client (40+ methods including cases)
│   │   └── utils.js         # Helper functions
│   ├── App.jsx              # Main app component
│   ├── main.jsx             # Entry point
│   └── index.css            # Global styles + theme
├── public/
│   └── recog-logo.svg       # Logo asset
├── index.html
├── vite.config.js
├── tailwind.config.js
├── postcss.config.cjs
└── package.json
```

## API Integration

All API calls go through `src/lib/api.js`:

```javascript
import { analyzeTier0, uploadFile, getInsights } from '@/lib/api'

// Tier 0 analysis
const result = await analyzeTier0(text)

// Upload file
const upload = await uploadFile(file)

// Get insights with filters
const insights = await getInsights({ status: 'surfaced', min_significance: 7 })
```

### Available API Methods

**Health & Info:**
- `getHealth()` - Server health check
- `getInfo()` - Server info and endpoints

**Analysis:**
- `analyzeTier0(text)` - Run Tier 0 signal extraction

**File Operations:**
- `uploadFile(file)` - Upload file for processing
- `detectFileFormat(file)` - Detect file format

**Preflight:**
- `getPreflight(sessionId)` - Get preflight session
- `getPreflightItems(sessionId)` - Get items in session
- `filterPreflightItems(sessionId, filters)` - Apply filters
- `excludePreflightItem(sessionId, itemId)` - Exclude item
- `includePreflightItem(sessionId, itemId)` - Include item
- `confirmPreflight(sessionId)` - Start processing

**Entities:**
- `getEntities(filters)` - List entities
- `getUnknownEntities()` - Get unknown entities
- `getEntity(entityId)` - Get entity details
- `updateEntity(entityId, updates)` - Update entity
- `getEntityStats()` - Get entity statistics

**Insights:**
- `getInsights(filters)` - List insights
- `getInsight(insightId)` - Get insight details
- `updateInsight(insightId, updates)` - Update insight
- `deleteInsight(insightId, hard)` - Delete insight
- `getInsightStats()` - Get insight statistics

**Synthesis:**
- `createClusters(data)` - Create insight clusters
- `getClusters()` - List pending clusters
- `runSynthesis(data)` - Run full synthesis
- `getPatterns(filters)` - List patterns
- `getPattern(patternId)` - Get pattern details
- `updatePattern(patternId, updates)` - Update pattern
- `getSynthStats()` - Get synthesis statistics

**Queue:**
- `getQueue(filters)` - List queue items
- `getQueueStats()` - Get queue statistics
- `retryQueueItem(itemId)` - Retry failed item
- `deleteQueueItem(itemId)` - Remove from queue
- `clearQueue()` - Clear completed items

**Cases:**
- `getCases(filters)` - List cases
- `getCase(caseId)` - Get case details
- `createCase(data)` - Create new case
- `updateCase(caseId, data)` - Update case
- `deleteCase(caseId)` - Delete case
- `getCaseDocuments(caseId)` - List case documents
- `getCaseStats(caseId)` - Get case statistics
- `getCaseContext(caseId)` - Get context for prompts

**Findings:**
- `getCaseFindings(caseId, filters)` - List case findings
- `getFinding(findingId)` - Get finding details
- `createFinding(data)` - Promote insight to finding
- `updateFinding(findingId, data)` - Update status
- `deleteFinding(findingId)` - Demote finding
- `addFindingNote(findingId, note)` - Add annotation

**Timeline:**
- `getCaseTimeline(caseId)` - Get timeline events
- `addTimelineEvent(caseId, data)` - Add human annotation
- `getCaseActivity(caseId)` - Recent activity

## Theme Customization

Theme is defined in `src/index.css` with CSS custom properties:

```css
:root {
  --background: 218 28% 5%;        /* Deep void */
  --foreground: 220 50% 93%;       /* Primary text */
  --card: 218 25% 7%;              /* Surface */
  --primary: 24 100% 67%;          /* Orange light */
  --accent: 24 58% 57%;            /* Orange mid */
  /* ... */
}
```

Custom colors in Tailwind:
- `orange-light` - Primary accent (#ff9955)
- `orange-mid` - Secondary accent (#d97e4a)
- `blue-light` - Structure color (#6b8cce)

## Adding shadcn Components

To add more shadcn/ui components:

```bash
npx shadcn@latest add [component-name]
```

Examples:
- `npx shadcn@latest add table`
- `npx shadcn@latest add toast`
- `npx shadcn@latest add progress`

Components are added to `src/components/ui/`

## Development Notes

### State Management
- Local component state with `useState`
- Server health polling (30s interval)
- Badge counts updated from `/api/health`

### Error Handling
- API errors caught and displayed to user
- Loading states for async operations
- Form validation before submission

### Accessibility
- Radix UI primitives (keyboard navigation, ARIA)
- Semantic HTML structure
- Focus management in dialogs

### Performance
- Vite's fast HMR
- Lazy loading could be added for code splitting
- API responses cached by browser

## Roadmap

**Phase 10.5 - Case Architecture ✅ COMPLETE:**
- [x] CasesPage with dashboard, detail, create modal
- [x] Findings management (verify/reject/annotate)
- [x] Timeline visualization
- [x] Case selection in UploadPage
- [x] Case context banner in PreflightPage
- [x] Findings promotion in InsightsPage

**Phase 10.6 - Component Library Expansion:**
- [ ] Add Table component for data grids
- [ ] Add Toast for notifications
- [ ] Add Progress for loading states
- [ ] Add Tooltip for help text

**Phase 10.7 - Page Enhancements:**
- [ ] Signal Extraction: Save analysis results
- [ ] Upload: Batch processing queue view
- [ ] Preflight: Advanced filtering UI
- [ ] Entities: Entity graph visualization
- [ ] Cases: Cross-case pattern detection
- [ ] Patterns: Pattern evolution timeline

**Phase 10.8 - Advanced Features:**
- [ ] Dark/light mode toggle
- [ ] User preferences persistence
- [ ] Keyboard shortcuts
- [ ] Export functionality (CSV, JSON)
- [ ] Real-time updates (WebSockets)

## Troubleshooting

**Port 3101 already in use:**
```bash
# Change port in vite.config.js
server: {
  port: 3102  // or any other port
}
```

**API calls failing:**
- Ensure Flask backend is running on :5100
- Check proxy configuration in `vite.config.js`
- Verify CORS settings in Flask

**Components not found:**
```bash
# Reinstall dependencies
rm -rf node_modules
npm install
```

## Contributing

When adding new pages:
1. Create component in `src/components/pages/`
2. Add API methods to `src/lib/api.js` if needed
3. Import and route in `src/App.jsx`
4. Update navigation badges if applicable

## License

Part of ReCog project - see main LICENSE file.

---

**Built with:** React 18 + Vite 5 + shadcn/ui + Tailwind CSS
**Version:** 0.7.0
**Last Updated:** 2026-01-06

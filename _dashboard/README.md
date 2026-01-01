# ReCog Dashboard

Professional web interface for the Recursive Cognition Engine (ReCog).

## Features

### Text Analysis
- Zero-cost Tier 0 analysis (no LLM required)
- Entity extraction (PERSON, DATE, MONEY, LOCATION, EMAIL, PHONE, URL)
- Emotional analysis
- Sentiment detection
- Real-time processing

### Entity Registry
- View all extracted entities
- Filter by type, status, or search term
- Confirm/delete entities
- Statistics dashboard
- Bulk operations

## Technology Stack

- **Frontend**: React 18 + Vite
- **Styling**: Tailwind CSS
- **Design System**: Custom ReCog Green theme
- **Icons**: Lucide React
- **Backend**: ReCog Server (localhost:5100)

## Quick Start

### 1. Install Dependencies
```bash
cd "G:\Other computers\Ehko\Obsidian\ReCog\_dashboard"
npm install
```

### 2. Start ReCog Server
Make sure the ReCog server is running on port 5100.

### 3. Start Dashboard
```bash
npm run dev
```

Dashboard will be available at: http://localhost:3100

## API Endpoints Used

- `POST /api/tier0` - Text analysis
- `GET /api/entities` - List all entities
- `POST /api/entities/confirm` - Confirm entity
- `DELETE /api/entities/{id}` - Delete entity

## Design Theme

**ReCog Clinical Green** - Data-focused aesthetic
- Primary: `#7ed99b` (Clinical green)
- Background: Dark slate
- Emphasis on tables, data density, and clarity
- Clean, professional, analytical

## Development

```bash
# Dev server (with hot reload)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Roadmap

- [ ] Insight Browser page
- [ ] Synthesis Dashboard with pattern visualization
- [ ] Queue monitoring page
- [ ] Preflight manager for large imports
- [ ] Real-time WebSocket updates
- [ ] Keyboard shortcuts (Cmd+K)
- [ ] Export functionality (CSV, JSON)
- [ ] Dark/light mode toggle

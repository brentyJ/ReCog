# ReCog Dashboard - Setup Guide

## One-Time Setup

### Step 1: Install npm dependencies

Open PowerShell and run:

```powershell
cd "G:\Other computers\Ehko\Obsidian\ReCog\_dashboard"
npm install
```

This will install:
- React 18
- Vite 5
- Tailwind CSS 3
- Lucide React (icons)
- React Router DOM

**Expected output:**
```
added 130+ packages in ~30s
```

### Step 2: Verify ReCog Server

Make sure your ReCog server is accessible at `http://localhost:5100`

You can start it from the EhkoForge Control Panel → ReCog tab.

## Daily Use

### Option 1: VBS Launcher (Recommended - No Console)

Double-click:
```
G:\Other computers\Ehko\Obsidian\ReCog\_dashboard\ReCog Dashboard.vbs
```

### Option 2: Batch File (Shows Console)

Double-click:
```
G:\Other computers\Ehko\Obsidian\ReCog\_dashboard\start-dashboard.bat
```

### Option 3: Command Line

```powershell
cd "G:\Other computers\Ehko\Obsidian\ReCog\_dashboard"
npm run dev
```

## Accessing the Dashboard

Once started, open your browser to:
```
http://localhost:3100
```

## Features

### Text Analysis Tab
1. Paste text into the input area
2. Click "Analyze" button
3. View extracted entities, emotions, and sentiment
4. All processing happens via Tier 0 (zero cost, no LLM)

### Entity Registry Tab
1. View all extracted entities from your system
2. Filter by type (PERSON, DATE, MONEY, etc.)
3. Filter by status (CONFIRMED, PENDING)
4. Search by entity value
5. Confirm entities with green checkmark
6. Delete entities with red trash icon

## Troubleshooting

**Issue: "Cannot find module"**
```powershell
# Delete node_modules and reinstall
cd "G:\Other computers\Ehko\Obsidian\ReCog\_dashboard"
rmdir /s /q node_modules
npm install
```

**Issue: "Port 3100 already in use"**
- Stop any existing dashboard instances
- Or change port in `vite.config.js`

**Issue: "Connection error" when analyzing**
- Make sure ReCog server is running on port 5100
- Check the ReCog tab in EhkoForge Control Panel

**Issue: npm not found**
- Install Node.js from https://nodejs.org
- Restart terminal after installation

## Next Steps

After basic setup is working:
1. Add more pages (Insights, Synthesis, Queue)
2. Install shadcn/ui CLI for advanced components
3. Add data visualization with recharts
4. Implement real-time updates

## Quick Test

1. Start ReCog server (port 5100)
2. Start dashboard (port 3100)
3. Navigate to Text Analysis
4. Paste this test text:
   ```
   Had a meeting with Sarah on Monday. Budget is $50,000. 
   Contact: sarah@example.com or 0412-555-789.
   ```
5. Click Analyze
6. Should see entities: PERSON (Sarah), DATE (Monday), MONEY ($50,000), EMAIL, PHONE
7. Go to Entity Registry tab
8. Should see all extracted entities in the table
9. Try confirming or deleting entities

Success! 🎉

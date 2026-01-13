# ReCog Testing Guide

*Production readiness through ruthless verification*

---

## Why E2E Tests Matter

### The Vibe Coding Problem

When working with AI-assisted development ("vibe coding"), a fundamental truth emerges:

**AI writes plausible code that often doesn't work.**

The code looks right. It follows patterns. It compiles. But it might:
- Reference functions that don't exist
- Use APIs incorrectly
- Miss edge cases
- Break existing functionality

### The Solution: Trust but Verify

The answer isn't to stop using AI assistance - it's to **verify ruthlessly** with real tests:

1. **Unit tests** catch logic errors in isolated functions
2. **Integration tests** catch API contract violations
3. **E2E tests** catch the failures unit tests miss - real-world integration issues

E2E tests are especially valuable because they test the system as users experience it.

---

## Running Tests

### Smoke Tests

The smoke test suite verifies core ReCog functionality works end-to-end:

```bash
cd _scripts
python test_e2e_smoke.py
```

Options:
```bash
# Verbose output (shows details)
python test_e2e_smoke.py --verbose

# Skip React build test (faster)
python test_e2e_smoke.py --skip-build

# Don't auto-start server
python test_e2e_smoke.py --no-auto-start

# Custom server URL
python test_e2e_smoke.py --server-url http://localhost:5100
```

#### What Smoke Tests Check

| Test | What It Verifies |
|------|------------------|
| Server Health | Flask starts, responds on port 5100 |
| API Root | REST endpoints accessible |
| Case Creation | POST /api/cases works |
| Case List | GET /api/cases returns data |
| Tier 0 Extraction | Free signal extraction works |
| Entity Registry | Entity CRUD operations |
| Insights Endpoint | Insight storage/retrieval |
| Database Connection | SQLite connection, table structure |
| Migrations | Schema files present |
| React Build | Frontend compiles (npm run build) |

### Preflight Checks

Preflight checks run before git operations to catch issues early:

```bash
cd _scripts
python preflight_check.py
```

Options:
```bash
# Verbose output
python preflight_check.py --verbose
```

#### What Preflight Checks Catch

| Check | What It Catches |
|-------|-----------------|
| Repo Identity | Wrong repo (EhkoForge vs ReCog) |
| ReCog Patterns | Missing port 5100, recog_engine imports |
| Cross-contamination | EhkoForge imports in ReCog code |
| License Headers | Missing AGPLv3 headers in new files |
| Instructions File | Missing/stale RECOG_INSTRUCTIONS.md |
| Private Protection | _private/ not gitignored |
| Sensitive Files | .env, credentials staged for commit |

### Full Test Suite

For comprehensive testing with pytest:

```bash
cd _scripts
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=recog_engine

# Single test file
python -m pytest tests/test_tier0.py -v
```

---

## Fixing Common Issues

### Preflight Failures

#### "This looks like EhkoForge!"
You're running preflight in the wrong directory. Navigate to ReCog:
```bash
cd C:\EhkoVaults\ReCog
```

#### "Missing AGPLv3 header"
Add the license header to new Python files:
```python
"""
Module description

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
"""
```

#### "_private/ not found in .gitignore"
Add to `.gitignore`:
```
_private/
```

#### "Sensitive files staged"
Unstage the file:
```bash
git reset HEAD .env
```

### Smoke Test Failures

#### "Server not reachable"
Start the server:
```bash
cd _scripts
python server.py
```

#### "Database not found"
Initialize the database:
```bash
cd _scripts
python recog_cli.py db init
```

#### "React build failed"
Install dependencies:
```bash
cd _ui
npm install
npm run build
```

---

## CI/CD Integration (Future)

### GitHub Actions Setup

When ready, add `.github/workflows/test.yml`:

```yaml
name: ReCog Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd _scripts
          pip install -r requirements.txt

      - name: Run preflight checks
        run: |
          cd _scripts
          python preflight_check.py

      - name: Initialize database
        run: |
          cd _scripts
          python recog_cli.py db init

      - name: Run pytest
        run: |
          cd _scripts
          python -m pytest tests/ -v

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Build frontend
        run: |
          cd _ui
          npm ci
          npm run build
```

### Pre-commit Hook

For local enforcement, add `.git/hooks/pre-commit`:

```bash
#!/bin/bash
python _scripts/preflight_check.py
if [ $? -ne 0 ]; then
    echo "Preflight checks failed. Commit blocked."
    exit 1
fi
```

---

## Manual Testing Checklist

For major features, verify manually:

### Document Upload Flow
- [ ] Drag and drop file into upload zone
- [ ] File appears in preflight list
- [ ] Tier 0 signals extracted
- [ ] Entity badges appear
- [ ] Processing completes without error

### Case Workflow
- [ ] Create new case with title/context
- [ ] Upload documents to case
- [ ] View case in Cases page
- [ ] Check findings tab
- [ ] View timeline events

### Entity Management
- [ ] View entities in registry
- [ ] Reject false positive entity
- [ ] Run AI validation (if LLM configured)
- [ ] Confirm validation suggestions

### Cypher Interface
- [ ] Open Cypher panel
- [ ] Send navigation command ("show entities")
- [ ] Send filter request ("filter by date")
- [ ] Check suggestions appear

---

## Architecture Diagram

Generate the current architecture diagram:

```bash
cd _scripts
python generate_architecture.py
```

Output:
- `_docs/ARCHITECTURE.mmd` - Mermaid diagram
- `_docs/ARCHITECTURE_SUMMARY.md` - Text summary

View the diagram at [mermaid.live](https://mermaid.live/) or use VS Code Mermaid extension.

---

## Best Practices

### Before Every Commit
1. Run preflight: `python _scripts/preflight_check.py`
2. Fix any failures
3. Commit only when checks pass

### Before Every Push
1. `git_push.bat` runs preflight automatically
2. Review the output
3. Push only when preflight passes

### After Major Changes
1. Run full smoke tests: `python _scripts/test_e2e_smoke.py`
2. Run pytest: `python -m pytest _scripts/tests/ -v`
3. Regenerate architecture if structure changed

### For Production Deployments
1. All tests must pass
2. Manual checklist completed
3. Architecture diagram updated
4. RECOG_INSTRUCTIONS.md current

---

*Trust but verify. Ship with confidence.*

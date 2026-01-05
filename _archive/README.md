# ReCog UI Archive

**Created:** 2026-01-05  
**Purpose:** Storage for deprecated ReCog dashboard versions

---

## Contents

### _dashboard (Archived 2026-01-05)
- **Reason:** Duplicate of `C:\EhkoDev\recog-ui` - should not have been in vault
- **Version:** v0.6.0 (shadcn/ui version)
- **Status:** Exact copy of external UI repo
- **Issue:** UI development belongs in `C:\EhkoDev\`, not the vault

### _dashboard_OLD (Archived 2026-01-05)
- **Reason:** Superseded by shadcn/ui version
- **Version:** Pre-v0.6.0 (original terminal UI)
- **Status:** No longer maintained

---

## Current Architecture

**PRIMARY UI (Active Development):**  
`C:\EhkoDev\recog-ui` - Full shadcn/ui implementation with 6 pages

**Backend (In Vault):**  
`C:\EhkoVaults\ReCog\_scripts\` - Flask server, worker, CLI

**Separation of Concerns:**
- **Vault** = Backend code, documentation, data
- **C:\EhkoDev\** = Frontend UIs (React, etc.)

---

## Notes

The vault should NOT contain UI code duplicates. Keep the vault focused on:
- Backend engine (`_scripts/`)
- Documentation (`_docs/`)
- Data and database (`_data/`)
- Private configs (`_private/`)

Frontend development happens in `C:\EhkoDev\recog-ui`.

#!/usr/bin/env python3
r"""
Migrate new React UI from C:\EhkoDev\recog-ui to C:\EhkoVaults\ReCog\_dashboard

This replaces the old dashboard with the new Session 31 version.
"""

import shutil
import sys
from pathlib import Path

SOURCE = Path("C:/EhkoDev/recog-ui")
DEST = Path("C:/EhkoVaults/ReCog/_dashboard")
BACKUP = Path("C:/EhkoVaults/ReCog/_dashboard_OLD")

def main():
    print("=" * 70)
    print("  RECOG DASHBOARD MIGRATION")
    print("=" * 70)
    print()
    
    # Check source exists
    if not SOURCE.exists():
        print(f"[X] Source not found: {SOURCE}")
        return 1
    
    # Check dest exists
    if not DEST.exists():
        print(f"[X] Destination not found: {DEST}")
        return 1
    
    print(f"Source: {SOURCE}")
    print(f"Dest:   {DEST}")
    print()
    
    # Confirm
    try:
        response = input("This will REPLACE the old dashboard. Continue? [y/N]: ").strip().lower()
        if response != 'y':
            print("[i] Cancelled")
            return 0
    except (KeyboardInterrupt, EOFError):
        print("\n[i] Cancelled")
        return 0
    
    print()
    print("[1/4] Backing up old dashboard...")
    if BACKUP.exists():
        print(f"      Removing old backup: {BACKUP}")
        shutil.rmtree(BACKUP)
    
    print(f"      Moving {DEST} → {BACKUP}")
    DEST.rename(BACKUP)
    print("      [OK]")
    
    print()
    print("[2/4] Copying new dashboard...")
    print(f"      Copying {SOURCE} → {DEST}")
    shutil.copytree(SOURCE, DEST, ignore=shutil.ignore_patterns('node_modules'))
    print("      [OK] (node_modules excluded)")
    
    print()
    print("[3/4] Creating launcher...")
    launcher_content = """@echo off
REM ReCog Dashboard Launcher
cd /d "%~dp0"
echo Starting ReCog Dashboard...
echo.
echo Dashboard: http://localhost:3101
echo Backend:   http://localhost:5100
echo.
npm run dev
"""
    launcher_file = DEST / "start-dashboard.bat"
    launcher_file.write_text(launcher_content)
    print(f"      Created: {launcher_file}")
    print("      [OK]")
    
    print()
    print("[4/4] Updating VBS launcher...")
    vbs_content = '''Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run "cmd /c start-dashboard.bat", 0, False
Set objShell = Nothing
'''
    vbs_file = DEST / "ReCog Dashboard.vbs"
    vbs_file.write_text(vbs_content)
    print(f"      Created: {vbs_file}")
    print("      [OK]")
    
    print()
    print("=" * 70)
    print("  [DONE] Dashboard migration complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. cd C:\\EhkoVaults\\ReCog\\_dashboard")
    print("  2. npm install")
    print("  3. npm run dev")
    print()
    print(f"Old dashboard backed up at: {BACKUP}")
    print("You can delete this after verifying the new one works.")
    print()
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
"""
ReCog Git Push - Session Update

Quick git add/commit/push for ReCog repository.
Updates the default commit message from git_recog.py to current session.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

REPO_PATH = Path(__file__).parent

def run_git(cmd):
    """Run git command and return result"""
    result = subprocess.run(
        cmd,
        cwd=REPO_PATH,
        capture_output=True,
        text=True,
        shell=True
    )
    return result.returncode, result.stdout, result.stderr

def main():
    print("=" * 70)
    print("  RECOG GIT PUSH")
    print("=" * 70)
    print()
    
    # Check status
    print("[*] Checking status...")
    code, out, err = run_git("git status --short")
    
    if not out.strip():
        print("[i] No changes to commit - working tree clean")
        print()
        return 0
    
    print("\nModified files:")
    print("-" * 70)
    print(out)
    print("-" * 70)
    print()
    
    # Ask for confirmation
    try:
        response = input("Commit and push these changes? [y/N]: ").strip().lower()
        if response != 'y':
            print("[i] Cancelled")
            return 0
    except (KeyboardInterrupt, EOFError):
        print("\n[i] Cancelled")
        return 0
    
    # Get commit message
    print()
    print("Enter commit message (or press Enter for default):")
    try:
        custom_msg = input("> ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n[i] Cancelled")
        return 0
    
    if custom_msg:
        commit_msg = custom_msg
    else:
        # Default message
        commit_msg = "Control panel verification - paths confirmed correct"
    
    print()
    print(f"[+] Staging all changes...")
    code, out, err = run_git("git add -A")
    if code != 0:
        print(f"[X] Error staging: {err}")
        return 1
    print("    [OK]")
    
    print(f"[+] Committing...")
    print(f"    Message: {commit_msg}")
    code, out, err = run_git(f'git commit -m "{commit_msg}"')
    if code != 0:
        if "nothing to commit" in (out + err):
            print("    [i] Nothing to commit")
            return 0
        print(f"[X] Error committing: {err}")
        return 1
    print("    [OK]")
    
    print(f"[>] Pushing to GitHub...")
    code, out, err = run_git("git push origin main")
    if code != 0:
        # Try master
        print("    Trying 'master' branch...")
        code, out, err = run_git("git push origin master")
        if code != 0:
            print(f"[X] Error pushing: {err}")
            return 1
    
    print("    [OK] Successfully pushed!")
    print()
    print("=" * 70)
    print("  [DONE]")
    print("=" * 70)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[X] Error: {e}")
        sys.exit(1)

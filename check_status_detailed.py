#!/usr/bin/env python3
"""Check ReCog git status and what needs committing"""
import subprocess
import sys
from pathlib import Path

RECOG_PATH = Path("C:/EhkoVaults/ReCog")

def run_git(cmd):
    result = subprocess.run(
        cmd,
        cwd=RECOG_PATH,
        capture_output=True,
        text=True,
        shell=True
    )
    return result.returncode, result.stdout, result.stderr

def main():
    print("=" * 70)
    print("  RECOG REPOSITORY STATUS")
    print("=" * 70)
    print()
    
    # Check if it's a repo
    code, _, _ = run_git("git status")
    if code != 0:
        print("[X] Not a git repository or git not found")
        return 1
    
    # Get status
    code, out, err = run_git("git status --short")
    
    print("Modified/new files:")
    print("-" * 70)
    if out.strip():
        print(out)
    else:
        print("  (working tree clean)")
    print("-" * 70)
    print()
    
    # Get last commit
    code, out, err = run_git("git log -1 --oneline")
    print("Last commit:")
    print(f"  {out.strip()}")
    print()
    
    # Check branch
    code, out, err = run_git("git branch --show-current")
    print(f"Current branch: {out.strip()}")
    print()
    
    # Show untracked files count
    code, out, err = run_git("git status --short")
    if out.strip():
        untracked = [line for line in out.split('\n') if line.startswith('??')]
        modified = [line for line in out.split('\n') if line.startswith(' M') or line.startswith('M ')]
        added = [line for line in out.split('\n') if line.startswith('A ')]
        
        print(f"Summary:")
        print(f"  Modified: {len(modified)}")
        print(f"  Added: {len(added)}")
        print(f"  Untracked: {len(untracked)}")

if __name__ == "__main__":
    sys.exit(main())

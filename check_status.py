#!/usr/bin/env python3
"""Quick git status check for ReCog"""

import subprocess
from pathlib import Path

REPO_PATH = Path(__file__).parent

def main():
    print("=" * 60)
    print("  RECOG GIT STATUS")
    print("=" * 60)
    print()
    
    # Get status
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_PATH,
        capture_output=True,
        text=True
    )
    
    print("Modified files:")
    print("-" * 60)
    if result.stdout.strip():
        print(result.stdout)
    else:
        print("  (none - working tree clean)")
    print("-" * 60)
    print()
    
    # Get last commit
    result = subprocess.run(
        ["git", "log", "-1", "--oneline"],
        cwd=REPO_PATH,
        capture_output=True,
        text=True
    )
    
    print("Last commit:")
    print(f"  {result.stdout.strip()}")
    print()
    
    # Get branch
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=REPO_PATH,
        capture_output=True,
        text=True
    )
    
    print(f"Current branch: {result.stdout.strip()}")
    print()

if __name__ == "__main__":
    main()

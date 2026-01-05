#!/usr/bin/env python3
"""Check git status for recog-ui"""
import subprocess
import sys
from pathlib import Path

def main():
    repo_path = Path(__file__).parent
    
    # Check if .git exists
    if not (repo_path / ".git").exists():
        print("NOT a git repository")
        print(f"Path: {repo_path}")
        print("\nShould this be:")
        print("  1. A separate git repo?")
        print("  2. Part of the main ReCog repo?")
        return
    
    # Get status
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    
    print("Git repository found!")
    print("\nModified files:")
    print("-" * 60)
    if result.stdout.strip():
        print(result.stdout)
    else:
        print("  (working tree clean)")
    print("-" * 60)

if __name__ == "__main__":
    main()

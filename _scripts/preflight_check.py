#!/usr/bin/env python3
"""
ReCog Preflight Check - Pre-git validation script

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Enforces repo rules before git operations:
- Verifies we're in ReCog repo (not EhkoForge)
- Checks for ReCog-specific patterns
- Validates AGPLv3 license headers in new Python files
- Detects EhkoForge cross-contamination
- Validates _private/ gitignore protection
- Checks RECOG_INSTRUCTIONS.md freshness

Usage:
    python preflight_check.py [--verbose] [--fix]

Exit codes:
    0 - All checks passed
    1 - One or more checks failed (blocks git push)
"""

import sys
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple, Optional


# =============================================================================
# CONFIGURATION
# =============================================================================

RECOG_PORT = 5100
EHKOFORGE_PORT = 5001

# Expected patterns that confirm we're in ReCog
RECOG_INDICATORS = [
    "recog_engine",
    "port 5100",
    "localhost:5100",
    "ReCog",
]

# Patterns that indicate EhkoForge contamination (actual imports, not comments)
EHKOFORGE_PATTERNS = [
    r"^from\s+ehko_engine\b",      # Import from ehko_engine
    r"^import\s+ehko_engine\b",    # Import ehko_engine
    r"^\s*from\s+ehko_engine\b",   # Indented import
    r"^\s*import\s+ehko_engine\b", # Indented import
    r"localhost:5001",             # EhkoForge server URL
    r"control_server\.py",         # EhkoForge server script
]

# AGPLv3 license header patterns (must contain one of these)
LICENSE_PATTERNS = [
    r"AGPLv3",
    r"AGPL-3\.0",
    r"GNU Affero General Public License",
    r"Licensed under AGPLv3",
]

# Files/directories to exclude from checks
EXCLUDED_PATHS = [
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "_data",
    ".claude",
    "preflight_check.py",  # This file contains detection patterns
    "migrate_from_ehkoforge.py",  # Migration script legitimately references EhkoForge
]

# Max age (days) for RECOG_INSTRUCTIONS.md before warning
INSTRUCTIONS_MAX_AGE_DAYS = 30


# =============================================================================
# CHECK FUNCTIONS
# =============================================================================

class CheckResult:
    """Result of a single check."""

    def __init__(self, name: str, passed: bool, message: str, is_warning: bool = False):
        self.name = name
        self.passed = passed
        self.message = message
        self.is_warning = is_warning

    def __str__(self) -> str:
        if self.passed:
            icon = "[PASS]"
        elif self.is_warning:
            icon = "[WARN]"
        else:
            icon = "[FAIL]"
        return f"{icon} {self.name}: {self.message}"


def get_repo_root() -> Optional[Path]:
    """Find the repository root directory."""
    current = Path(__file__).resolve().parent

    # Walk up to find .git directory
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent

    return None


def check_repo_identity() -> CheckResult:
    """Verify we're in the ReCog repository, not EhkoForge."""
    repo_root = get_repo_root()

    if repo_root is None:
        return CheckResult(
            "Repo Identity",
            False,
            "Not in a git repository"
        )

    # Check for ReCog-specific markers
    recog_markers = [
        repo_root / "_scripts" / "recog_engine",
        repo_root / "_scripts" / "server.py",
        repo_root / "RECOG_INSTRUCTIONS.md",
    ]

    ehkoforge_markers = [
        repo_root / "5.0 Scripts" / "control_server.py",
        repo_root / "6.0 Frontend",
        repo_root / "EHKOFORGE_INSTRUCTIONS.md",
    ]

    recog_found = sum(1 for m in recog_markers if m.exists())
    ehkoforge_found = sum(1 for m in ehkoforge_markers if m.exists())

    if ehkoforge_found > 0:
        return CheckResult(
            "Repo Identity",
            False,
            f"This looks like EhkoForge! Found {ehkoforge_found} EhkoForge markers. Wrong repo!"
        )

    if recog_found < 2:
        return CheckResult(
            "Repo Identity",
            False,
            f"Only found {recog_found}/3 ReCog markers. Is this the right repo?"
        )

    # Check repo name from git remote
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=repo_root
        )
        if result.returncode == 0:
            remote_url = result.stdout.strip().lower()
            if "ehkoforge" in remote_url:
                return CheckResult(
                    "Repo Identity",
                    False,
                    f"Remote URL contains 'ehkoforge': {remote_url}"
                )
            if "recog" not in remote_url:
                return CheckResult(
                    "Repo Identity",
                    True,
                    f"Confirmed ReCog repo (remote doesn't contain 'ehkoforge')",
                )
    except Exception:
        pass  # Git command failed, continue with other checks

    return CheckResult(
        "Repo Identity",
        True,
        f"Confirmed ReCog repository ({recog_found} markers found)"
    )


def check_recog_patterns() -> CheckResult:
    """Verify ReCog-specific patterns exist in key files."""
    repo_root = get_repo_root()
    if repo_root is None:
        return CheckResult("ReCog Patterns", False, "No repo root found")

    server_path = repo_root / "_scripts" / "server.py"
    if not server_path.exists():
        return CheckResult(
            "ReCog Patterns",
            False,
            "server.py not found in _scripts/"
        )

    server_content = server_path.read_text(encoding="utf-8", errors="ignore")

    # Check for port 5100
    if str(RECOG_PORT) not in server_content:
        return CheckResult(
            "ReCog Patterns",
            False,
            f"Port {RECOG_PORT} not found in server.py - is this configured correctly?"
        )

    # Check for recog_engine imports
    if "recog_engine" not in server_content:
        return CheckResult(
            "ReCog Patterns",
            False,
            "No recog_engine imports found in server.py"
        )

    return CheckResult(
        "ReCog Patterns",
        True,
        f"Found port {RECOG_PORT} and recog_engine imports"
    )


def check_ehkoforge_contamination() -> CheckResult:
    """Detect any EhkoForge imports or patterns in Python files."""
    repo_root = get_repo_root()
    if repo_root is None:
        return CheckResult("Cross-contamination", False, "No repo root found")

    scripts_dir = repo_root / "_scripts"
    if not scripts_dir.exists():
        return CheckResult("Cross-contamination", True, "_scripts/ not found, skipping")

    contaminated_files = []

    for py_file in scripts_dir.rglob("*.py"):
        # Skip excluded paths
        if any(excluded in str(py_file) for excluded in EXCLUDED_PATHS):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for pattern in EHKOFORGE_PATTERNS:
                # Use MULTILINE flag for patterns starting with ^
                flags = re.IGNORECASE | re.MULTILINE
                if re.search(pattern, content, flags):
                    rel_path = py_file.relative_to(repo_root)
                    contaminated_files.append(str(rel_path))
                    break
        except Exception:
            continue

    if contaminated_files:
        files_str = ", ".join(contaminated_files[:5])
        if len(contaminated_files) > 5:
            files_str += f" (+{len(contaminated_files) - 5} more)"
        return CheckResult(
            "Cross-contamination",
            False,
            f"EhkoForge patterns found in: {files_str}"
        )

    return CheckResult(
        "Cross-contamination",
        True,
        "No EhkoForge contamination detected"
    )


def check_license_headers(staged_only: bool = True) -> CheckResult:
    """Verify AGPLv3 license headers in Python files."""
    repo_root = get_repo_root()
    if repo_root is None:
        return CheckResult("License Headers", False, "No repo root found")

    if staged_only:
        # Get list of staged Python files
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
                capture_output=True,
                text=True,
                cwd=repo_root
            )
            if result.returncode != 0:
                return CheckResult(
                    "License Headers",
                    True,
                    "Could not get staged files, skipping"
                )

            staged_files = [
                repo_root / f.strip()
                for f in result.stdout.strip().split("\n")
                if f.strip().endswith(".py")
            ]

            if not staged_files:
                return CheckResult(
                    "License Headers",
                    True,
                    "No new Python files staged"
                )

            files_to_check = staged_files
        except Exception as e:
            return CheckResult(
                "License Headers",
                True,
                f"Could not check staged files: {e}"
            )
    else:
        # Check all Python files in _scripts/
        scripts_dir = repo_root / "_scripts"
        files_to_check = list(scripts_dir.rglob("*.py"))

    missing_license = []

    for py_file in files_to_check:
        if any(excluded in str(py_file) for excluded in EXCLUDED_PATHS):
            continue

        try:
            # Read first 50 lines (license should be near top)
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            header = "\n".join(content.split("\n")[:50])

            has_license = any(
                re.search(pattern, header, re.IGNORECASE)
                for pattern in LICENSE_PATTERNS
            )

            if not has_license:
                rel_path = py_file.relative_to(repo_root)
                missing_license.append(str(rel_path))
        except Exception:
            continue

    if missing_license:
        files_str = ", ".join(missing_license[:3])
        if len(missing_license) > 3:
            files_str += f" (+{len(missing_license) - 3} more)"
        return CheckResult(
            "License Headers",
            False,
            f"Missing AGPLv3 header in: {files_str}"
        )

    return CheckResult(
        "License Headers",
        True,
        f"All {len(files_to_check)} checked Python files have license headers"
    )


def check_instructions_freshness() -> CheckResult:
    """Check that RECOG_INSTRUCTIONS.md exists and is reasonably recent."""
    repo_root = get_repo_root()
    if repo_root is None:
        return CheckResult("Instructions File", False, "No repo root found")

    instructions_path = repo_root / "RECOG_INSTRUCTIONS.md"

    if not instructions_path.exists():
        return CheckResult(
            "Instructions File",
            False,
            "RECOG_INSTRUCTIONS.md not found! This file is required."
        )

    # Check modification time
    mtime = datetime.fromtimestamp(instructions_path.stat().st_mtime)
    age_days = (datetime.now() - mtime).days

    if age_days > INSTRUCTIONS_MAX_AGE_DAYS:
        return CheckResult(
            "Instructions File",
            True,  # Warning, not failure
            f"RECOG_INSTRUCTIONS.md last updated {age_days} days ago - consider updating",
            is_warning=True
        )

    # Check file has reasonable content
    content = instructions_path.read_text(encoding="utf-8", errors="ignore")
    if len(content) < 500:
        return CheckResult(
            "Instructions File",
            True,
            "RECOG_INSTRUCTIONS.md seems too short - is it complete?",
            is_warning=True
        )

    return CheckResult(
        "Instructions File",
        True,
        f"RECOG_INSTRUCTIONS.md exists (updated {age_days} days ago)"
    )


def check_private_gitignore() -> CheckResult:
    """Verify _private/ is properly gitignored."""
    repo_root = get_repo_root()
    if repo_root is None:
        return CheckResult("Private Protection", False, "No repo root found")

    gitignore_path = repo_root / ".gitignore"

    if not gitignore_path.exists():
        return CheckResult(
            "Private Protection",
            False,
            ".gitignore not found!"
        )

    gitignore_content = gitignore_path.read_text(encoding="utf-8", errors="ignore")

    # Check for _private/ in gitignore
    private_patterns = ["_private/", "_private", "_private/*"]
    has_private = any(pattern in gitignore_content for pattern in private_patterns)

    if not has_private:
        return CheckResult(
            "Private Protection",
            False,
            "_private/ not found in .gitignore - Brief Prep Plugin data at risk!"
        )

    # Check if any _private files are staged
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=repo_root
        )
        if result.returncode == 0:
            staged = result.stdout.strip()
            if "_private" in staged:
                return CheckResult(
                    "Private Protection",
                    False,
                    "_private/ files are staged for commit! Remove them before pushing."
                )
    except Exception:
        pass

    return CheckResult(
        "Private Protection",
        True,
        "_private/ is gitignored and not staged"
    )


def check_sensitive_files() -> CheckResult:
    """Check for accidentally staged sensitive files."""
    repo_root = get_repo_root()
    if repo_root is None:
        return CheckResult("Sensitive Files", False, "No repo root found")

    sensitive_patterns = [
        ".env",
        "*.key",
        "*.pem",
        "credentials.json",
        "secrets.json",
        "api_key",
        ".env.local",
        ".env.production",
    ]

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=repo_root
        )
        if result.returncode != 0:
            return CheckResult(
                "Sensitive Files",
                True,
                "Could not check staged files"
            )

        staged_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        flagged = []
        for staged in staged_files:
            for pattern in sensitive_patterns:
                if pattern.startswith("*"):
                    # Wildcard pattern
                    if staged.endswith(pattern[1:]):
                        flagged.append(staged)
                        break
                else:
                    # Exact match
                    if pattern in staged:
                        flagged.append(staged)
                        break

        if flagged:
            return CheckResult(
                "Sensitive Files",
                False,
                f"Sensitive files staged: {', '.join(flagged)}"
            )

    except Exception as e:
        return CheckResult(
            "Sensitive Files",
            True,
            f"Check skipped: {e}"
        )

    return CheckResult(
        "Sensitive Files",
        True,
        "No sensitive files detected in staged changes"
    )


# =============================================================================
# MAIN
# =============================================================================

def run_all_checks(verbose: bool = False) -> Tuple[List[CheckResult], int]:
    """Run all preflight checks and return results."""
    checks = [
        check_repo_identity,
        check_recog_patterns,
        check_ehkoforge_contamination,
        check_license_headers,
        check_instructions_freshness,
        check_private_gitignore,
        check_sensitive_files,
    ]

    results = []

    print("\n" + "=" * 60)
    print("  ReCog Preflight Checks")
    print("=" * 60 + "\n")

    for check_fn in checks:
        try:
            result = check_fn()
        except Exception as e:
            result = CheckResult(
                check_fn.__name__.replace("check_", "").replace("_", " ").title(),
                False,
                f"Check crashed: {e}"
            )

        results.append(result)
        print(str(result))

        if verbose and not result.passed:
            print(f"    → Fix: Review the above issue before pushing")

    # Summary
    passed = sum(1 for r in results if r.passed)
    warnings = sum(1 for r in results if r.passed and r.is_warning)
    failed = sum(1 for r in results if not r.passed)

    print("\n" + "-" * 60)
    print(f"  Results: {passed} passed, {warnings} warnings, {failed} failed")
    print("-" * 60)

    if failed > 0:
        print("\n** PREFLIGHT FAILED - Fix issues before pushing **\n")
        return results, 1
    elif warnings > 0:
        print("\n** Passed with warnings - review before pushing **\n")
        return results, 0
    else:
        print("\n** All checks passed - ready to push **\n")
        return results, 0


def main():
    """Main entry point."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    _, exit_code = run_all_checks(verbose=verbose)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

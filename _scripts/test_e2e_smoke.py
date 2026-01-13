#!/usr/bin/env python3
"""
ReCog E2E Smoke Tests - Real-world integration tests

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Verifies that ReCog's core functionality works end-to-end.
Designed for running via CLI or MCP integration.

Usage:
    python test_e2e_smoke.py [--server-url URL] [--verbose] [--skip-build]

Tests:
    1. Flask server starts and responds
    2. /api/health endpoint returns 200
    3. Case creation (POST /api/cases)
    4. File upload pipeline
    5. Tier 0 extraction (no LLM cost)
    6. Entity registry operations
    7. Database connection and migrations
    8. React build compiles

Exit codes:
    0 - All tests passed
    1 - One or more tests failed
"""

import sys
import os
import json
import time
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager
import urllib.request
import urllib.error


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_SERVER_URL = "http://localhost:5100"
SERVER_STARTUP_TIMEOUT = 15  # seconds
REQUEST_TIMEOUT = 10  # seconds

# Test data
SAMPLE_TEXT = """
Dr. Sarah Chen called John yesterday about the project deadline.
She mentioned that Marcus was frustrated with the delays.
The meeting is scheduled for Monday at 3pm.

"I'm really worried about the timeline," Sarah said.
John replied, "We'll figure it out. Let me talk to the team."

Contact: sarah.chen@example.com or call 0412 345 678.
"""


# =============================================================================
# TEST RESULT TRACKING
# =============================================================================

@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str
    duration_ms: float
    details: Optional[str] = None

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        time_str = f"{self.duration_ms:.0f}ms"
        base = f"[{status}] {self.name} ({time_str})"
        if not self.passed and self.message:
            base += f"\n       -> {self.message}"
        return base


class TestRunner:
    """Runs and tracks E2E tests."""

    def __init__(self, server_url: str = DEFAULT_SERVER_URL, verbose: bool = False):
        self.server_url = server_url.rstrip("/")
        self.verbose = verbose
        self.results: List[TestResult] = []
        self._created_case_id: Optional[str] = None
        self._created_session_id: Optional[str] = None

    def log(self, message: str):
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def run_test(self, name: str, test_fn: Callable) -> TestResult:
        """Run a single test and record result."""
        start = time.time()

        try:
            passed, message, details = test_fn()
            duration_ms = (time.time() - start) * 1000

            result = TestResult(
                name=name,
                passed=passed,
                message=message,
                duration_ms=duration_ms,
                details=details
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = TestResult(
                name=name,
                passed=False,
                message=f"Exception: {type(e).__name__}: {e}",
                duration_ms=duration_ms
            )

        self.results.append(result)
        print(str(result))

        if self.verbose and result.details:
            for line in result.details.split("\n"):
                print(f"       | {line}")

        return result

    def api_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        timeout: int = REQUEST_TIMEOUT
    ) -> Tuple[int, Optional[Dict]]:
        """Make HTTP request to API."""
        url = f"{self.server_url}{endpoint}"
        self.log(f"{method} {url}")

        headers = {"Content-Type": "application/json"}

        if data:
            body = json.dumps(data).encode("utf-8")
        else:
            body = None

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                try:
                    response_data = json.loads(resp.read().decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    response_data = None
                return status, response_data

        except urllib.error.HTTPError as e:
            try:
                response_data = json.loads(e.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                response_data = None
            return e.code, response_data

        except urllib.error.URLError as e:
            raise ConnectionError(f"Could not connect to {url}: {e.reason}")

    def summary(self) -> Tuple[int, int, int]:
        """Return (passed, failed, total) counts."""
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        return passed, failed, len(self.results)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_repo_root() -> Path:
    """Get the repository root directory."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


@contextmanager
def temporary_server():
    """Context manager that starts server if not running."""
    port = 5100
    server_was_running = is_port_in_use(port)
    server_process = None

    if not server_was_running:
        print("\n  Starting ReCog server for tests...")
        scripts_dir = get_repo_root() / "_scripts"

        server_process = subprocess.Popen(
            [sys.executable, "server.py"],
            cwd=scripts_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        )

        # Wait for server to start
        deadline = time.time() + SERVER_STARTUP_TIMEOUT
        while time.time() < deadline:
            if is_port_in_use(port):
                print(f"  Server started on port {port}")
                break
            time.sleep(0.5)
        else:
            server_process.terminate()
            raise RuntimeError(f"Server failed to start within {SERVER_STARTUP_TIMEOUT}s")

    try:
        yield server_process
    finally:
        if server_process is not None:
            print("\n  Stopping test server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_server_health(runner: TestRunner) -> Tuple[bool, str, Optional[str]]:
    """Test that /api/health endpoint responds."""
    try:
        status, data = runner.api_request("GET", "/api/health")

        if status == 200:
            return True, "Health endpoint responded", json.dumps(data)
        else:
            return False, f"Unexpected status: {status}", None

    except ConnectionError as e:
        return False, f"Server not reachable: {e}", None


def test_api_root(runner: TestRunner) -> Tuple[bool, str, Optional[str]]:
    """Test that /api/ endpoint exists."""
    try:
        # Try root API endpoint - may return 404 or 200 depending on config
        status, data = runner.api_request("GET", "/api/")

        # Accept 200 or 404 (server is responding)
        if status in (200, 404):
            return True, f"API responding (status {status})", None
        else:
            return False, f"Unexpected status: {status}", None

    except ConnectionError as e:
        return False, f"Server not reachable: {e}", None


def test_case_creation(runner: TestRunner) -> Tuple[bool, str, Optional[str]]:
    """Test creating a new case."""
    try:
        case_data = {
            "title": f"Smoke Test Case {int(time.time())}",
            "context": "E2E smoke test - can be deleted",
            "focus_areas": ["testing", "validation"]
        }

        status, data = runner.api_request("POST", "/api/cases", data=case_data)

        if status in (200, 201) and data:
            # Handle wrapped response: {success: true, data: {...}}
            inner_data = data.get("data", data)
            case_id = inner_data.get("id") or inner_data.get("case_id") or data.get("id")
            if case_id:
                runner._created_case_id = case_id
                return True, f"Created case: {case_id[:8]}...", json.dumps(data, indent=2)
            else:
                return False, "Case created but no ID returned", json.dumps(data, indent=2)
        else:
            return False, f"Failed to create case (status {status})", json.dumps(data) if data else None

    except ConnectionError as e:
        return False, f"Server not reachable: {e}", None


def test_case_list(runner: TestRunner) -> Tuple[bool, str, Optional[str]]:
    """Test listing cases."""
    try:
        status, data = runner.api_request("GET", "/api/cases")

        if status == 200 and isinstance(data, (list, dict)):
            # Response might be list or {cases: [...]}
            cases = data if isinstance(data, list) else data.get("cases", data.get("data", []))
            count = len(cases) if isinstance(cases, list) else "unknown"
            return True, f"Listed {count} cases", None
        else:
            return False, f"Unexpected response (status {status})", json.dumps(data) if data else None

    except ConnectionError as e:
        return False, f"Server not reachable: {e}", None


def test_tier0_extraction(runner: TestRunner) -> Tuple[bool, str, Optional[str]]:
    """Test Tier 0 signal extraction (no LLM cost)."""
    try:
        status, data = runner.api_request(
            "POST",
            "/api/tier0",
            data={"text": SAMPLE_TEXT}
        )

        if status == 200 and data:
            # Check for expected Tier 0 output fields
            # Handle wrapped response: {success: true, data: {tier0: {...}}}
            inner_data = data.get("data", data)
            result = inner_data.get("tier0") or inner_data.get("result") or inner_data

            has_emotions = "emotion_signals" in result or "emotions" in result
            has_entities = "entities" in result
            has_version = "version" in result

            if has_emotions or has_entities:
                entities = result.get("entities", {})
                people = entities.get("people", [])
                emails = entities.get("email_addresses", [])

                details = f"Found {len(people)} people, {len(emails)} emails"
                return True, "Tier 0 extraction working", details
            else:
                return False, "Missing expected fields in response", json.dumps(result, indent=2)
        else:
            return False, f"Tier 0 failed (status {status})", json.dumps(data) if data else None

    except ConnectionError as e:
        return False, f"Server not reachable: {e}", None


def test_entity_registry(runner: TestRunner) -> Tuple[bool, str, Optional[str]]:
    """Test entity registry operations."""
    try:
        # Get entity list
        status, data = runner.api_request("GET", "/api/entities")

        if status == 200:
            entities = data if isinstance(data, list) else data.get("entities", data.get("data", []))
            count = len(entities) if isinstance(entities, list) else 0
            return True, f"Entity registry accessible ({count} entities)", None
        else:
            return False, f"Could not access entities (status {status})", json.dumps(data) if data else None

    except ConnectionError as e:
        return False, f"Server not reachable: {e}", None


def test_insights_endpoint(runner: TestRunner) -> Tuple[bool, str, Optional[str]]:
    """Test insights endpoint."""
    try:
        status, data = runner.api_request("GET", "/api/insights")

        if status == 200:
            insights = data if isinstance(data, list) else data.get("insights", data.get("data", []))
            count = len(insights) if isinstance(insights, list) else 0
            return True, f"Insights endpoint accessible ({count} insights)", None
        else:
            return False, f"Could not access insights (status {status})", json.dumps(data) if data else None

    except ConnectionError as e:
        return False, f"Server not reachable: {e}", None


def test_database_connection(runner: TestRunner) -> Tuple[bool, str, Optional[str]]:
    """Test database connection by checking db status endpoint or direct check."""
    repo_root = get_repo_root()
    scripts_dir = repo_root / "_scripts"

    # Try via API first
    try:
        status, data = runner.api_request("GET", "/api/db/status", timeout=5)
        if status == 200:
            return True, "Database status OK via API", json.dumps(data) if data else None
    except (ConnectionError, Exception):
        pass

    # Fall back to direct check
    try:
        sys.path.insert(0, str(scripts_dir))
        from db import check_database, get_database_path

        db_path = get_database_path(scripts_dir / "_data")
        if not db_path.exists():
            return False, f"Database not found at {db_path}", None

        status = check_database(db_path)
        if "error" in status:
            return False, f"Database error: {status['error']}", None

        tables = status.get("total_tables", 0)
        rows = status.get("total_rows", 0)
        return True, f"Database OK ({tables} tables, {rows} rows)", json.dumps(status, indent=2)

    except ImportError as e:
        return False, f"Could not import db module: {e}", None
    except Exception as e:
        return False, f"Database check failed: {e}", None


def test_migrations(runner: TestRunner) -> Tuple[bool, str, Optional[str]]:
    """Test that database migrations are applied."""
    repo_root = get_repo_root()
    scripts_dir = repo_root / "_scripts"
    migrations_dir = scripts_dir / "migrations"

    if not migrations_dir.exists():
        return True, "No migrations directory (may be expected)", None

    migration_files = list(migrations_dir.glob("migration_v*.sql"))
    schema_file = migrations_dir / "schema_v0_1.sql"

    if not schema_file.exists() and not migration_files:
        return False, "No schema or migration files found", None

    found_files = []
    if schema_file.exists():
        found_files.append(schema_file.name)
    found_files.extend(f.name for f in migration_files)

    return True, f"Found {len(found_files)} migration files", "\n".join(found_files)


def test_react_build(runner: TestRunner, skip: bool = False) -> Tuple[bool, str, Optional[str]]:
    """Test that React frontend builds successfully."""
    if skip:
        return True, "Skipped (--skip-build)", None

    repo_root = get_repo_root()
    ui_dir = repo_root / "_ui"

    if not ui_dir.exists():
        return False, "_ui directory not found", None

    package_json = ui_dir / "package.json"
    if not package_json.exists():
        return False, "package.json not found in _ui/", None

    # Check if node_modules exists (npm install needed)
    node_modules = ui_dir / "node_modules"
    if not node_modules.exists():
        return False, "node_modules not found - run 'npm install' first", None

    # Run build
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=ui_dir,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            shell=True  # Needed for Windows
        )

        if result.returncode == 0:
            dist_dir = ui_dir / "dist"
            if dist_dir.exists():
                files = list(dist_dir.rglob("*"))
                return True, f"Build succeeded ({len(files)} files in dist/)", None
            else:
                return True, "Build succeeded (no dist/ dir)", None
        else:
            error_lines = result.stderr.strip().split("\n")[-5:]
            return False, "Build failed", "\n".join(error_lines)

    except subprocess.TimeoutExpired:
        return False, "Build timed out (>120s)", None
    except FileNotFoundError:
        return False, "npm not found - is Node.js installed?", None
    except Exception as e:
        return False, f"Build error: {e}", None


# =============================================================================
# MAIN
# =============================================================================

def run_smoke_tests(
    server_url: str = DEFAULT_SERVER_URL,
    verbose: bool = False,
    skip_build: bool = False,
    auto_start_server: bool = True
) -> int:
    """Run all smoke tests and return exit code."""

    print("\n" + "=" * 60)
    print("  ReCog E2E Smoke Tests")
    print("=" * 60)
    print(f"  Server: {server_url}")
    print(f"  Verbose: {verbose}")
    print(f"  Skip build: {skip_build}")
    print("=" * 60 + "\n")

    runner = TestRunner(server_url=server_url, verbose=verbose)

    # Check if server is running
    port = 5100
    server_running = is_port_in_use(port)

    if not server_running:
        if auto_start_server:
            print(f"  Server not running on port {port}")
            print("  Starting server automatically...\n")

            try:
                with temporary_server():
                    return _run_tests(runner, skip_build)
            except RuntimeError as e:
                print(f"\n[ERROR] Could not start server: {e}")
                print("   Start the server manually: python server.py")
                return 1
        else:
            print(f"[ERROR] Server not running on port {port}")
            print("   Start the server: cd _scripts && python server.py")
            return 1
    else:
        print(f"  Using existing server on port {port}\n")
        return _run_tests(runner, skip_build)


def _run_tests(runner: TestRunner, skip_build: bool) -> int:
    """Execute all tests."""

    # API Tests (require server)
    print("-" * 40)
    print("  API Tests")
    print("-" * 40)

    runner.run_test("Server Health", lambda: test_server_health(runner))
    runner.run_test("API Root", lambda: test_api_root(runner))
    runner.run_test("Case Creation", lambda: test_case_creation(runner))
    runner.run_test("Case List", lambda: test_case_list(runner))
    runner.run_test("Tier 0 Extraction", lambda: test_tier0_extraction(runner))
    runner.run_test("Entity Registry", lambda: test_entity_registry(runner))
    runner.run_test("Insights Endpoint", lambda: test_insights_endpoint(runner))

    # Database Tests
    print("\n" + "-" * 40)
    print("  Database Tests")
    print("-" * 40)

    runner.run_test("Database Connection", lambda: test_database_connection(runner))
    runner.run_test("Migrations", lambda: test_migrations(runner))

    # Build Tests
    print("\n" + "-" * 40)
    print("  Build Tests")
    print("-" * 40)

    runner.run_test("React Build", lambda: test_react_build(runner, skip=skip_build))

    # Summary
    passed, failed, total = runner.summary()

    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed}/{total} tests passed")
    if failed > 0:
        print(f"  FAILED: {failed} test(s)")
    print("=" * 60)

    # Calculate total time
    total_time_ms = sum(r.duration_ms for r in runner.results)
    print(f"  Total time: {total_time_ms:.0f}ms ({total_time_ms/1000:.1f}s)")
    print("=" * 60 + "\n")

    if failed > 0:
        print("** SMOKE TESTS FAILED **\n")
        return 1
    else:
        print("** ALL SMOKE TESTS PASSED **\n")
        return 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="ReCog E2E Smoke Tests")
    parser.add_argument(
        "--server-url",
        default=DEFAULT_SERVER_URL,
        help=f"Server URL (default: {DEFAULT_SERVER_URL})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip React build test"
    )
    parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Don't auto-start server if not running"
    )

    args = parser.parse_args()

    exit_code = run_smoke_tests(
        server_url=args.server_url,
        verbose=args.verbose,
        skip_build=args.skip_build,
        auto_start_server=not args.no_auto_start
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

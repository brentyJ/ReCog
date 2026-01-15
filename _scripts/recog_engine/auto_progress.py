"""
ReCog Engine - Auto Progress Worker v0.8

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Background worker that polls for cases and auto-advances them through
the processing pipeline based on completion conditions.

Run as: python -m recog_engine.auto_progress
Or integrate into worker.py as a thread.
"""

import os
import sys
import time
import signal
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from recog_engine.state_machine import CaseStateMachine
from recog_engine.core.providers import load_env_file

# =============================================================================
# CONFIGURATION
# =============================================================================

_scripts_dir = Path(__file__).parent.parent
load_env_file(_scripts_dir / ".env")


class AutoProgressConfig:
    """Auto-progress worker configuration."""
    DATA_DIR = Path(os.environ.get("RECOG_DATA_DIR", "./_data"))
    DB_PATH = DATA_DIR / "recog.db"

    # Polling interval in seconds
    POLL_INTERVAL = int(os.environ.get("RECOG_AUTO_PROGRESS_INTERVAL", 10))

    # Max age for cases to consider (hours)
    MAX_CASE_AGE_HOURS = 24


# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AUTO-PROGRESS] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# WORKER STATE
# =============================================================================

class WorkerState:
    """Track worker state."""

    def __init__(self):
        self.running = True
        self.cycles = 0
        self.advances = 0
        self.started_at = datetime.now(timezone.utc)

    def stats(self):
        runtime = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return {
            "cycles": self.cycles,
            "advances": self.advances,
            "runtime_seconds": round(runtime, 1),
        }


state = WorkerState()


# =============================================================================
# SIGNAL HANDLING
# =============================================================================

def shutdown_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received...")
    state.running = False


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


# =============================================================================
# DATABASE HELPERS
# =============================================================================

def get_connection() -> sqlite3.Connection:
    """Create database connection."""
    conn = sqlite3.connect(str(AutoProgressConfig.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# AUTO-PROGRESS LOGIC
# =============================================================================

def check_scanning_cases(conn: sqlite3.Connection, state_machine: CaseStateMachine):
    """
    Check cases in 'scanning' state.

    Tier 0 runs synchronously during upload, so scanning cases can advance
    immediately to clarifying or processing based on entity status.
    """
    cases = conn.execute("""
        SELECT c.id, ps.unknown_entities_count
        FROM cases c
        LEFT JOIN preflight_sessions ps ON ps.case_id = c.id
        WHERE c.state = 'scanning'
        ORDER BY c.updated_at DESC
    """).fetchall()

    for case in cases:
        case_id = case["id"]
        unknown_count = case["unknown_entities_count"] or 0

        # Tier 0 is complete (runs during upload)
        # Decide next state based on unknown entities
        if unknown_count > 0:
            if state_machine.advance_case(case_id, {
                "tier0_complete": True,
                "unknown_entities": True
            }):
                logger.info(f"Case {case_id}: scanning -> clarifying ({unknown_count} unknown entities)")
                state.advances += 1
        else:
            if state_machine.advance_case(case_id, {
                "tier0_complete": True,
                "unknown_entities": False
            }):
                logger.info(f"Case {case_id}: scanning -> processing (no unknown entities)")
                state.advances += 1


def check_clarifying_cases(conn: sqlite3.Connection, state_machine: CaseStateMachine):
    """
    Check cases in 'clarifying' state.

    Advances to processing when all entities are confirmed.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=AutoProgressConfig.MAX_CASE_AGE_HOURS)).isoformat()

    cases = conn.execute("""
        SELECT id FROM cases
        WHERE state = 'clarifying'
          AND last_activity > ?
    """, (cutoff,)).fetchall()

    for case in cases:
        case_id = case["id"]

        # Check if entities are clarified
        # Option 1: Check unknown_entities_count in preflight session
        session = conn.execute("""
            SELECT unknown_entities_count
            FROM preflight_sessions
            WHERE case_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (case_id,)).fetchone()

        unknown_count = session["unknown_entities_count"] if session else 0

        # Option 2: Check if user has confirmed entities in registry
        # (This is a simplification - real implementation might check
        # specific entities from the preflight items)

        if unknown_count == 0:
            if state_machine.advance_case(case_id, {"entities_clarified": True}):
                logger.info(f"Case {case_id}: clarifying -> processing (entities clarified)")
                state.advances += 1


def check_processing_cases(conn: sqlite3.Connection, state_machine: CaseStateMachine):
    """
    Check cases in 'processing' state.

    Advances to complete when:
    1. All extraction jobs are done
    2. Synthesis has run (or no insights to synthesize)
    """
    cases = conn.execute("""
        SELECT id FROM cases WHERE state = 'processing'
    """).fetchall()

    for case in cases:
        case_id = case["id"]

        # Check if extraction is complete
        pending_extract = conn.execute("""
            SELECT COUNT(*) as count
            FROM processing_queue
            WHERE case_id = ?
              AND operation_type = 'extract'
              AND status IN ('pending', 'processing')
        """, (case_id,)).fetchone()["count"]

        if pending_extract > 0:
            continue  # Still extracting

        # Check if synthesis is complete or not needed
        pending_synth = conn.execute("""
            SELECT COUNT(*) as count
            FROM processing_queue
            WHERE case_id = ?
              AND operation_type = 'synthesize'
              AND status IN ('pending', 'processing')
        """, (case_id,)).fetchone()["count"]

        # Check progress tracker
        progress = conn.execute("""
            SELECT stage, status
            FROM case_progress
            WHERE case_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (case_id,)).fetchone()

        # If extraction is done and (synthesis is done or no synthesis jobs)
        extraction_done = pending_extract == 0
        synthesis_done = pending_synth == 0

        # Queue synthesis if extraction done but no synthesis queued yet
        if extraction_done and not synthesis_done:
            continue  # Wait for synthesis

        # Check if we should queue synthesis
        if extraction_done:
            # Check if synthesis was ever queued
            synth_jobs = conn.execute("""
                SELECT COUNT(*) as count
                FROM processing_queue
                WHERE case_id = ? AND operation_type = 'synthesize'
            """, (case_id,)).fetchone()["count"]

            if synth_jobs == 0:
                # Queue synthesis job
                now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                try:
                    conn.execute("""
                        INSERT INTO processing_queue
                        (operation_type, source_type, source_id, status, priority, case_id, queued_at)
                        VALUES ('synthesize', 'auto', ?, 'pending', 0, ?, ?)
                    """, (case_id, case_id, now))
                    conn.commit()
                    logger.info(f"Case {case_id}: queued synthesis job")
                except sqlite3.IntegrityError:
                    pass  # Already exists
                continue

        # All done - advance to complete
        if extraction_done and synthesis_done:
            if state_machine.advance_case(case_id, {"synthesis_complete": True}):
                logger.info(f"Case {case_id}: processing -> complete")
                state.advances += 1


def run_progress_cycle(state_machine: CaseStateMachine):
    """Run one cycle of auto-progress checks."""
    conn = get_connection()
    try:
        check_scanning_cases(conn, state_machine)
        check_clarifying_cases(conn, state_machine)
        check_processing_cases(conn, state_machine)
    except Exception as e:
        logger.error(f"Error in progress cycle: {e}")
    finally:
        conn.close()


# =============================================================================
# MAIN WORKER LOOP
# =============================================================================

def run_auto_progress_worker(interval: int = None):
    """
    Main auto-progress worker loop.

    Args:
        interval: Poll interval in seconds (default from config)
    """
    interval = interval or AutoProgressConfig.POLL_INTERVAL
    state_machine = CaseStateMachine(AutoProgressConfig.DB_PATH)

    logger.info("=" * 50)
    logger.info("Auto-Progress Worker Started")
    logger.info("=" * 50)
    logger.info(f"Database: {AutoProgressConfig.DB_PATH}")
    logger.info(f"Poll interval: {interval}s")
    logger.info("=" * 50)

    while state.running:
        try:
            run_progress_cycle(state_machine)
            state.cycles += 1
        except Exception as e:
            logger.exception(f"Error in worker loop: {e}")

        # Sleep in small increments to respond to shutdown quickly
        for _ in range(interval * 2):
            if not state.running:
                break
            time.sleep(0.5)

    # Shutdown
    logger.info("=" * 50)
    logger.info("Auto-Progress Worker Shutdown")
    stats = state.stats()
    logger.info(f"Cycles: {stats['cycles']}")
    logger.info(f"Advances: {stats['advances']}")
    logger.info(f"Runtime: {stats['runtime_seconds']}s")
    logger.info("=" * 50)


# =============================================================================
# SINGLE-PASS FUNCTION (for integration)
# =============================================================================

def run_single_pass(db_path: Path = None):
    """
    Run a single pass of auto-progress checks.

    Useful for integration into existing worker or testing.

    Args:
        db_path: Optional database path override
    """
    db_path = db_path or AutoProgressConfig.DB_PATH
    state_machine = CaseStateMachine(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        check_scanning_cases(conn, state_machine)
        check_clarifying_cases(conn, state_machine)
        check_processing_cases(conn, state_machine)
    finally:
        conn.close()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_auto_progress_worker()

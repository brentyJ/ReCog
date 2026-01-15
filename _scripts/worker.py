"""
ReCog Worker - Background Queue Processor

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Processes items from the processing_queue table:
- Extract: Run LLM insight extraction
- Correlate: Find patterns across insights (future)
- Synthesize: Generate summaries (future)

Run: python worker.py
"""

import os
import sys
import json
import time
import signal
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

# ReCog imports
from recog_engine import (
    preprocess_text,
    build_extraction_prompt,
    parse_extraction_response,
    InsightStore,
    SynthEngine,
    ClusterStrategy,
)
from recog_engine.case_store import CaseStore
from recog_engine.timeline_store import TimelineStore
from recog_engine.state_machine import CaseStateMachine
from recog_engine.cost_estimator import CostEstimator
from recog_engine.core.providers import (
    create_provider,
    get_available_providers,
    load_env_file,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

_scripts_dir = Path(__file__).parent
load_env_file(_scripts_dir / ".env")


class WorkerConfig:
    """Worker configuration."""
    DATA_DIR = Path(os.environ.get("RECOG_DATA_DIR", "./_data"))
    DB_PATH = DATA_DIR / "recog.db"
    
    # Polling
    POLL_INTERVAL_SECONDS = int(os.environ.get("RECOG_WORKER_POLL", 5))
    BATCH_SIZE = int(os.environ.get("RECOG_WORKER_BATCH", 10))
    
    # Cost controls
    COST_LIMIT_CENTS = int(os.environ.get("RECOG_COST_LIMIT_CENTS", 100))
    MAX_RETRIES = 3
    
    # LLM
    DEFAULT_PROVIDER = os.environ.get("RECOG_LLM_PROVIDER", "openai")
    AVAILABLE_PROVIDERS = get_available_providers()


# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# WORKER STATE
# =============================================================================

class WorkerState:
    """Track worker state and costs."""
    
    def __init__(self):
        self.running = True
        self.processed_count = 0
        self.failed_count = 0
        self.total_cost_cents = 0.0
        self.started_at = datetime.now(timezone.utc)
    
    def add_cost(self, cents: float):
        self.total_cost_cents += cents
    
    def is_over_budget(self) -> bool:
        return self.total_cost_cents >= WorkerConfig.COST_LIMIT_CENTS
    
    def stats(self) -> Dict[str, Any]:
        runtime = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return {
            "processed": self.processed_count,
            "failed": self.failed_count,
            "cost_cents": round(self.total_cost_cents, 4),
            "budget_remaining": round(WorkerConfig.COST_LIMIT_CENTS - self.total_cost_cents, 4),
            "runtime_seconds": round(runtime, 1),
        }


state = WorkerState()


# =============================================================================
# SIGNAL HANDLING
# =============================================================================

def shutdown_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received, finishing current job...")
    state.running = False


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


# =============================================================================
# DATABASE HELPERS
# =============================================================================

def get_connection() -> sqlite3.Connection:
    """Create database connection."""
    conn = sqlite3.connect(str(WorkerConfig.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def fetch_pending_jobs(conn: sqlite3.Connection, limit: int) -> list:
    """Fetch pending jobs from queue, ordered by priority."""
    cursor = conn.execute("""
        SELECT * FROM processing_queue
        WHERE status = 'pending'
        ORDER BY priority DESC, queued_at ASC
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()


def update_job_status(
    conn: sqlite3.Connection,
    job_id: int,
    status: str,
    notes: Optional[str] = None,
    increment_pass: bool = False,
):
    """Update job status."""
    now = datetime.now(timezone.utc).isoformat() + "Z"
    
    if increment_pass:
        conn.execute("""
            UPDATE processing_queue
            SET status = ?, last_processed_at = ?, notes = ?, pass_count = pass_count + 1
            WHERE id = ?
        """, (status, now, notes, job_id))
    else:
        conn.execute("""
            UPDATE processing_queue
            SET status = ?, last_processed_at = ?, notes = ?
            WHERE id = ?
        """, (status, now, notes, job_id))
    
    conn.commit()


def get_source_content(conn: sqlite3.Connection, source_type: str, source_id: str) -> Optional[str]:
    """Fetch content for a source."""
    if source_type == "preflight_item":
        cursor = conn.execute(
            "SELECT content FROM preflight_items WHERE id = ?",
            (source_id,)
        )
        row = cursor.fetchone()
        return row["content"] if row else None
    
    elif source_type == "document_chunk":
        cursor = conn.execute(
            "SELECT content FROM document_chunks WHERE id = ?",
            (source_id,)
        )
        row = cursor.fetchone()
        return row["content"] if row else None
    
    else:
        logger.warning(f"Unknown source type: {source_type}")
        return None


# =============================================================================
# JOB PROCESSORS
# =============================================================================

# Global stores (initialized in run_worker)
synth_engine: Optional[SynthEngine] = None
case_store: Optional[CaseStore] = None
timeline_store: Optional[TimelineStore] = None
state_machine: Optional[CaseStateMachine] = None
cost_estimator_instance: Optional[CostEstimator] = None


def process_extract_job(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    provider,
    insight_store: InsightStore,
    case_store: CaseStore,
    timeline_store: TimelineStore,
) -> Dict[str, Any]:
    """
    Process an extraction job.

    Returns dict with 'success', 'insights_count', 'cost_cents', 'error'.
    """
    source_type = job["source_type"]
    source_id = job["source_id"]
    case_id = job["case_id"] if "case_id" in job.keys() else None

    # Fetch content
    content = get_source_content(conn, source_type, source_id)
    if not content:
        return {"success": False, "error": f"No content found for {source_type}:{source_id}"}

    # Get or run Tier 0
    pre_annotation = None
    if job["pre_annotation_json"]:
        try:
            pre_annotation = json.loads(job["pre_annotation_json"])
        except json.JSONDecodeError:
            pass

    if not pre_annotation:
        pre_annotation = preprocess_text(content)

    # Get case context if case_id provided
    case_context = None
    if case_id:
        case_obj = case_store.get_case(case_id)
        if case_obj:
            case_context = {
                "title": case_obj.title,
                "context": case_obj.context,
                "focus_areas": case_obj.focus_areas or [],
            }
            logger.info(f"Injecting case context: {case_obj.title}")

    # Build prompt with case context
    prompt = build_extraction_prompt(content, pre_annotation, case_context=case_context)

    # Call LLM
    try:
        response = provider.generate_json(
            prompt=prompt,
            system="You are an insight extraction engine. Extract meaningful insights from personal reflections.",
        )
    except Exception as e:
        return {"success": False, "error": f"LLM error: {str(e)}"}

    # Parse response
    insights = parse_extraction_response(response.content, source_type, source_id)

    # Save insights with case_id
    saved = insight_store.save_insights_batch(insights, check_similarity=True, case_id=case_id)

    # Log timeline event if case_id provided and insights were created
    if case_id and saved.get("created", 0) > 0:
        timeline_store.log_event(
            case_id,
            "insights_extracted",
            {
                "count": saved.get("created", 0),
                "source_type": source_type,
                "source_id": source_id,
            },
        )

    # Calculate cost
    cost_cents = response.cost_estimate_cents or 0

    return {
        "success": True,
        "insights_count": saved["created"] + saved["merged"],
        "created": saved["created"],
        "merged": saved["merged"],
        "cost_cents": cost_cents,
        "tokens": response.total_tokens,
        "case_id": case_id,
    }


def process_synthesize_job(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    provider,
    synth: SynthEngine,
) -> Dict[str, Any]:
    """
    Process a synthesis job.
    
    Synthesize jobs run pattern synthesis on insight clusters.
    The source_type should be 'cluster' and source_id is the cluster_id,
    OR source_type is 'auto' for automatic clustering and synthesis.
    
    Returns dict with 'success', 'patterns_count', 'cost_cents', 'error'.
    """
    source_type = job["source_type"]
    source_id = job["source_id"]
    
    try:
        if source_type == "auto":
            # Run full synthesis cycle
            strategy_str = source_id or "auto"
            try:
                strategy = ClusterStrategy(strategy_str)
            except ValueError:
                strategy = ClusterStrategy.AUTO
            
            result = synth.run_synthesis(
                provider=provider,
                strategy=strategy,
                min_cluster_size=3,
                max_clusters=5,  # Limit per job
            )
            
            return {
                "success": result.success,
                "patterns_count": result.patterns_created,
                "clusters_processed": result.clusters_processed,
                "cost_cents": 0,  # TODO: Track synthesis costs
                "tokens": 0,
            }
        
        elif source_type == "cluster":
            # Synthesize specific cluster
            clusters = synth.get_pending_clusters(limit=100)
            target_cluster = None
            
            for c in clusters:
                if c.id == source_id:
                    target_cluster = c
                    break
            
            if not target_cluster:
                return {"success": False, "error": f"Cluster not found: {source_id}"}
            
            patterns = synth.synthesize_cluster(target_cluster, provider)
            
            if patterns:
                save_result = synth.save_patterns_batch(patterns)
                synth._update_cluster_status(source_id, "complete")
                
                return {
                    "success": True,
                    "patterns_count": save_result["saved"],
                    "cost_cents": 0,
                    "tokens": 0,
                }
            else:
                synth._update_cluster_status(source_id, "failed")
                return {"success": False, "error": "No patterns generated"}
        
        else:
            return {"success": False, "error": f"Unknown synth source type: {source_type}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


def process_job(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    provider,
    insight_store: InsightStore,
) -> bool:
    """
    Process a single job.

    Returns True if successful, False otherwise.
    """
    job_id = job["id"]
    op_type = job["operation_type"]
    case_id = job["case_id"] if "case_id" in job.keys() else None

    logger.info(f"Processing job {job_id}: {op_type} ({job['source_type']}:{job['source_id']})")

    # Mark as processing
    update_job_status(conn, job_id, "processing")

    # v0.8: Update case progress if case_id present
    if case_id and state_machine:
        _update_case_progress(conn, case_id, op_type, job["source_id"])

    try:
        if op_type == "extract":
            result = process_extract_job(conn, job, provider, insight_store, case_store, timeline_store)
        elif op_type == "synthesize":
            result = process_synthesize_job(conn, job, provider, synth_engine)
        elif op_type == "correlate":
            # TODO: Implement correlation
            result = {"success": False, "error": "Correlation not yet implemented"}
        else:
            result = {"success": False, "error": f"Unknown operation type: {op_type}"}

        if result["success"]:
            notes = json.dumps({
                "insights": result.get("insights_count", 0),
                "created": result.get("created", 0),
                "merged": result.get("merged", 0),
                "cost_cents": result.get("cost_cents", 0),
                "tokens": result.get("tokens", 0),
            })
            update_job_status(conn, job_id, "complete", notes=notes, increment_pass=True)
            state.processed_count += 1
            state.add_cost(result.get("cost_cents", 0))

            # v0.8: Record actual cost and update progress
            if case_id and cost_estimator_instance:
                cost_usd = result.get("cost_cents", 0) / 100
                cost_estimator_instance.record_actual_cost(case_id, cost_usd, op_type)

                # Update progress with recent insight
                recent_insight = None
                if result.get("insights_count", 0) > 0:
                    # Get the most recent insight for this case
                    recent = conn.execute("""
                        SELECT summary FROM insights
                        WHERE case_id = ?
                        ORDER BY created_at DESC LIMIT 1
                    """, (case_id,)).fetchone()
                    if recent:
                        recent_insight = recent["summary"][:100]

                _update_case_progress_complete(conn, case_id, op_type, recent_insight)

            logger.info(f"  ✓ Completed: {result.get('insights_count', 0)} insights, ${result.get('cost_cents', 0)/100:.4f}")
            return True
        else:
            # Check retry count
            pass_count = job["pass_count"] or 0
            if pass_count < WorkerConfig.MAX_RETRIES:
                update_job_status(conn, job_id, "pending", notes=result.get("error"), increment_pass=True)
                logger.warning(f"  ⚠ Failed (will retry): {result.get('error')}")
            else:
                update_job_status(conn, job_id, "failed", notes=result.get("error"), increment_pass=True)
                state.failed_count += 1
                logger.error(f"  ✗ Failed (max retries): {result.get('error')}")
            return False

    except Exception as e:
        logger.exception(f"  ✗ Exception processing job {job_id}")
        update_job_status(conn, job_id, "failed", notes=str(e), increment_pass=True)
        state.failed_count += 1
        return False


def _update_case_progress(conn: sqlite3.Connection, case_id: str, stage: str, current_item: str):
    """Update case progress when starting a job."""
    now = datetime.now(timezone.utc).isoformat() + "Z"

    # Get or create progress record
    progress = conn.execute("""
        SELECT id, completed_items, total_items FROM case_progress
        WHERE case_id = ? AND stage = ?
        ORDER BY updated_at DESC LIMIT 1
    """, (case_id, stage)).fetchone()

    if progress:
        # Update existing progress
        completed = progress["completed_items"] or 0
        total = progress["total_items"] or 1
        new_progress = min(completed / total, 0.99)  # Cap at 99% until complete

        conn.execute("""
            UPDATE case_progress
            SET status = 'running', current_item = ?, progress = ?, updated_at = ?
            WHERE id = ?
        """, (current_item, new_progress, now, progress["id"]))
    else:
        # Get total items for this case/stage
        if stage == "extract":
            total = conn.execute("""
                SELECT COUNT(*) FROM processing_queue
                WHERE case_id = ? AND operation_type = 'extract'
            """, (case_id,)).fetchone()[0]
        else:
            total = 1

        # Create new progress record
        from uuid import uuid4
        conn.execute("""
            INSERT INTO case_progress
            (id, case_id, stage, status, total_items, completed_items, progress, current_item, created_at, updated_at)
            VALUES (?, ?, ?, 'running', ?, 0, 0.0, ?, ?, ?)
        """, (str(uuid4()), case_id, stage, total, current_item, now, now))

    conn.commit()


def _update_case_progress_complete(conn: sqlite3.Connection, case_id: str, stage: str, recent_insight: str = None):
    """Update case progress when completing a job."""
    now = datetime.now(timezone.utc).isoformat() + "Z"

    progress = conn.execute("""
        SELECT id, completed_items, total_items FROM case_progress
        WHERE case_id = ? AND stage = ?
        ORDER BY updated_at DESC LIMIT 1
    """, (case_id, stage)).fetchone()

    if progress:
        completed = (progress["completed_items"] or 0) + 1
        total = progress["total_items"] or 1
        new_progress = min(completed / total, 1.0)
        status = "complete" if completed >= total else "running"

        conn.execute("""
            UPDATE case_progress
            SET status = ?, completed_items = ?, progress = ?, recent_insight = ?, updated_at = ?
            WHERE id = ?
        """, (status, completed, new_progress, recent_insight, now, progress["id"]))
        conn.commit()


# =============================================================================
# MAIN LOOP
# =============================================================================

def run_worker():
    """Main worker loop."""
    logger.info("=" * 60)
    logger.info("ReCog Worker Starting")
    logger.info("=" * 60)
    logger.info(f"Database: {WorkerConfig.DB_PATH}")
    logger.info(f"Poll interval: {WorkerConfig.POLL_INTERVAL_SECONDS}s")
    logger.info(f"Batch size: {WorkerConfig.BATCH_SIZE}")
    logger.info(f"Cost limit: ${WorkerConfig.COST_LIMIT_CENTS/100:.2f}")
    logger.info(f"Available providers: {', '.join(WorkerConfig.AVAILABLE_PROVIDERS) or 'none'}")
    
    if not WorkerConfig.AVAILABLE_PROVIDERS:
        logger.error("No LLM providers configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")
        sys.exit(1)
    
    # Create provider
    provider = create_provider(WorkerConfig.DEFAULT_PROVIDER)
    if not provider:
        provider = create_provider()  # Use any available
    
    logger.info(f"Using provider: {provider.__class__.__name__}")
    logger.info("=" * 60)
    
    # Create stores
    global synth_engine, case_store, timeline_store, state_machine, cost_estimator_instance
    insight_store = InsightStore(WorkerConfig.DB_PATH)
    case_store = CaseStore(WorkerConfig.DB_PATH)
    timeline_store = TimelineStore(WorkerConfig.DB_PATH)
    synth_engine = SynthEngine(WorkerConfig.DB_PATH, insight_store)
    state_machine = CaseStateMachine(WorkerConfig.DB_PATH)
    cost_estimator_instance = CostEstimator(WorkerConfig.DB_PATH)
    
    while state.running:
        # Check budget
        if state.is_over_budget():
            logger.warning(f"Cost limit reached (${state.total_cost_cents/100:.2f}). Stopping.")
            break
        
        conn = get_connection()
        try:
            # Fetch jobs
            jobs = fetch_pending_jobs(conn, WorkerConfig.BATCH_SIZE)
            
            if not jobs:
                # No work, sleep
                conn.close()
                time.sleep(WorkerConfig.POLL_INTERVAL_SECONDS)
                continue
            
            logger.info(f"Found {len(jobs)} pending jobs")
            
            # Process jobs
            for job in jobs:
                if not state.running:
                    break
                if state.is_over_budget():
                    break
                    
                process_job(conn, job, provider, insight_store)
            
        except Exception as e:
            logger.exception("Error in worker loop")
            time.sleep(WorkerConfig.POLL_INTERVAL_SECONDS)
        finally:
            conn.close()
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("Worker Shutdown")
    stats = state.stats()
    logger.info(f"Processed: {stats['processed']}")
    logger.info(f"Failed: {stats['failed']}")
    logger.info(f"Total cost: ${stats['cost_cents']/100:.4f}")
    logger.info(f"Runtime: {stats['runtime_seconds']}s")
    logger.info("=" * 60)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_worker()

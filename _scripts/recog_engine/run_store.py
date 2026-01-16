"""
Extraction Run Store - Manages versioned extraction runs.

Tracks extraction passes with their context configurations, enabling
comparison between runs to understand how context affects synthesis.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get database connection with row factory."""
    if db_path is None:
        db_path = Path(__file__).parent.parent / "_data" / "recog.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# EXTRACTION RUNS
# =============================================================================

def create_run(
    name: str,
    description: str = "",
    context_config: Optional[Dict] = None,
    source_description: str = "",
    parent_run_id: Optional[str] = None,
    db_path: Optional[Path] = None
) -> str:
    """
    Create a new extraction run.

    Args:
        name: Human-friendly name (e.g., "Baseline - Pure Extraction")
        description: What context/changes were made
        context_config: Dict of context configuration (will be JSON serialized)
        source_description: Description of source data
        parent_run_id: Previous run to compare against

    Returns:
        Run ID
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    run_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO extraction_runs
        (id, name, description, context_config_json, source_description,
         parent_run_id, status, started_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)
    """, (
        run_id, name, description,
        json.dumps(context_config) if context_config else None,
        source_description, parent_run_id, now, now
    ))

    conn.commit()
    conn.close()

    return run_id


def complete_run(
    run_id: str,
    insight_count: int = 0,
    pattern_count: int = 0,
    db_path: Optional[Path] = None
) -> None:
    """Mark a run as complete with result counts."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE extraction_runs
        SET status = 'complete',
            completed_at = ?,
            insight_count = ?,
            pattern_count = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), insight_count, pattern_count, run_id))

    conn.commit()
    conn.close()


def get_run(run_id: str, db_path: Optional[Path] = None) -> Optional[Dict]:
    """Get a run by ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM extraction_runs WHERE id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def list_runs(db_path: Optional[Path] = None) -> List[Dict]:
    """List all extraction runs, newest first."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM extraction_runs
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_run_lineage(run_id: str, db_path: Optional[Path] = None) -> List[Dict]:
    """Get the lineage chain of a run (from baseline to current)."""
    runs = []
    current_id = run_id

    while current_id:
        run = get_run(current_id, db_path)
        if run:
            runs.insert(0, run)  # Insert at start to maintain order
            current_id = run.get('parent_run_id')
        else:
            break

    return runs


# =============================================================================
# LIFE CONTEXT
# =============================================================================

def add_life_context(
    title: str,
    start_date: str,
    context_type: str,
    end_date: Optional[str] = None,
    description: str = "",
    location: str = "",
    tags: Optional[List[str]] = None,
    db_path: Optional[Path] = None
) -> str:
    """
    Add a life context event for timeline injection.

    Args:
        title: Short title (e.g., "NZ Police Officer")
        start_date: YYYY-MM-DD format
        context_type: 'career', 'relationship', 'residence', 'education', 'health', 'event'
        end_date: YYYY-MM-DD format or None if ongoing
        description: More details
        location: Where this occurred
        tags: List of tags for categorization

    Returns:
        Context ID
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    context_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO life_context
        (id, start_date, end_date, title, description, location,
         context_type, tags_json, active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (
        context_id, start_date, end_date, title, description, location,
        context_type, json.dumps(tags) if tags else None, now, now
    ))

    conn.commit()
    conn.close()

    return context_id


def get_life_context_for_date(
    date: str,
    db_path: Optional[Path] = None
) -> List[Dict]:
    """Get all active life context events that overlap with a given date."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM life_context
        WHERE active = 1
          AND start_date <= ?
          AND (end_date IS NULL OR end_date >= ?)
        ORDER BY context_type, start_date
    """, (date, date))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_all_life_context(db_path: Optional[Path] = None) -> List[Dict]:
    """Get all life context events."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM life_context
        ORDER BY start_date DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def build_life_context_prompt(date: str, db_path: Optional[Path] = None) -> str:
    """
    Build a prompt section with life context for a given date.

    Returns a formatted string describing what was happening in the subject's
    life at the specified date.
    """
    contexts = get_life_context_for_date(date, db_path)

    if not contexts:
        return ""

    lines = ["## Life Context at Time of Content\n"]

    # Group by type
    by_type = {}
    for ctx in contexts:
        t = ctx['context_type']
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(ctx)

    type_labels = {
        'career': 'Career',
        'relationship': 'Relationships',
        'residence': 'Location',
        'education': 'Education',
        'health': 'Health',
        'event': 'Life Events'
    }

    for ctx_type, label in type_labels.items():
        if ctx_type in by_type:
            lines.append(f"**{label}:**")
            for ctx in by_type[ctx_type]:
                loc = f" ({ctx['location']})" if ctx['location'] else ""
                lines.append(f"- {ctx['title']}{loc}")
                if ctx['description']:
                    lines.append(f"  {ctx['description']}")
            lines.append("")

    return "\n".join(lines)


# =============================================================================
# RUN DELTAS
# =============================================================================

def record_delta(
    run_id: str,
    parent_run_id: str,
    delta_type: str,
    entity_type: str,
    change_summary: str,
    entity_id: Optional[str] = None,
    old_value: Optional[Dict] = None,
    new_value: Optional[Dict] = None,
    attributed_to: Optional[str] = None,
    db_path: Optional[Path] = None
) -> str:
    """
    Record a change between extraction runs.

    Args:
        run_id: New run ID
        parent_run_id: Baseline run ID
        delta_type: Type of change (insight_added, insight_modified, etc.)
        entity_type: 'insight' or 'pattern'
        change_summary: Human-readable description
        entity_id: Specific insight/pattern ID
        old_value: Previous state (dict, will be JSON serialized)
        new_value: New state (dict, will be JSON serialized)
        attributed_to: What caused this change (e.g., "age_context")

    Returns:
        Delta ID
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    delta_id = str(uuid.uuid4())

    cursor.execute("""
        INSERT INTO run_deltas
        (id, run_id, parent_run_id, delta_type, entity_type, entity_id,
         change_summary, old_value_json, new_value_json, attributed_to, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        delta_id, run_id, parent_run_id, delta_type, entity_type, entity_id,
        change_summary,
        json.dumps(old_value) if old_value else None,
        json.dumps(new_value) if new_value else None,
        attributed_to,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    return delta_id


def get_run_deltas(run_id: str, db_path: Optional[Path] = None) -> List[Dict]:
    """Get all deltas for a specific run."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM run_deltas
        WHERE run_id = ?
        ORDER BY created_at
    """, (run_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def summarize_deltas(run_id: str, db_path: Optional[Path] = None) -> Dict:
    """
    Generate a summary of changes for a run compared to its parent.

    Returns:
        Dict with counts and highlights
    """
    deltas = get_run_deltas(run_id, db_path)

    summary = {
        'total_changes': len(deltas),
        'by_type': {},
        'by_entity': {'insight': 0, 'pattern': 0},
        'attributions': {},
        'highlights': []
    }

    for delta in deltas:
        # Count by delta type
        dt = delta['delta_type']
        summary['by_type'][dt] = summary['by_type'].get(dt, 0) + 1

        # Count by entity type
        et = delta['entity_type']
        summary['by_entity'][et] = summary['by_entity'].get(et, 0) + 1

        # Track attributions
        attr = delta.get('attributed_to', 'unattributed')
        if attr:
            summary['attributions'][attr] = summary['attributions'].get(attr, 0) + 1

        # Collect highlights (first 5 changes)
        if len(summary['highlights']) < 5:
            summary['highlights'].append(delta['change_summary'])

    return summary


# =============================================================================
# RUN SYNTHESIS
# =============================================================================

def save_synthesis(
    run_id: str,
    synthesis_type: str,
    title: str,
    content: str,
    model_used: Optional[str] = None,
    token_count: Optional[int] = None,
    db_path: Optional[Path] = None
) -> str:
    """Save a synthesis output for a run."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    synthesis_id = str(uuid.uuid4())

    cursor.execute("""
        INSERT INTO run_synthesis
        (id, run_id, synthesis_type, title, content, model_used, token_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        synthesis_id, run_id, synthesis_type, title, content,
        model_used, token_count, datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    return synthesis_id


def get_run_syntheses(run_id: str, db_path: Optional[Path] = None) -> List[Dict]:
    """Get all syntheses for a run."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM run_synthesis
        WHERE run_id = ?
        ORDER BY created_at
    """, (run_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# =============================================================================
# LINK INSIGHTS/PATTERNS TO RUNS
# =============================================================================

def link_insight_to_run(
    insight_id: str,
    run_id: str,
    db_path: Optional[Path] = None
) -> None:
    """Link an insight to an extraction run."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE insights SET run_id = ? WHERE id = ?
    """, (run_id, insight_id))

    conn.commit()
    conn.close()


def link_pattern_to_run(
    pattern_id: str,
    run_id: str,
    db_path: Optional[Path] = None
) -> None:
    """Link a pattern to an extraction run."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE patterns SET run_id = ? WHERE id = ?
    """, (run_id, pattern_id))

    conn.commit()
    conn.close()


def link_all_unlinked_to_run(
    run_id: str,
    db_path: Optional[Path] = None
) -> Dict[str, int]:
    """
    Link all insights and patterns that don't have a run_id to the specified run.

    Useful for retroactively tagging existing extractions as a baseline run.

    Returns:
        Dict with counts of linked insights and patterns
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Link unlinked insights
    cursor.execute("""
        UPDATE insights SET run_id = ? WHERE run_id IS NULL
    """, (run_id,))
    insights_linked = cursor.rowcount

    # Link unlinked patterns
    cursor.execute("""
        UPDATE patterns SET run_id = ? WHERE run_id IS NULL
    """, (run_id,))
    patterns_linked = cursor.rowcount

    # Update run counts
    cursor.execute("""
        UPDATE extraction_runs
        SET insight_count = ?, pattern_count = ?
        WHERE id = ?
    """, (insights_linked, patterns_linked, run_id))

    conn.commit()
    conn.close()

    return {
        'insights_linked': insights_linked,
        'patterns_linked': patterns_linked
    }


# =============================================================================
# COMPARISON UTILITIES
# =============================================================================

def compare_runs(
    run_id: str,
    parent_run_id: str,
    db_path: Optional[Path] = None
) -> Dict:
    """
    Compare two extraction runs and generate comparison data.

    Returns:
        Dict with comparison statistics and differences
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Get run metadata
    cursor.execute("SELECT * FROM extraction_runs WHERE id = ?", (run_id,))
    new_run = dict(cursor.fetchone()) if cursor.fetchone() else None

    cursor.execute("SELECT * FROM extraction_runs WHERE id = ?", (parent_run_id,))
    old_run = dict(cursor.fetchone()) if cursor.fetchone() else None

    # Get insight counts by type for each run
    cursor.execute("""
        SELECT insight_type, COUNT(*) as count, AVG(significance) as avg_sig
        FROM insights WHERE run_id = ?
        GROUP BY insight_type
    """, (run_id,))
    new_insight_types = {row[0]: {'count': row[1], 'avg_sig': row[2]} for row in cursor.fetchall()}

    cursor.execute("""
        SELECT insight_type, COUNT(*) as count, AVG(significance) as avg_sig
        FROM insights WHERE run_id = ?
        GROUP BY insight_type
    """, (parent_run_id,))
    old_insight_types = {row[0]: {'count': row[1], 'avg_sig': row[2]} for row in cursor.fetchall()}

    # Get pattern counts by type
    cursor.execute("""
        SELECT pattern_type, COUNT(*) as count, AVG(strength) as avg_strength
        FROM patterns WHERE run_id = ?
        GROUP BY pattern_type
    """, (run_id,))
    new_pattern_types = {row[0]: {'count': row[1], 'avg_strength': row[2]} for row in cursor.fetchall()}

    cursor.execute("""
        SELECT pattern_type, COUNT(*) as count, AVG(strength) as avg_strength
        FROM patterns WHERE run_id = ?
        GROUP BY pattern_type
    """, (parent_run_id,))
    old_pattern_types = {row[0]: {'count': row[1], 'avg_strength': row[2]} for row in cursor.fetchall()}

    conn.close()

    return {
        'new_run': new_run,
        'old_run': old_run,
        'insight_type_comparison': {
            'new': new_insight_types,
            'old': old_insight_types
        },
        'pattern_type_comparison': {
            'new': new_pattern_types,
            'old': old_pattern_types
        }
    }

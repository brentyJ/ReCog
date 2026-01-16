"""
Run extraction with full context injection (DOB + life timeline).
Compares against baseline run.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Load .env file manually
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from recog_engine.extraction import (
    build_extraction_prompt,
    parse_extraction_response,
    load_user_profile
)
from recog_engine.run_store import (
    complete_run,
    get_life_context_for_date,
)
from recog_engine.core.providers.anthropic_provider import AnthropicProvider
from recog_engine.synth import SynthEngine, ClusterStrategy
from ingestion.parsers.instagram import InstagramHTMLParser


# Configuration
RUN_ID = "9e016a1d-e23a-4fcd-a005-527a5b6e1aa1"
BASELINE_RUN_ID = "dbf20292-dc80-464a-a716-a73a9dc955d6"
DB_PATH = Path("_data/recog.db")
INSTAGRAM_EXPORT_PATH = Path(r"C:\Users\brent\Documents\Mirrowell Data\meta-2026-Jan-10-17-13-19\instagram-brenty_jay-2026-01-09-f6TM2NkJ")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def build_life_context_for_period(start_year: int, end_year: int) -> str:
    """Build life context string for a date range."""
    mid_date = f"{(start_year + end_year) // 2}-06-15"
    contexts = get_life_context_for_date(mid_date, DB_PATH)

    if not contexts:
        return ""

    lines = ["## Life Context During This Period\n"]

    by_type = {}
    for ctx in contexts:
        t = ctx['context_type']
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(ctx)

    type_labels = {
        'career': 'Career',
        'relationship': 'Relationships',
        'residence': 'Living Situation',
        'event': 'Life Events'
    }

    for ctx_type, label in type_labels.items():
        if ctx_type in by_type:
            lines.append(f"**{label}:**")
            for ctx in by_type[ctx_type]:
                loc = f" ({ctx['location']})" if ctx['location'] else ""
                lines.append(f"- {ctx['title']}{loc}")
            lines.append("")

    lines.append("Use this context to understand references in the messages.\n")
    return "\n".join(lines)


def run_extraction():
    """Run full extraction with context injection."""
    print("=" * 70)
    print("EXTRACTION RUN 2: Age + Life Context")
    print("=" * 70)
    print(f"Run ID: {RUN_ID}")
    print(f"Baseline: {BASELINE_RUN_ID}")
    print()

    api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('RECOG_ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: No API key found. Set ANTHROPIC_API_KEY or RECOG_ANTHROPIC_API_KEY")
        return
    provider = AnthropicProvider(api_key=api_key)
    conn = get_db()
    cursor = conn.cursor()

    # Re-parse Instagram data
    print(f"Parsing Instagram export...")
    parser = InstagramHTMLParser()
    parsed = parser.parse(INSTAGRAM_EXPORT_PATH)

    messages = parsed.metadata.get('messages', [])
    if not messages:
        print(f"ERROR: No messages found in export")
        return

    print(f"Loaded {len(messages):,} messages")

    # Build full content string
    content_lines = []
    for msg in messages:
        sender = msg.get('sender', 'Unknown')
        content = msg.get('content', '')
        timestamp = msg.get('timestamp', '')
        if content:
            content_lines.append(f"[{timestamp}] {sender}: {content}")

    full_content = "\n".join(content_lines)
    print(f"Total content: {len(full_content):,} characters")

    # Chunk the content
    chunk_size = 100000
    chunks = []
    for i in range(0, len(full_content), chunk_size):
        chunks.append(full_content[i:i + chunk_size])

    print(f"Split into {len(chunks)} chunks")
    print()

    # Load user profile
    user_profile = load_user_profile()
    print(f"User profile loaded: DOB {user_profile.get('date_of_birth', 'N/A')}")
    print()

    # Run extraction on each chunk
    all_insights = []

    for i, chunk_content in enumerate(chunks):
        # Estimate year range for this chunk
        year_start = 2017 + (i * 9 // len(chunks))
        year_end = min(2026, year_start + 2)

        print(f"[Chunk {i + 1}/{len(chunks)}] ~{year_start}-{year_end} | ", end="", flush=True)

        # Build life context for this period
        life_context = build_life_context_for_period(year_start, year_end)
        content_date = datetime(year_start, 6, 15)

        # Build prompt with context
        prompt = build_extraction_prompt(
            content=chunk_content,
            source_type="instagram_dm",
            source_description=f"Instagram DM messages from @brenty_jay (chunk {i + 1}/{len(chunks)}, approx {year_start}-{year_end})",
            is_chat=True,
            additional_context=life_context,
            user_profile=user_profile,
            content_date=content_date
        )

        # Call LLM
        try:
            response = provider.generate(
                prompt=prompt,
                max_tokens=4000,
                temperature=0.3
            )

            result = parse_extraction_response(response.content)

            if result.success and result.insights:
                print(f"{len(result.insights)} insights")
                all_insights.extend(result.insights)
            else:
                print(f"No insights")

        except Exception as e:
            print(f"ERROR: {e}")

    print()
    print(f"Total insights extracted: {len(all_insights)}")

    # Save insights to database with run_id
    print("\nSaving insights to database...")

    for insight in all_insights:
        cursor.execute("""
            INSERT INTO insights
            (id, summary, themes_json, emotional_tags_json, patterns_json,
             significance, confidence, insight_type, status, excerpt,
             created_at, updated_at, run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """, (
            insight.id,
            insight.summary,
            json.dumps(insight.themes),
            json.dumps(insight.emotional_tags),
            json.dumps(insight.patterns),
            insight.significance,
            insight.confidence,
            insight.insight_type,
            insight.excerpt[:500] if insight.excerpt else None,
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            RUN_ID
        ))

    conn.commit()
    print(f"Saved {len(all_insights)} insights")

    # Run Tier 2 synthesis
    print("\n" + "=" * 70)
    print("TIER 2: Pattern Synthesis")
    print("=" * 70)

    # Initialize synth engine
    synth_engine = SynthEngine(DB_PATH)

    # The synth engine works on insights with status='raw', so update our new insights
    cursor.execute("""
        UPDATE insights SET status = 'raw' WHERE run_id = ?
    """, (RUN_ID,))
    conn.commit()

    # Run synthesis
    synth_result = synth_engine.run_synthesis(
        provider=provider,
        strategy=ClusterStrategy.AUTO,
        min_cluster_size=2,
        max_clusters=20
    )

    print(f"Clusters processed: {synth_result.clusters_processed}")
    print(f"Patterns created: {synth_result.patterns_created}")

    if synth_result.errors:
        print(f"Errors: {synth_result.errors}")

    # Link new patterns to this run
    cursor.execute("""
        UPDATE patterns SET run_id = ? WHERE run_id IS NULL
    """, (RUN_ID,))
    conn.commit()

    # Get final counts
    cursor.execute("SELECT COUNT(*) FROM insights WHERE run_id = ?", (RUN_ID,))
    insight_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patterns WHERE run_id = ?", (RUN_ID,))
    pattern_count = cursor.fetchone()[0]

    # Complete the run
    complete_run(RUN_ID, insight_count, pattern_count, DB_PATH)

    print(f"\n{'=' * 70}")
    print(f"RUN COMPLETE")
    print(f"{'=' * 70}")
    print(f"Insights: {insight_count}")
    print(f"Patterns: {pattern_count}")

    conn.close()

    return {
        'insights': insight_count,
        'patterns': pattern_count
    }


if __name__ == "__main__":
    run_extraction()

"""
Run extraction with full context injection (DOB + life timeline).
Uses actual message timestamps for accurate temporal tracking.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

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
    create_run,
    complete_run,
    get_life_context_for_date,
)
from recog_engine.core.providers.anthropic_provider import AnthropicProvider
from recog_engine.synth import SynthEngine, ClusterStrategy
from ingestion.parsers.instagram import InstagramHTMLParser


# Configuration
DB_PATH = Path("_data/recog.db")
INSTAGRAM_EXPORT_PATH = Path(r"C:\Users\brent\Documents\Mirrowell Data\meta-2026-Jan-10-17-13-19\instagram-brenty_jay-2026-01-09-f6TM2NkJ")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse ISO timestamp string to datetime."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        return None


def chunk_messages_by_time(
    messages: List[Dict],
    chunk_months: int = 6,
    min_messages: int = 20
) -> List[Tuple[List[Dict], datetime, datetime]]:
    """
    Chunk messages by time period, merging small chunks.

    Args:
        messages: List of message dicts with 'timestamp' field
        chunk_months: Target chunk period in months
        min_messages: Minimum messages per chunk (smaller chunks merge with next)

    Returns list of (messages, start_date, end_date) tuples.
    """
    # Filter messages with valid timestamps and sort
    valid_messages = []
    for msg in messages:
        ts = parse_timestamp(msg.get('timestamp'))
        if ts:
            msg['_parsed_ts'] = ts
            valid_messages.append(msg)

    valid_messages.sort(key=lambda m: m['_parsed_ts'])

    if not valid_messages:
        return []

    # Group by time periods
    raw_chunks = []
    current_chunk = []
    chunk_start = valid_messages[0]['_parsed_ts']

    for msg in valid_messages:
        ts = msg['_parsed_ts']

        # Check if we've exceeded the chunk period
        months_diff = (ts.year - chunk_start.year) * 12 + (ts.month - chunk_start.month)

        if months_diff >= chunk_months and current_chunk:
            # Save current chunk
            chunk_end = current_chunk[-1]['_parsed_ts']
            raw_chunks.append((current_chunk, chunk_start, chunk_end))

            # Start new chunk
            current_chunk = [msg]
            chunk_start = ts
        else:
            current_chunk.append(msg)

    # Don't forget the last chunk
    if current_chunk:
        chunk_end = current_chunk[-1]['_parsed_ts']
        raw_chunks.append((current_chunk, chunk_start, chunk_end))

    # Merge small chunks with the next chunk
    if not raw_chunks:
        return []

    merged_chunks = []
    carry_over = []
    carry_start = None

    for i, (chunk_msgs, start, end) in enumerate(raw_chunks):
        # Add any carried over messages
        if carry_over:
            chunk_msgs = carry_over + chunk_msgs
            start = carry_start
            carry_over = []
            carry_start = None

        # If this chunk is too small and not the last, carry it forward
        if len(chunk_msgs) < min_messages and i < len(raw_chunks) - 1:
            carry_over = chunk_msgs
            carry_start = start
        else:
            # Chunk is large enough or is the last chunk
            merged_chunks.append((chunk_msgs, start, end))

    # If we still have carry-over (last chunks were small), merge with previous
    if carry_over and merged_chunks:
        prev_msgs, prev_start, _ = merged_chunks.pop()
        merged_msgs = prev_msgs + carry_over
        merged_end = carry_over[-1]['_parsed_ts']
        merged_chunks.append((merged_msgs, prev_start, merged_end))
    elif carry_over:
        # Edge case: all messages were in carry-over
        merged_chunks.append((carry_over, carry_start, carry_over[-1]['_parsed_ts']))

    return merged_chunks


def format_messages_for_extraction(messages: List[Dict]) -> str:
    """Format messages into text for LLM extraction."""
    lines = []
    for msg in messages:
        sender = msg.get('sender', 'Unknown')
        content = msg.get('content', '')
        timestamp = msg.get('timestamp', '')
        if content:
            # Format: [2019-06-15] sender: content
            date_str = timestamp[:10] if timestamp else ''
            lines.append(f"[{date_str}] {sender}: {content}")
    return "\n".join(lines)


def build_life_context_for_date(date: datetime) -> str:
    """Build life context string for a specific date."""
    date_str = date.strftime('%Y-%m-%d')
    contexts = get_life_context_for_date(date_str, DB_PATH)

    if not contexts:
        return ""

    lines = ["## Life Context At This Time\n"]

    by_type = {}
    for ctx in contexts:
        t = ctx['context_type']
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(ctx)

    type_labels = {
        'career': 'Career',
        'relationship': 'Relationship',
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

    return "\n".join(lines)


def run_extraction(
    run_name: str = None,
    parent_run_id: str = None,
    chunk_months: int = 6,
    min_messages: int = 20
):
    """Run full extraction with timestamp-based chunking and context injection."""

    # Get API key
    api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('RECOG_ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: No API key found. Set ANTHROPIC_API_KEY")
        return

    provider = AnthropicProvider(api_key=api_key)
    conn = get_db()
    cursor = conn.cursor()

    # Create run
    if not run_name:
        run_name = f"Extraction - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    run_id = create_run(
        name=run_name,
        description=f'Timestamp-based extraction with {chunk_months}-month chunks (min {min_messages} msgs) and life context injection.',
        context_config={
            'dob_injection': True,
            'life_context': True,
            'timestamp_chunking': True,
            'chunk_months': chunk_months,
            'min_messages': min_messages
        },
        source_description='Instagram DMs @brenty_jay (28,863 messages, 2017-2026)',
        parent_run_id=parent_run_id,
        db_path=DB_PATH
    )

    print("=" * 70)
    print(f"EXTRACTION: {run_name}")
    print("=" * 70)
    print(f"Run ID: {run_id}")
    print(f"Chunk period: {chunk_months} months")
    print()

    # Parse Instagram data
    print("Parsing Instagram export...")
    parser = InstagramHTMLParser()
    parsed = parser.parse(INSTAGRAM_EXPORT_PATH)

    messages = parsed.metadata.get('messages', [])
    if not messages:
        print("ERROR: No messages found")
        return

    print(f"Loaded {len(messages):,} messages")

    # Chunk by time period
    print(f"Chunking by {chunk_months}-month periods (min {min_messages} messages)...")
    chunks = chunk_messages_by_time(messages, chunk_months=chunk_months, min_messages=min_messages)
    print(f"Created {len(chunks)} chunks")
    print()

    # Show chunk overview
    print("Chunk Overview:")
    print("-" * 60)
    for i, (chunk_msgs, start, end) in enumerate(chunks):
        print(f"  {i+1:2}. {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} | {len(chunk_msgs):,} msgs")
    print()

    # Load user profile
    user_profile = load_user_profile()
    print(f"User profile: DOB {user_profile.get('date_of_birth', 'N/A')}")
    print()

    # Run extraction on each chunk
    all_insights = []

    for i, (chunk_msgs, chunk_start, chunk_end) in enumerate(chunks):
        print(f"[Chunk {i+1}/{len(chunks)}] {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')} | ", end="", flush=True)

        # Format messages for extraction
        content = format_messages_for_extraction(chunk_msgs)

        # Skip empty chunks (shouldn't happen with min_messages merging)
        if len(content) < 100:
            print("skipped (empty)")
            continue

        # Build life context for midpoint of chunk
        midpoint = chunk_start + (chunk_end - chunk_start) / 2
        life_context = build_life_context_for_date(midpoint)

        # Build prompt with context
        prompt = build_extraction_prompt(
            content=content,
            source_type="instagram_dm",
            source_description=f"Instagram DMs from {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')} ({len(chunk_msgs)} messages)",
            is_chat=True,
            additional_context=life_context,
            user_profile=user_profile,
            content_date=midpoint
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

                # Tag insights with ACTUAL date range
                for insight in result.insights:
                    insight.earliest_source_date = chunk_start.strftime('%Y-%m-%d')
                    insight.latest_source_date = chunk_end.strftime('%Y-%m-%d')

                all_insights.extend(result.insights)
            else:
                print("no insights")

        except Exception as e:
            print(f"ERROR: {e}")

    print()
    print(f"Total insights extracted: {len(all_insights)}")

    # Save insights to database
    print("\nSaving insights to database...")

    for insight in all_insights:
        earliest_date = getattr(insight, 'earliest_source_date', None)
        latest_date = getattr(insight, 'latest_source_date', None)

        cursor.execute("""
            INSERT INTO insights
            (id, summary, themes_json, emotional_tags_json, patterns_json,
             significance, confidence, insight_type, status, excerpt,
             earliest_source_date, latest_source_date,
             created_at, updated_at, run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'raw', ?, ?, ?, ?, ?, ?)
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
            earliest_date,
            latest_date,
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            run_id
        ))

    conn.commit()
    print(f"Saved {len(all_insights)} insights with actual timestamps")

    # Run Tier 2 synthesis
    print("\n" + "=" * 70)
    print("TIER 2: Pattern Synthesis")
    print("=" * 70)

    synth_engine = SynthEngine(DB_PATH)

    synth_result = synth_engine.run_synthesis(
        provider=provider,
        strategy=ClusterStrategy.AUTO,
        min_cluster_size=2,
        max_clusters=30
    )

    print(f"Clusters processed: {synth_result.clusters_processed}")
    print(f"Patterns created: {synth_result.patterns_created}")

    # Link patterns to run
    cursor.execute("UPDATE patterns SET run_id = ? WHERE run_id IS NULL", (run_id,))
    conn.commit()

    # Get final counts
    cursor.execute("SELECT COUNT(*) FROM insights WHERE run_id = ?", (run_id,))
    insight_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patterns WHERE run_id = ?", (run_id,))
    pattern_count = cursor.fetchone()[0]

    # Complete the run
    complete_run(run_id, insight_count, pattern_count, DB_PATH)

    print(f"\n{'=' * 70}")
    print("RUN COMPLETE")
    print(f"{'=' * 70}")
    print(f"Run ID: {run_id}")
    print(f"Insights: {insight_count}")
    print(f"Patterns: {pattern_count}")

    conn.close()

    return {
        'run_id': run_id,
        'insights': insight_count,
        'patterns': pattern_count
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Run extraction with timestamp-based chunking')
    parser.add_argument('--name', type=str, help='Run name')
    parser.add_argument('--parent', type=str, help='Parent run ID for comparison')
    parser.add_argument('--months', type=int, default=6, help='Chunk period in months (default: 6)')
    parser.add_argument('--min-messages', type=int, default=20, help='Minimum messages per chunk (default: 20)')

    args = parser.parse_args()

    run_extraction(
        run_name=args.name,
        parent_run_id=args.parent,
        chunk_months=args.months,
        min_messages=args.min_messages
    )

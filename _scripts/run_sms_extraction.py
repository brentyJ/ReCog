"""
Run extraction on SMS export with timestamp-based chunking.

HYBRID MODE SUPPORT
-------------------
This script supports two modes of operation:

1. FULL API MODE (default):
   - Uses Anthropic API for Tier 1-3 extraction
   - Requires API key in .env
   - Costs money per token
   - Command: python run_sms_extraction.py <path>

2. PREPARE-ONLY MODE (--prepare-only):
   - Parses messages and creates time-based chunks
   - Exports chunks to JSON for in-conversation extraction
   - NO API calls, NO cost
   - Use this when doing extraction via Claude Code (Max plan)
   - Command: python run_sms_extraction.py <path> --prepare-only

WHY HYBRID?
-----------
- API mode: Automated, runs unattended, but costs money per token
- Prepare-only + in-conversation: Uses flat-rate Max plan subscription
- For personal use, in-conversation extraction is more cost-effective
- For production/other users, API mode provides full automation

WORKFLOW FOR IN-CONVERSATION EXTRACTION:
1. Run with --prepare-only to generate chunk files
2. Read chunks in Claude Code conversation
3. Claude extracts insights in-conversation (uses Max plan, not API)
4. Save insights to database via conversation
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# Load .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())

sys.path.insert(0, str(Path(__file__).parent))

from recog_engine.extraction import build_extraction_prompt, parse_extraction_response, load_user_profile
from recog_engine.run_store import create_run, complete_run, get_life_context_for_date
from recog_engine.synth import SynthEngine, ClusterStrategy
from ingestion.parsers.messages import MessagesParser


DB_PATH = Path("_data/recog.db")
CHUNKS_DIR = Path("_data/chunks")  # For prepare-only mode exports


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        return None


def chunk_messages_by_time(
    messages: List[Dict],
    chunk_months: int = 6,
    min_messages: int = 15
) -> List[Tuple[List[Dict], datetime, datetime]]:
    """Chunk messages by time period, merging small chunks."""
    valid_messages = []
    for msg in messages:
        ts = parse_timestamp(msg.get('timestamp'))
        if ts:
            msg['_parsed_ts'] = ts
            valid_messages.append(msg)

    valid_messages.sort(key=lambda m: m['_parsed_ts'])

    if not valid_messages:
        return []

    raw_chunks = []
    current_chunk = []
    chunk_start = valid_messages[0]['_parsed_ts']

    for msg in valid_messages:
        ts = msg['_parsed_ts']
        months_diff = (ts.year - chunk_start.year) * 12 + (ts.month - chunk_start.month)

        if months_diff >= chunk_months and current_chunk:
            chunk_end = current_chunk[-1]['_parsed_ts']
            raw_chunks.append((current_chunk, chunk_start, chunk_end))
            current_chunk = [msg]
            chunk_start = ts
        else:
            current_chunk.append(msg)

    if current_chunk:
        chunk_end = current_chunk[-1]['_parsed_ts']
        raw_chunks.append((current_chunk, chunk_start, chunk_end))

    # Merge small chunks
    if not raw_chunks:
        return []

    merged_chunks = []
    carry_over = []
    carry_start = None

    for i, (chunk_msgs, start, end) in enumerate(raw_chunks):
        if carry_over:
            chunk_msgs = carry_over + chunk_msgs
            start = carry_start
            carry_over = []
            carry_start = None

        if len(chunk_msgs) < min_messages and i < len(raw_chunks) - 1:
            carry_over = chunk_msgs
            carry_start = start
        else:
            merged_chunks.append((chunk_msgs, start, end))

    if carry_over and merged_chunks:
        prev_msgs, prev_start, _ = merged_chunks.pop()
        merged_msgs = prev_msgs + carry_over
        merged_end = carry_over[-1]['_parsed_ts']
        merged_chunks.append((merged_msgs, prev_start, merged_end))
    elif carry_over:
        merged_chunks.append((carry_over, carry_start, carry_over[-1]['_parsed_ts']))

    return merged_chunks


def format_messages_for_extraction(messages: List[Dict]) -> str:
    """Format messages for LLM extraction."""
    lines = []
    for msg in messages:
        sender = msg.get('sender', 'Unknown')
        # SMS parser uses 'text', Instagram uses 'content'
        content = msg.get('text') or msg.get('content', '')
        timestamp = msg.get('timestamp', '')
        direction = msg.get('direction', '')
        if content:
            date_str = timestamp[:10] if timestamp else ''
            # Mark who sent (Brent vs Mum)
            if sender == 'Me' or direction == 'sent':
                sender = 'Brent'
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


def prepare_chunks_for_conversation(
    sms_path: Path,
    run_name: str = None,
    chunk_months: int = 6,
    min_messages: int = 15,
    relationship_context: str = None
):
    """
    PREPARE-ONLY MODE: Parse and chunk messages without API calls.

    Exports chunks to JSON files for in-conversation extraction.
    This allows using Claude Code (Max plan) instead of API credits.

    Returns:
        dict with run_id and path to exported chunks
    """
    conn = get_db()
    cursor = conn.cursor()

    # Parse SMS
    print("Parsing SMS export...")
    parser = MessagesParser()
    parsed = parser.parse(sms_path)
    messages = parsed.metadata.get('messages', [])
    participants = parsed.metadata.get('participants', ['Unknown'])

    print(f"Loaded {len(messages)} messages")
    print(f"Participants: {participants}")

    # Create run record (marks as 'prepared' status)
    if not run_name:
        run_name = f"SMS Extraction - {participants[0]} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    run_id = create_run(
        name=run_name,
        description=f'SMS messages with {participants[0]}, {chunk_months}-month chunks (PREPARE-ONLY)',
        context_config={
            'dob_injection': True,
            'life_context': True,
            'timestamp_chunking': True,
            'chunk_months': chunk_months,
            'prepare_only': True  # Flag for in-conversation extraction
        },
        source_description=f'SMS with {participants[0]} ({len(messages)} messages)',
        db_path=DB_PATH
    )

    print("=" * 70)
    print(f"PREPARE-ONLY: {run_name}")
    print("=" * 70)
    print(f"Run ID: {run_id}")
    print()

    # Chunk by time
    chunks = chunk_messages_by_time(messages, chunk_months=chunk_months, min_messages=min_messages)
    print(f"Created {len(chunks)} chunks")
    print()

    # Load user profile
    user_profile = load_user_profile()
    print(f"User profile: DOB {user_profile.get('date_of_birth', 'N/A')}")
    print()

    # Default relationship context if not provided
    if not relationship_context:
        relationship_context = f"""
## Relationship Context
- Conversation with: {participants[0]}
- Messages marked as "Me" are from the user
"""

    # Prepare export directory
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    export_dir = CHUNKS_DIR / run_id
    export_dir.mkdir(exist_ok=True)

    # Export chunks
    print("Chunk Overview:")
    print("-" * 60)

    chunk_manifest = {
        'run_id': run_id,
        'run_name': run_name,
        'participants': participants,
        'total_messages': len(messages),
        'chunk_months': chunk_months,
        'user_profile': user_profile,
        'relationship_context': relationship_context,
        'chunks': []
    }

    for i, (chunk_msgs, start, end) in enumerate(chunks):
        content = format_messages_for_extraction(chunk_msgs)

        if len(content) < 100:
            print(f"  {i+1:2}. {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} | {len(chunk_msgs):,} msgs | SKIPPED (empty)")
            continue

        midpoint = start + (end - start) / 2
        life_context = build_life_context_for_date(midpoint)

        chunk_data = {
            'chunk_index': i + 1,
            'start_date': start.strftime('%Y-%m-%d'),
            'end_date': end.strftime('%Y-%m-%d'),
            'message_count': len(chunk_msgs),
            'content': content,
            'life_context': life_context,
            'additional_context': life_context + relationship_context
        }

        # Save individual chunk file
        chunk_file = export_dir / f"chunk_{i+1:02d}.json"
        chunk_file.write_text(json.dumps(chunk_data, indent=2), encoding='utf-8')

        chunk_manifest['chunks'].append({
            'chunk_index': i + 1,
            'start_date': start.strftime('%Y-%m-%d'),
            'end_date': end.strftime('%Y-%m-%d'),
            'message_count': len(chunk_msgs),
            'file': f"chunk_{i+1:02d}.json",
            'char_count': len(content)
        })

        print(f"  {i+1:2}. {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} | {len(chunk_msgs):,} msgs | {len(content):,} chars")

    # Save manifest
    manifest_file = export_dir / "manifest.json"
    manifest_file.write_text(json.dumps(chunk_manifest, indent=2), encoding='utf-8')

    print()
    print("=" * 70)
    print("PREPARATION COMPLETE")
    print("=" * 70)
    print(f"Run ID: {run_id}")
    print(f"Chunks exported to: {export_dir}")
    print(f"Manifest: {manifest_file}")
    print()
    print("NEXT STEPS FOR IN-CONVERSATION EXTRACTION:")
    print("-" * 60)
    print("1. Read chunk files in Claude Code conversation")
    print("2. Claude extracts insights (uses Max plan, not API)")
    print("3. Save insights to database via conversation")
    print()
    print("To read manifest: Read tool -> " + str(manifest_file.absolute()))

    conn.close()

    return {
        'run_id': run_id,
        'export_dir': str(export_dir),
        'manifest': str(manifest_file),
        'chunk_count': len(chunk_manifest['chunks'])
    }


def run_extraction(
    sms_path: Path,
    run_name: str = None,
    chunk_months: int = 6,
    min_messages: int = 15,
    prepare_only: bool = False,
    relationship_context: str = None
):
    """
    Run extraction on SMS export.

    Args:
        sms_path: Path to SMS XML file
        run_name: Optional name for this run
        chunk_months: Time period for chunking (default: 6 months)
        min_messages: Minimum messages per chunk before merging (default: 15)
        prepare_only: If True, skip API calls and export chunks for in-conversation extraction
        relationship_context: Optional context about the relationship (for prompts)
    """

    # PREPARE-ONLY MODE: Export chunks without API calls
    if prepare_only:
        return prepare_chunks_for_conversation(
            sms_path=sms_path,
            run_name=run_name,
            chunk_months=chunk_months,
            min_messages=min_messages,
            relationship_context=relationship_context
        )

    # FULL API MODE: Requires API key
    # Note: This mode costs money per token. For personal use, consider
    # --prepare-only mode with in-conversation extraction via Claude Code.
    from recog_engine.core.providers.anthropic_provider import AnthropicProvider

    api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('RECOG_ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: No API key found")
        print()
        print("Options:")
        print("  1. Add ANTHROPIC_API_KEY to .env file")
        print("  2. Use --prepare-only for in-conversation extraction (no API cost)")
        return

    provider = AnthropicProvider(api_key=api_key)
    conn = get_db()
    cursor = conn.cursor()

    # Parse SMS
    print("Parsing SMS export...")
    parser = MessagesParser()
    parsed = parser.parse(sms_path)
    messages = parsed.metadata.get('messages', [])
    participants = parsed.metadata.get('participants', ['Unknown'])

    print(f"Loaded {len(messages)} messages")
    print(f"Participants: {participants}")

    # Create run
    if not run_name:
        run_name = f"SMS Extraction - {participants[0]} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    run_id = create_run(
        name=run_name,
        description=f'SMS messages with {participants[0]}, {chunk_months}-month chunks with life context',
        context_config={
            'dob_injection': True,
            'life_context': True,
            'timestamp_chunking': True,
            'chunk_months': chunk_months
        },
        source_description=f'SMS with {participants[0]} ({len(messages)} messages)',
        db_path=DB_PATH
    )

    print("=" * 70)
    print(f"EXTRACTION: {run_name}")
    print("=" * 70)
    print(f"Run ID: {run_id}")
    print()

    # Chunk by time
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

    # Relationship context for Mum
    relationship_context = """
## Relationship Context
- Jennifer Law is Brent's biological mother
- They have had a complicated relationship with periods of estrangement and reconciliation
- Brent calls her "Mum" or "Muzz"
- Messages marked as "Me" are from Brent
- Key themes to watch for: boundaries, family dynamics, forgiveness, emotional patterns
"""

    # Run extraction
    all_insights = []

    for i, (chunk_msgs, chunk_start, chunk_end) in enumerate(chunks):
        print(f"[Chunk {i+1}/{len(chunks)}] {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')} | ", end="", flush=True)

        content = format_messages_for_extraction(chunk_msgs)

        if len(content) < 100:
            print("skipped (empty)")
            continue

        midpoint = chunk_start + (chunk_end - chunk_start) / 2
        life_context = build_life_context_for_date(midpoint)

        additional_context = life_context + relationship_context

        prompt = build_extraction_prompt(
            content=content,
            source_type="sms",
            source_description=f"SMS with Mum from {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')} ({len(chunk_msgs)} messages)",
            is_chat=True,
            additional_context=additional_context,
            user_profile=user_profile,
            content_date=midpoint
        )

        try:
            response = provider.generate(
                prompt=prompt,
                max_tokens=4000,
                temperature=0.3
            )

            result = parse_extraction_response(response.content)

            if result.success and result.insights:
                print(f"{len(result.insights)} insights")

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

    # Save insights
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
    print(f"Saved {len(all_insights)} insights")

    # Run synthesis
    print("\n" + "=" * 70)
    print("TIER 2: Pattern Synthesis")
    print("=" * 70)

    synth_engine = SynthEngine(DB_PATH)
    synth_result = synth_engine.run_synthesis(
        provider=provider,
        strategy=ClusterStrategy.AUTO,
        min_cluster_size=2,
        max_clusters=20
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

    parser = argparse.ArgumentParser(
        description='Run SMS extraction with optional hybrid mode',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full API mode (costs money per token)
  python run_sms_extraction.py messages.xml

  # Prepare-only mode (no API cost, for in-conversation extraction)
  python run_sms_extraction.py messages.xml --prepare-only

  # Custom chunk period
  python run_sms_extraction.py messages.xml --months 3 --prepare-only

Hybrid Workflow:
  1. Run with --prepare-only to export chunks
  2. Read chunks in Claude Code conversation
  3. Claude extracts insights using Max plan (no API cost)
  4. Save insights to database via conversation
"""
    )
    parser.add_argument('path', type=str, help='Path to SMS XML file')
    parser.add_argument('--name', type=str, help='Run name')
    parser.add_argument('--months', type=int, default=6, help='Chunk period in months')
    parser.add_argument('--min-messages', type=int, default=15, help='Minimum messages per chunk')
    parser.add_argument('--prepare-only', action='store_true',
                        help='Skip API calls, export chunks for in-conversation extraction')
    parser.add_argument('--relationship-context', type=str,
                        help='Context about the relationship (optional, for prompts)')

    args = parser.parse_args()

    run_extraction(
        sms_path=Path(args.path),
        run_name=args.name,
        chunk_months=args.months,
        min_messages=args.min_messages,
        prepare_only=args.prepare_only,
        relationship_context=args.relationship_context
    )

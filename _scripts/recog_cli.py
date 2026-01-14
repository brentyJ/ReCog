"""
ReCog CLI - Command line interface for testing ReCog engine

Copyright (c) 2025 Brent Lefebure / EhkoLabs

Usage:
    python recog_cli.py detect <file>              - Detect file format
    python recog_cli.py ingest <file>              - Ingest a file
    python recog_cli.py formats                    - Show supported formats
    python recog_cli.py tier0 <file>               - Run Tier 0 signal extraction
    python recog_cli.py tier0 --text "..."         - Run Tier 0 on text
    python recog_cli.py prompt <file>              - Generate extraction prompt
    python recog_cli.py db init [path]             - Initialize database
    python recog_cli.py db check [path]            - Check database status
    python recog_cli.py preflight create <folder>  - Create preflight session
    python recog_cli.py preflight scan <id>        - Scan preflight session
    python recog_cli.py preflight status <id>      - Get preflight status
    python recog_cli.py cost-report                - View LLM cost summary (last 7 days)
    python recog_cli.py cost-report --last-30-days - View costs for last 30 days
    python recog_cli.py cost-report --daily        - Show day-by-day breakdown
"""

import sys
import json
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ingestion import (
    detect_file,
    ingest_file,
    get_format_info,
    get_supported_extensions,
)

from recog_engine import (
    # Tier 0
    Tier0Processor,
    preprocess_text,
    summarise_for_prompt,
    # Extraction
    build_extraction_prompt,
    prepare_chat_content,
    # Entity & Preflight
    EntityRegistry,
    PreflightManager,
)

from db import init_database, check_database, get_schema_path
from recog_engine.cost_tracker import CostTracker


# =============================================================================
# FILE COMMANDS
# =============================================================================

def cmd_detect(path: str):
    """Detect file format and show guidance."""
    result = detect_file(path)
    
    print(f"\nFile: {path}")
    print("-" * 50)
    print(f"Supported: {'Yes' if result.supported else 'No'}")
    print(f"Type: {result.file_type}")
    
    if result.parser_name:
        print(f"Parser: {result.parser_name}")
    
    if result.is_container:
        print(f"Container: Yes")
        if result.contained_files:
            print(f"Contains: {len(result.contained_files)} files")
            for f in result.contained_files[:5]:
                print(f"  - {f}")
            if len(result.contained_files) > 5:
                print(f"  ... and {len(result.contained_files) - 5} more")
    
    if result.needs_action:
        print(f"\n⚠️  {result.action_message}")
        if result.suggestions:
            print("\nSuggestions:")
            for s in result.suggestions:
                print(f"  → {s}")


def cmd_ingest(path: str):
    """Ingest a file and show results."""
    try:
        documents = ingest_file(path)
        
        print(f"\nIngested: {path}")
        print("-" * 50)
        print(f"Documents created: {len(documents)}")
        
        for doc in documents:
            print(f"\n  ID: {doc.id}")
            print(f"  Source: {doc.source_type}")
            print(f"  Content length: {len(doc.content)} chars")
            
            # Preview
            preview = doc.content[:200].replace('\n', ' ')
            if len(doc.content) > 200:
                preview += "..."
            print(f"  Preview: {preview}")
            
            if doc.metadata:
                print(f"  Metadata: {json.dumps(doc.metadata, indent=4, default=str)}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        
        # Show detection info
        result = detect_file(path)
        if result.suggestions:
            print("\nSuggestions:")
            for s in result.suggestions:
                print(f"  → {s}")


def cmd_formats():
    """Show supported formats."""
    info = get_format_info()
    
    print("\nSupported Formats")
    print("=" * 50)
    
    print("\nDirect Support:")
    for ext, (name, _) in info["supported"].items():
        print(f"  {ext:12} {name}")
    
    print("\nContainer Formats (extract first):")
    for ext, name in info["containers"].items():
        print(f"  {ext:12} {name}")
    
    print("\nUnsupported (with conversion help):")
    for ext in info["unsupported_with_help"]:
        print(f"  {ext}")
    
    print(f"\nAll extensions: {', '.join(info['extensions'])}")


# =============================================================================
# TIER 0 COMMANDS
# =============================================================================

def cmd_tier0(source: str, is_text: bool = False):
    """Run Tier 0 signal extraction."""
    if is_text:
        text = source
        source_name = "<text input>"
    else:
        path = Path(source)
        if not path.exists():
            print(f"❌ File not found: {source}")
            return
        text = path.read_text(encoding="utf-8")
        source_name = path.name
    
    print(f"\nTier 0 Signal Extraction")
    print(f"Source: {source_name}")
    print("=" * 60)
    
    # Run Tier 0
    result = preprocess_text(text)
    
    # Basic info
    print(f"\n📊 Basic Stats")
    print(f"  Word count: {result['word_count']}")
    print(f"  Char count: {result['char_count']}")
    
    # Emotions
    emotions = result.get("emotion_signals", {})
    if emotions.get("keywords_found"):
        print(f"\n😊 Emotion Signals")
        print(f"  Keywords: {', '.join(emotions['keywords_found'][:10])}")
        if emotions.get("categories"):
            print(f"  Categories: {', '.join(emotions['categories'])}")
        print(f"  Density: {emotions.get('keyword_density', 0):.3f}")
    
    # Intensity
    intensity = result.get("intensity_markers", {})
    if any([intensity.get("exclamations"), intensity.get("all_caps_words"), 
            intensity.get("intensifiers"), intensity.get("hedges")]):
        print(f"\n⚡ Intensity Markers")
        if intensity.get("exclamations"):
            print(f"  Exclamations: {intensity['exclamations']}")
        if intensity.get("all_caps_words"):
            print(f"  ALL CAPS words: {intensity['all_caps_words']}")
        if intensity.get("intensifiers"):
            print(f"  Intensifiers: {', '.join(intensity['intensifiers'][:5])}")
        if intensity.get("hedges"):
            print(f"  Hedges: {', '.join(intensity['hedges'][:5])}")
        if intensity.get("absolutes"):
            print(f"  Absolutes: {', '.join(intensity['absolutes'][:5])}")
    
    # Questions
    questions = result.get("question_analysis", {})
    if questions.get("question_count"):
        print(f"\n❓ Questions")
        print(f"  Count: {questions['question_count']}")
        if questions.get("self_inquiry"):
            print(f"  Self-inquiry: {questions['self_inquiry']}")
        if questions.get("rhetorical_likely"):
            print(f"  Rhetorical: {questions['rhetorical_likely']}")
    
    # Temporal
    temporal = result.get("temporal_references", {})
    has_temporal = any(temporal.get(k) for k in ["past", "present", "future", "habitual"])
    if has_temporal:
        print(f"\n⏰ Temporal References")
        for period in ["past", "present", "future", "habitual"]:
            refs = temporal.get(period, [])
            if refs:
                print(f"  {period.title()}: {', '.join(refs[:3])}")
    
    # Entities
    entities = result.get("entities", {})
    has_entities = any(entities.get(k) for k in ["people", "phone_numbers", "email_addresses"])
    if has_entities:
        print(f"\n👤 Entities")
        if entities.get("people"):
            print(f"  People: {', '.join(entities['people'][:5])}")
        if entities.get("phone_numbers"):
            phones = [p.get("normalised", p.get("raw", "?")) for p in entities["phone_numbers"][:3]]
            print(f"  Phones: {', '.join(phones)}")
        if entities.get("email_addresses"):
            emails = [e.get("normalised", e.get("raw", "?")) for e in entities["email_addresses"][:3]]
            print(f"  Emails: {', '.join(emails)}")
    
    # Structure
    structure = result.get("structural", {})
    print(f"\n📝 Structure")
    print(f"  Paragraphs: {structure.get('paragraph_count', 0)}")
    print(f"  Sentences: {structure.get('sentence_count', 0)}")
    print(f"  Avg sentence length: {structure.get('avg_sentence_length', 0)} words")
    if structure.get("speaker_changes"):
        print(f"  Speaker changes: {structure['speaker_changes']}")
    
    # Flags
    flags = result.get("flags", {})
    active_flags = [k.replace("_", " ").title() for k, v in flags.items() if v]
    if active_flags:
        print(f"\n🚩 Flags: {', '.join(active_flags)}")
    
    # Prompt summary
    print(f"\n📋 Prompt Summary (for LLM)")
    print("-" * 40)
    print(summarise_for_prompt(result))


def cmd_tier0_json(source: str, is_text: bool = False):
    """Run Tier 0 and output raw JSON."""
    if is_text:
        text = source
    else:
        path = Path(source)
        if not path.exists():
            print(f"Error: File not found: {source}", file=sys.stderr)
            sys.exit(1)
        text = path.read_text(encoding="utf-8")
    
    result = preprocess_text(text)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_prompt(path: str):
    """Generate extraction prompt for a file (no LLM call)."""
    file_path = Path(path)
    if not file_path.exists():
        print(f"❌ File not found: {path}")
        return
    
    # Ingest
    try:
        documents = ingest_file(path)
    except Exception as e:
        print(f"❌ Ingest error: {e}")
        return
    
    if not documents:
        print("❌ No documents extracted")
        return
    
    doc = documents[0]
    content = doc.content
    
    # Run Tier 0
    pre_annotation = preprocess_text(content)
    
    # Detect if chat format
    is_chat = "<USER_MESSAGE>" in content or doc.source_type in ("chatgpt_export", "chat")
    
    # Build prompt
    prompt = build_extraction_prompt(
        content=content,
        source_type=doc.source_type,
        source_description=file_path.name,
        pre_annotation=pre_annotation,
        is_chat=is_chat,
    )
    
    print("\n" + "=" * 60)
    print("EXTRACTION PROMPT (ready for LLM)")
    print("=" * 60)
    print(prompt)
    print("\n" + "=" * 60)
    print(f"Prompt length: {len(prompt)} chars, ~{len(prompt.split())} words")


# =============================================================================
# DATABASE COMMANDS
# =============================================================================

def cmd_db(args: list):
    """Database management commands."""
    if not args:
        print("Usage: recog_cli.py db <command>")
        print("Commands: init, check, schema")
        return
    
    subcmd = args[0].lower()
    
    if subcmd == "init":
        path = Path(args[1]) if len(args) > 1 and not args[1].startswith("--") else None
        force = "--force" in args
        init_database(path, force=force)
    
    elif subcmd == "check":
        path = Path(args[1]) if len(args) > 1 else Path.cwd() / "recog.db"
        result = check_database(path)
        
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        
        print(f"\nDatabase: {path}")
        print(f"Tables: {result['total_tables']}")
        print(f"Total rows: {result['total_rows']}")
        print()
        
        for table, count in sorted(result["tables"].items()):
            print(f"  {table}: {count}")
    
    elif subcmd == "schema":
        print(get_schema_path())
    
    else:
        print(f"Unknown db command: {subcmd}")


# =============================================================================
# PREFLIGHT COMMANDS
# =============================================================================

def cmd_preflight(args: list):
    """Preflight session commands."""
    if not args:
        print("Usage: recog_cli.py preflight <command>")
        print("Commands: create, scan, status, filter")
        return
    
    subcmd = args[0].lower()
    
    # Get database path
    db_path = Path.cwd() / "recog.db"
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run: recog_cli.py db init")
        return
    
    manager = PreflightManager(db_path)
    
    if subcmd == "create":
        if len(args) < 2:
            print("Usage: recog_cli.py preflight create <folder>")
            return
        
        folder = Path(args[1])
        if not folder.exists():
            print(f"❌ Folder not found: {folder}")
            return
        
        # Get files
        files = [str(f) for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")]
        
        if not files:
            print(f"❌ No files found in: {folder}")
            return
        
        # Create session
        session_id = manager.create_session(
            session_type="batch",
            source_files=files,
        )
        
        print(f"\n✅ Created preflight session: {session_id}")
        print(f"   Files: {len(files)}")
        
        # Add items
        for file_path in files:
            try:
                path = Path(file_path)
                content = path.read_text(encoding="utf-8")
                manager.add_item(
                    session_id=session_id,
                    source_type="file",
                    content=content,
                    source_id=str(path),
                    title=path.name,
                )
                print(f"   Added: {path.name}")
            except Exception as e:
                print(f"   ⚠️  Skipped {path.name}: {e}")
        
        print(f"\nNext: recog_cli.py preflight scan {session_id}")
    
    elif subcmd == "scan":
        if len(args) < 2:
            print("Usage: recog_cli.py preflight scan <session_id>")
            return
        
        session_id = int(args[1])
        result = manager.scan_session(session_id)
        
        print(f"\n📊 Preflight Scan Results")
        print("=" * 50)
        print(f"Session: {session_id}")
        print(f"Items: {result['item_count']}")
        print(f"Words: {result['total_words']:,}")
        print(f"Entities: {result['total_entities']}")
        print(f"  Phones: {result['entities']['phones']}")
        print(f"  Emails: {result['entities']['emails']}")
        print(f"  People: {result['entities']['people']}")
        print()
        print(f"Unknown entities: {result['unknown_entities']}")
        print(f"Estimated tokens: {result['estimated_tokens']:,}")
        print(f"Estimated cost: ${result['estimated_cost_dollars']:.3f}")
        
        if result['questions']:
            print(f"\n❓ Entity Questions ({len(result['questions'])})")
            for q in result['questions'][:5]:
                print(f"  - {q['question']}")
    
    elif subcmd == "status":
        if len(args) < 2:
            print("Usage: recog_cli.py preflight status <session_id>")
            return
        
        session_id = int(args[1])
        summary = manager.get_summary(session_id)
        
        if "error" in summary:
            print(f"❌ {summary['error']}")
            return
        
        print(f"\n📋 Preflight Session {session_id}")
        print("=" * 50)
        print(f"Type: {summary['session_type']}")
        print(f"Status: {summary['status']}")
        print(f"Items: {summary['items']['included']}/{summary['items']['total']} included")
        print(f"Words: {summary['total_words']:,}")
        print(f"Entities: {summary['total_entities']} ({summary['unknown_entities']} unknown)")
        print(f"Est. cost: ${summary['estimated_cost_dollars']:.3f}")
        print(f"Created: {summary['created_at']}")
    
    else:
        print(f"Unknown preflight command: {subcmd}")


# =============================================================================
# COST TRACKING COMMANDS
# =============================================================================

def cmd_cost_report(args: list):
    """Show LLM cost report."""
    # Parse arguments
    days = 7  # Default
    show_daily = "--daily" in args
    show_recent = "--recent" in args

    for arg in args:
        if arg.startswith("--last-"):
            # Parse --last-N-days format
            try:
                days = int(arg.replace("--last-", "").replace("-days", ""))
            except ValueError:
                print(f"Invalid format: {arg}")
                print("Use --last-N-days (e.g., --last-30-days)")
                return

    # Get database path
    db_path = Path.cwd() / "_data" / "recog.db"
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Run: recog_cli.py db init")
        return

    tracker = CostTracker(db_path)

    # Header
    print(f"\n{'='*60}")
    print(f" LLM Cost Report - Last {days} Days")
    print(f"{'='*60}")

    # Get summary
    summary = tracker.get_summary(days=days)

    if summary.total_requests == 0:
        print("\nNo LLM requests recorded in this period.")
        print("Costs are tracked automatically when using the router.")
        return

    # Overview
    print(f"\n--- Overview {'-'*37}")
    print(f"  Total requests:     {summary.total_requests:,}")
    print(f"  Successful:         {summary.successful_requests:,}")
    print(f"  Failed:             {summary.failed_requests:,}")
    print(f"  Total tokens:       {summary.total_tokens:,}")
    print(f"    Input tokens:     {summary.total_input_tokens:,}")
    print(f"    Output tokens:    {summary.total_output_tokens:,}")
    print(f"  Total cost:         ${summary.total_cost:.4f}")

    # By provider
    if summary.by_provider:
        print(f"\n--- By Provider {'-'*34}")
        for provider, data in sorted(summary.by_provider.items(), key=lambda x: x[1]['cost'], reverse=True):
            print(f"  {provider:15} {data['requests']:5} reqs | {data['tokens']:10,} tokens | ${data['cost']:.4f}")

    # By feature
    if summary.by_feature:
        print(f"\n--- By Feature {'-'*35}")
        for feature, data in sorted(summary.by_feature.items(), key=lambda x: x[1]['cost'], reverse=True):
            print(f"  {feature:15} {data['requests']:5} reqs | {data['tokens']:10,} tokens | ${data['cost']:.4f}")

    # Daily breakdown
    if show_daily:
        print(f"\n--- Daily Breakdown {'-'*30}")
        daily = tracker.get_daily_breakdown(days=days)
        if daily:
            print(f"  {'Date':<12} {'Requests':>10} {'Tokens':>12} {'Cost':>10} {'Failed':>8}")
            print(f"  {'-'*12} {'-'*10} {'-'*12} {'-'*10} {'-'*8}")
            for row in daily:
                print(f"  {row['day']:<12} {row['requests']:>10,} {row['tokens']:>12,} ${row['cost']:>9.4f} {row['failed']:>8}")
        else:
            print("  No daily data available")

    # Recent requests
    if show_recent:
        print(f"\n--- Recent Requests {'-'*30}")
        recent = tracker.get_recent_requests(limit=10)
        for entry in recent:
            status = "OK" if entry.success else "FAIL"
            print(f"  {entry.created_at.strftime('%Y-%m-%d %H:%M')} | {entry.feature:12} | {entry.provider:10} | {entry.total_tokens:6} tok | ${entry.total_cost:.4f} | {status}")

    # Footer
    print(f"\n{'='*60}")
    print(f"Period: {summary.period_start.strftime('%Y-%m-%d')} to {summary.period_end.strftime('%Y-%m-%d')}")
    print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    
    # detect
    if cmd == "detect" and len(sys.argv) >= 3:
        cmd_detect(sys.argv[2])
    
    # ingest
    elif cmd == "ingest" and len(sys.argv) >= 3:
        cmd_ingest(sys.argv[2])
    
    # formats
    elif cmd == "formats":
        cmd_formats()
    
    # tier0
    elif cmd == "tier0":
        if len(sys.argv) < 3:
            print("Usage: recog_cli.py tier0 <file> [--json]")
            print("       recog_cli.py tier0 --text \"your text here\" [--json]")
            sys.exit(1)
        
        is_json = "--json" in sys.argv
        is_text = "--text" in sys.argv
        
        if is_text:
            try:
                idx = sys.argv.index("--text")
                text = sys.argv[idx + 1]
            except (ValueError, IndexError):
                print("Usage: recog_cli.py tier0 --text \"your text here\"")
                sys.exit(1)
            
            if is_json:
                cmd_tier0_json(text, is_text=True)
            else:
                cmd_tier0(text, is_text=True)
        else:
            file_arg = [a for a in sys.argv[2:] if not a.startswith("--")][0]
            if is_json:
                cmd_tier0_json(file_arg)
            else:
                cmd_tier0(file_arg)
    
    # prompt
    elif cmd == "prompt" and len(sys.argv) >= 3:
        cmd_prompt(sys.argv[2])
    
    # db
    elif cmd == "db":
        cmd_db(sys.argv[2:])
    
    # preflight
    elif cmd == "preflight":
        cmd_preflight(sys.argv[2:])

    # cost-report
    elif cmd == "cost-report":
        cmd_cost_report(sys.argv[2:])

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

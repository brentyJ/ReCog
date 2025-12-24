"""
ReCog Server - Flask API for ReCog Engine

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

REST API for:
- File upload and preflight workflow
- Insight extraction and browsing
- Entity management
- Processing queue
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ReCog imports
from recog_engine import (
    # Tier 0
    preprocess_text,
    summarise_for_prompt,
    # Extraction
    build_extraction_prompt,
    parse_extraction_response,
    prepare_chat_content,
    ExtractedInsight,
    # Entity & Preflight
    EntityRegistry,
    PreflightManager,
    # Insight Store
    InsightStore,
    # Synth Engine
    SynthEngine,
    ClusterStrategy,
)
from recog_engine.core.providers import (
    create_provider,
    get_available_providers,
    load_env_file,
)
from ingestion import detect_file, ingest_file
from db import init_database, check_database

# =============================================================================
# CONFIGURATION
# =============================================================================

# Load .env file before Config class
_scripts_dir = Path(__file__).parent
load_env_file(_scripts_dir / ".env")


class Config:
    """Server configuration."""
    DATA_DIR = Path(os.environ.get("RECOG_DATA_DIR", "./_data"))
    UPLOAD_DIR = DATA_DIR / "uploads"
    DB_PATH = DATA_DIR / "recog.db"
    
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {
        'txt', 'md', 'json', 'pdf', 'csv',
        'eml', 'msg', 'mbox', 'xml', 'xlsx',
    }
    
    # LLM config - uses provider factory
    # Available providers determined by which API keys are configured
    AVAILABLE_PROVIDERS = get_available_providers()
    LLM_CONFIGURED = len(AVAILABLE_PROVIDERS) > 0


# =============================================================================
# APP SETUP
# =============================================================================

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure directories exist
Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
Config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database if needed
if not Config.DB_PATH.exists():
    init_database(Config.DB_PATH)
    logger.info(f"Initialized database: {Config.DB_PATH}")

# Initialize managers
entity_registry = EntityRegistry(Config.DB_PATH)
preflight_manager = PreflightManager(Config.DB_PATH, entity_registry)
insight_store = InsightStore(Config.DB_PATH)
synth_engine = SynthEngine(Config.DB_PATH, insight_store, entity_registry)


# =============================================================================
# UTILITIES
# =============================================================================

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def api_response(data=None, error=None, status=200):
    """Standard API response wrapper."""
    response = {
        "success": error is None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if data is not None:
        response["data"] = data
    if error is not None:
        response["error"] = error
    return jsonify(response), status


def require_json(f):
    """Decorator to require JSON body."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not request.is_json:
            return api_response(error="JSON body required", status=400)
        return f(*args, **kwargs)
    return decorated


# =============================================================================
# HEALTH & INFO
# =============================================================================

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    db_status = check_database(Config.DB_PATH)
    return api_response({
        "status": "healthy",
        "database": {
            "path": str(Config.DB_PATH),
            "tables": db_status.get("total_tables", 0),
            "rows": db_status.get("total_rows", 0),
        },
        "llm_configured": Config.LLM_CONFIGURED,
        "available_providers": Config.AVAILABLE_PROVIDERS,
    })


@app.route("/api/info", methods=["GET"])
def info():
    """Server info endpoint."""
    return api_response({
        "name": "ReCog Server",
        "version": "0.4.0",
        "endpoints": [
            "/api/health",
            "/api/upload",
            "/api/detect",
            "/api/tier0",
            "/api/extract",
            "/api/preflight/<id>",
            "/api/preflight/<id>/items",
            "/api/preflight/<id>/filter",
            "/api/preflight/<id>/confirm",
            "/api/entities",
            "/api/entities/unknown",
            "/api/entities/<id>",
            "/api/entities/stats",
            "/api/insights",
            "/api/insights/<id>",
            "/api/insights/stats",
            "/api/queue",
            "/api/queue/stats",
            "/api/queue/<id>",
            "/api/queue/<id>/retry",
            "/api/queue/clear",
            "/api/synth/clusters",
            "/api/synth/run",
            "/api/synth/patterns",
            "/api/synth/patterns/<id>",
            "/api/synth/stats",
        ],
    })


# =============================================================================
# FILE OPERATIONS
# =============================================================================

@app.route("/api/detect", methods=["POST"])
def detect_format():
    """Detect file format from upload."""
    if "file" not in request.files:
        return api_response(error="No file provided", status=400)
    
    file = request.files["file"]
    if file.filename == "":
        return api_response(error="No file selected", status=400)
    
    # Save temporarily
    filename = secure_filename(file.filename)
    temp_path = Config.UPLOAD_DIR / f"temp_{uuid4().hex}_{filename}"
    file.save(str(temp_path))
    
    try:
        result = detect_file(str(temp_path))
        return api_response({
            "filename": filename,
            "supported": result.supported,
            "file_type": result.file_type,
            "parser": result.parser_name,
            "is_container": result.is_container,
            "contained_files": result.contained_files[:10] if result.contained_files else [],
            "needs_action": result.needs_action,
            "action_message": result.action_message,
            "suggestions": result.suggestions,
        })
    finally:
        temp_path.unlink(missing_ok=True)


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """
    Upload file and create preflight session.
    
    Returns preflight session ID for review workflow.
    """
    if "file" not in request.files:
        return api_response(error="No file provided", status=400)
    
    file = request.files["file"]
    if file.filename == "":
        return api_response(error="No file selected", status=400)
    
    # Save file
    filename = secure_filename(file.filename)
    file_id = uuid4().hex[:8]
    saved_path = Config.UPLOAD_DIR / f"{file_id}_{filename}"
    file.save(str(saved_path))
    
    logger.info(f"Uploaded: {saved_path}")
    
    # Detect format
    detection = detect_file(str(saved_path))
    
    if not detection.supported:
        return api_response({
            "uploaded": True,
            "file_id": file_id,
            "filename": filename,
            "supported": False,
            "message": detection.action_message,
            "suggestions": detection.suggestions,
        })
    
    # Create preflight session
    try:
        session_id = preflight_manager.create_session(
            session_type="single_file",
            source_files=[str(saved_path)],
        )
        
        # Ingest and add to preflight
        documents = ingest_file(str(saved_path))
        
        for doc in documents:
            preflight_manager.add_item(
                session_id=session_id,
                source_type=doc.source_type,
                content=doc.content,
                source_id=doc.id,
                title=doc.metadata.get("title", filename) if doc.metadata else filename,
            )
        
        # Scan session
        scan_result = preflight_manager.scan_session(session_id)
        
        return api_response({
            "uploaded": True,
            "file_id": file_id,
            "filename": filename,
            "supported": True,
            "preflight_session_id": session_id,
            "items": scan_result["item_count"],
            "words": scan_result["total_words"],
            "entities": scan_result["total_entities"],
            "unknown_entities": scan_result["unknown_entities"],
            "estimated_cost_cents": scan_result["estimated_cost_cents"],
            "questions": scan_result["questions"][:5],
        })
    
    except Exception as e:
        logger.error(f"Upload processing error: {e}")
        return api_response(error=str(e), status=500)


# =============================================================================
# TIER 0 (Direct Processing)
# =============================================================================

@app.route("/api/tier0", methods=["POST"])
@require_json
def run_tier0():
    """
    Run Tier 0 signal extraction on provided text.
    
    Body: {"text": "..."}
    """
    data = request.get_json()
    text = data.get("text", "")
    
    if not text:
        return api_response(error="No text provided", status=400)
    
    result = preprocess_text(text)
    summary = summarise_for_prompt(result)
    
    return api_response({
        "tier0": result,
        "summary": summary,
    })


# =============================================================================
# PREFLIGHT WORKFLOW
# =============================================================================

@app.route("/api/preflight/<int:session_id>", methods=["GET"])
def get_preflight(session_id: int):
    """Get preflight session summary."""
    summary = preflight_manager.get_summary(session_id)
    
    if "error" in summary:
        return api_response(error=summary["error"], status=404)
    
    return api_response(summary)


@app.route("/api/preflight/<int:session_id>/items", methods=["GET"])
def get_preflight_items(session_id: int):
    """Get all items in preflight session."""
    items = preflight_manager.get_items(session_id)
    
    # Simplify for API response
    simplified = []
    for item in items:
        simplified.append({
            "id": item["id"],
            "source_type": item["source_type"],
            "title": item["title"],
            "word_count": item["word_count"],
            "included": item["included"],
            "exclusion_reason": item["exclusion_reason"],
            "processed": item["processed"],
            "flags": item.get("pre_annotation", {}).get("flags", {}),
            "entities_count": sum(
                len(item.get("entities_found", {}).get(k, []))
                for k in ["phone_numbers", "email_addresses", "people"]
            ),
        })
    
    return api_response({
        "session_id": session_id,
        "items": simplified,
        "total": len(items),
        "included": sum(1 for i in items if i["included"]),
    })


@app.route("/api/preflight/<int:session_id>/filter", methods=["POST"])
@require_json
def filter_preflight(session_id: int):
    """
    Apply filters to preflight session.
    
    Body: {
        "min_words": 100,
        "min_messages": 5,
        "date_after": "2024-01-01",
        "date_before": "2024-12-31",
        "keywords": ["important", "urgent"]
    }
    """
    data = request.get_json()
    
    result = preflight_manager.apply_filters(
        session_id,
        min_words=data.get("min_words"),
        min_messages=data.get("min_messages"),
        date_after=data.get("date_after"),
        date_before=data.get("date_before"),
        keywords=data.get("keywords"),
    )
    
    return api_response({
        "session_id": session_id,
        "filtered": True,
        "items_remaining": result["item_count"],
        "words_remaining": result["total_words"],
        "estimated_cost_cents": result["estimated_cost_cents"],
    })


@app.route("/api/preflight/<int:session_id>/exclude/<int:item_id>", methods=["POST"])
def exclude_item(session_id: int, item_id: int):
    """Exclude an item from preflight session."""
    reason = request.json.get("reason", "manual") if request.is_json else "manual"
    
    success = preflight_manager.exclude_item(item_id, reason)
    
    if success:
        return api_response({"excluded": True, "item_id": item_id})
    return api_response(error="Item not found", status=404)


@app.route("/api/preflight/<int:session_id>/include/<int:item_id>", methods=["POST"])
def include_item(session_id: int, item_id: int):
    """Re-include an excluded item."""
    success = preflight_manager.include_item(item_id)
    
    if success:
        return api_response({"included": True, "item_id": item_id})
    return api_response(error="Item not found", status=404)


@app.route("/api/preflight/<int:session_id>/confirm", methods=["POST"])
def confirm_preflight(session_id: int):
    """
    Confirm preflight session and queue for processing.
    
    This marks items for LLM extraction (requires API key).
    """
    result = preflight_manager.confirm_session(session_id)
    
    if not result.get("success"):
        return api_response(error=result.get("error"), status=400)
    
    return api_response({
        "confirmed": True,
        "session_id": session_id,
        "items_queued": result["items_to_process"],
        "estimated_cost_cents": result["estimated_cost_cents"],
        "message": "Items queued for extraction. Use /api/extract to process.",
    })


# =============================================================================
# ENTITY MANAGEMENT
# =============================================================================

@app.route("/api/entities", methods=["GET"])
def list_entities():
    """List all entities."""
    entity_type = request.args.get("type")
    confirmed = request.args.get("confirmed")
    limit = int(request.args.get("limit", 100))
    
    entities = entity_registry.list_entities(
        entity_type=entity_type,
        confirmed_only=(confirmed == "true"),
        unconfirmed_only=(confirmed == "false"),
        limit=limit,
    )
    
    return api_response({
        "entities": entities,
        "count": len(entities),
    })


@app.route("/api/entities/unknown", methods=["GET"])
def get_unknown_entities():
    """Get entities needing user identification."""
    limit = int(request.args.get("limit", 50))
    entities = entity_registry.get_unknown_entities(limit)
    
    return api_response({
        "entities": entities,
        "count": len(entities),
    })


@app.route("/api/entities/<int:entity_id>", methods=["GET"])
def get_entity(entity_id: int):
    """Get entity by ID."""
    entity = entity_registry.get_entity_by_id(entity_id)
    
    if not entity:
        return api_response(error="Entity not found", status=404)
    
    return api_response(entity)


@app.route("/api/entities/<int:entity_id>", methods=["PATCH"])
@require_json
def update_entity(entity_id: int):
    """
    Update entity with user context.
    
    Body: {
        "display_name": "Mum",
        "relationship": "mother",
        "notes": "...",
        "anonymise_in_prompts": true,
        "placeholder_name": "Person A",
        "confirmed": true
    }
    """
    data = request.get_json()
    
    success = entity_registry.update_entity(
        entity_id,
        display_name=data.get("display_name"),
        relationship=data.get("relationship"),
        notes=data.get("notes"),
        anonymise_in_prompts=data.get("anonymise_in_prompts"),
        placeholder_name=data.get("placeholder_name"),
        confirmed=data.get("confirmed"),
    )
    
    if success:
        entity = entity_registry.get_entity_by_id(entity_id)
        return api_response(entity)
    
    return api_response(error="Update failed", status=400)


@app.route("/api/entities/stats", methods=["GET"])
def entity_stats():
    """Get entity registry statistics."""
    stats = entity_registry.get_stats()
    return api_response(stats)


# =============================================================================
# EXTRACTION
# =============================================================================

@app.route("/api/extract", methods=["POST"])
@require_json
def extract_insights():
    """
    Extract insights from text using LLM.
    
    Body: {
        "text": "...",
        "source_type": "document",
        "source_id": "optional-id",
        "is_chat": false,
        "provider": "openai|anthropic" (optional)
    }
    
    Requires LLM API key(s) configured via environment variables.
    """
    if not Config.LLM_CONFIGURED:
        return api_response(
            error="LLM not configured. Set RECOG_OPENAI_API_KEY or RECOG_ANTHROPIC_API_KEY.",
            status=503
        )
    
    data = request.get_json()
    text = data.get("text", "")
    source_type = data.get("source_type", "unknown")
    source_id = data.get("source_id", str(uuid4()))
    is_chat = data.get("is_chat", False)
    provider_name = data.get("provider")  # Optional override
    
    if not text:
        return api_response(error="No text provided", status=400)
    
    # Run Tier 0
    pre_annotation = preprocess_text(text)
    
    # Build prompt
    prompt = build_extraction_prompt(
        content=text,
        source_type=source_type,
        source_description=source_id,
        pre_annotation=pre_annotation,
        is_chat=is_chat,
    )
    
    # Call LLM via provider
    try:
        provider = create_provider(provider_name)
        
        response = provider.generate(
            prompt=prompt,
            system_prompt="You are an insight extraction system. Return valid JSON only.",
            temperature=0.3,
            max_tokens=2000,
        )
        
        if not response.success:
            return api_response(error=response.error, status=500)
        
        # Parse response
        result = parse_extraction_response(response.content, source_type, source_id)
        
        # Save insights to database
        save_results = []
        if result.success and result.insights:
            save_to_db = data.get("save", True)  # Default to saving
            if save_to_db:
                batch_result = insight_store.save_insights_batch(
                    result.insights,
                    check_similarity=data.get("check_similarity", True),
                )
                save_results = batch_result.get("results", [])
                logger.info(f"Saved {batch_result['created']} new, merged {batch_result['merged']} insights")
        
        return api_response({
            "success": result.success,
            "insights": [i.to_dict() for i in result.insights],
            "saved": save_results,
            "content_quality": result.content_quality,
            "notes": result.notes,
            "provider": provider.name,
            "model": response.model,
            "tokens_used": response.usage.get("total_tokens", 0) if response.usage else 0,
            "tier0": {
                "flags": pre_annotation.get("flags", {}),
                "emotion_categories": pre_annotation.get("emotion_signals", {}).get("categories", []),
            },
        })
    
    except ValueError as e:
        # Provider configuration error
        return api_response(error=str(e), status=503)
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return api_response(error=str(e), status=500)


# =============================================================================
# INSIGHTS
# =============================================================================

@app.route("/api/insights", methods=["GET"])
def list_insights():
    """
    List extracted insights from database.
    
    Query params:
        - status: raw, refined, surfaced, rejected
        - min_significance: 0.0-1.0
        - insight_type: observation, pattern, relationship, etc.
        - limit: max results (default 100)
        - offset: pagination offset
        - order_by: significance, confidence, created_at, updated_at
        - order_dir: ASC or DESC
    """
    status = request.args.get("status")
    min_sig = request.args.get("min_significance")
    insight_type = request.args.get("insight_type")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    order_by = request.args.get("order_by", "significance")
    order_dir = request.args.get("order_dir", "DESC")
    
    result = insight_store.list_insights(
        status=status,
        min_significance=float(min_sig) if min_sig else None,
        insight_type=insight_type,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_dir=order_dir,
    )
    
    return api_response(result)


@app.route("/api/insights/<insight_id>", methods=["GET"])
def get_insight(insight_id: str):
    """Get a single insight by ID."""
    insight = insight_store.get_insight(insight_id)
    
    if not insight:
        return api_response(error="Insight not found", status=404)
    
    # Include sources and history
    insight["sources"] = insight_store.get_sources(insight_id)
    insight["history"] = insight_store.get_history(insight_id)
    
    return api_response(insight)


@app.route("/api/insights/<insight_id>", methods=["PATCH"])
@require_json
def update_insight_status(insight_id: str):
    """
    Update an insight's status or significance.
    
    Body: {
        "status": "surfaced",
        "significance": 0.8,
        "themes": ["updated", "themes"],
        "patterns": ["new-pattern"]
    }
    """
    data = request.get_json()
    
    success = insight_store.update_insight(
        insight_id,
        status=data.get("status"),
        significance=data.get("significance"),
        themes=data.get("themes"),
        patterns=data.get("patterns"),
    )
    
    if success:
        insight = insight_store.get_insight(insight_id)
        return api_response(insight)
    
    return api_response(error="Insight not found or update failed", status=404)


@app.route("/api/insights/<insight_id>", methods=["DELETE"])
def delete_insight(insight_id: str):
    """
    Soft-delete an insight (sets status to 'rejected').
    
    Query param ?hard=true for permanent deletion.
    """
    hard_delete = request.args.get("hard", "false").lower() == "true"
    
    success = insight_store.delete_insight(insight_id, soft=not hard_delete)
    
    if success:
        return api_response({"deleted": True, "insight_id": insight_id})
    
    return api_response(error="Insight not found", status=404)


@app.route("/api/insights/stats", methods=["GET"])
def insight_stats():
    """Get insight statistics."""
    stats = insight_store.get_stats()
    return api_response(stats)


# =============================================================================
# PROCESSING QUEUE
# =============================================================================

def _get_db_connection():
    """Get raw database connection for queue operations."""
    import sqlite3
    conn = sqlite3.connect(str(Config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/api/queue", methods=["GET"])
def list_queue():
    """
    List processing queue items.
    
    Query params:
        - status: pending, processing, complete, failed (default: all)
        - limit: max results (default 50)
        - offset: pagination offset
    """
    status = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    
    conn = _get_db_connection()
    try:
        # Build query
        if status:
            query = "SELECT * FROM processing_queue WHERE status = ? ORDER BY priority DESC, queued_at DESC LIMIT ? OFFSET ?"
            params = (status, limit, offset)
            count_query = "SELECT COUNT(*) FROM processing_queue WHERE status = ?"
            count_params = (status,)
        else:
            query = "SELECT * FROM processing_queue ORDER BY priority DESC, queued_at DESC LIMIT ? OFFSET ?"
            params = (limit, offset)
            count_query = "SELECT COUNT(*) FROM processing_queue"
            count_params = ()
        
        rows = conn.execute(query, params).fetchall()
        total = conn.execute(count_query, count_params).fetchone()[0]
        
        items = []
        for row in rows:
            items.append({
                "id": row["id"],
                "operation_type": row["operation_type"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "status": row["status"],
                "priority": row["priority"],
                "word_count": row["word_count"],
                "pass_count": row["pass_count"],
                "notes": row["notes"],
                "queued_at": row["queued_at"],
                "last_processed_at": row["last_processed_at"],
            })
        
        return api_response({
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    finally:
        conn.close()


@app.route("/api/queue/stats", methods=["GET"])
def queue_stats():
    """Get queue statistics."""
    conn = _get_db_connection()
    try:
        # Count by status
        status_counts = {}
        for row in conn.execute(
            "SELECT status, COUNT(*) as count FROM processing_queue GROUP BY status"
        ).fetchall():
            status_counts[row["status"]] = row["count"]
        
        # Count by operation type
        op_counts = {}
        for row in conn.execute(
            "SELECT operation_type, COUNT(*) as count FROM processing_queue WHERE status = 'pending' GROUP BY operation_type"
        ).fetchall():
            op_counts[row["operation_type"]] = row["count"]
        
        # Total pending word count
        pending_words = conn.execute(
            "SELECT SUM(word_count) FROM processing_queue WHERE status = 'pending'"
        ).fetchone()[0] or 0
        
        return api_response({
            "by_status": status_counts,
            "pending_by_type": op_counts,
            "pending_word_count": pending_words,
            "total": sum(status_counts.values()),
        })
    finally:
        conn.close()


@app.route("/api/queue/<int:job_id>", methods=["GET"])
def get_queue_item(job_id: int):
    """Get a single queue item by ID."""
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM processing_queue WHERE id = ?",
            (job_id,)
        ).fetchone()
        
        if not row:
            return api_response(error="Job not found", status=404)
        
        return api_response({
            "id": row["id"],
            "operation_type": row["operation_type"],
            "source_type": row["source_type"],
            "source_id": row["source_id"],
            "status": row["status"],
            "priority": row["priority"],
            "word_count": row["word_count"],
            "pass_count": row["pass_count"],
            "notes": row["notes"],
            "queued_at": row["queued_at"],
            "last_processed_at": row["last_processed_at"],
            "pre_annotation": json.loads(row["pre_annotation_json"]) if row["pre_annotation_json"] else None,
        })
    finally:
        conn.close()


@app.route("/api/queue/<int:job_id>/retry", methods=["POST"])
def retry_queue_item(job_id: int):
    """Retry a failed queue item."""
    conn = _get_db_connection()
    try:
        # Check current status
        row = conn.execute(
            "SELECT status FROM processing_queue WHERE id = ?",
            (job_id,)
        ).fetchone()
        
        if not row:
            return api_response(error="Job not found", status=404)
        
        if row["status"] not in ("failed", "complete"):
            return api_response(
                error=f"Cannot retry job with status '{row['status']}'",
                status=400
            )
        
        # Reset to pending
        now = datetime.utcnow().isoformat() + "Z"
        conn.execute(
            "UPDATE processing_queue SET status = 'pending', notes = 'Manual retry', last_processed_at = ? WHERE id = ?",
            (now, job_id)
        )
        conn.commit()
        
        return api_response({"retried": True, "job_id": job_id})
    finally:
        conn.close()


@app.route("/api/queue/<int:job_id>", methods=["DELETE"])
def delete_queue_item(job_id: int):
    """Delete a queue item."""
    conn = _get_db_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM processing_queue WHERE id = ?",
            (job_id,)
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            return api_response({"deleted": True, "job_id": job_id})
        
        return api_response(error="Job not found", status=404)
    finally:
        conn.close()


@app.route("/api/queue/clear", methods=["POST"])
def clear_queue():
    """
    Clear queue items by status.
    
    Body: {"status": "failed"} or {"status": "complete"}
    """
    if not request.is_json:
        return api_response(error="JSON body required", status=400)
    
    data = request.get_json()
    status = data.get("status")
    
    if status not in ("failed", "complete"):
        return api_response(
            error="Can only clear 'failed' or 'complete' items",
            status=400
        )
    
    conn = _get_db_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM processing_queue WHERE status = ?",
            (status,)
        )
        conn.commit()
        
        return api_response({
            "cleared": True,
            "status": status,
            "count": cursor.rowcount,
        })
    finally:
        conn.close()


# =============================================================================
# SYNTH ENGINE (Pattern Synthesis)
# =============================================================================

@app.route("/api/synth/clusters", methods=["POST"])
def create_clusters():
    """
    Create insight clusters for synthesis.
    
    Body: {
        "strategy": "auto|thematic|temporal|entity",
        "min_cluster_size": 3,
        "insight_status": "raw"
    }
    """
    data = request.get_json() if request.is_json else {}
    
    strategy_str = data.get("strategy", "auto")
    try:
        strategy = ClusterStrategy(strategy_str)
    except ValueError:
        strategy = ClusterStrategy.AUTO
    
    min_size = int(data.get("min_cluster_size", 3))
    insight_status = data.get("insight_status", "raw")
    
    clusters = synth_engine.create_clusters(
        strategy=strategy,
        min_cluster_size=min_size,
        insight_status=insight_status,
    )
    
    return api_response({
        "clusters_created": len(clusters),
        "clusters": [c.to_dict() for c in clusters],
    })


@app.route("/api/synth/clusters", methods=["GET"])
def list_clusters():
    """List pending clusters awaiting synthesis."""
    limit = int(request.args.get("limit", 20))
    
    clusters = synth_engine.get_pending_clusters(limit=limit)
    
    return api_response({
        "clusters": [c.to_dict() for c in clusters],
        "count": len(clusters),
    })


@app.route("/api/synth/run", methods=["POST"])
def run_synthesis():
    """
    Run a full synthesis cycle.
    
    Creates clusters from raw insights, synthesizes patterns via LLM.
    
    Body: {
        "strategy": "auto|thematic|temporal|entity",
        "min_cluster_size": 3,
        "max_clusters": 10,
        "provider": "openai|anthropic" (optional)
    }
    
    Requires LLM API key configured.
    """
    if not Config.LLM_CONFIGURED:
        return api_response(
            error="LLM not configured. Set API keys in environment.",
            status=503
        )
    
    data = request.get_json() if request.is_json else {}
    
    strategy_str = data.get("strategy", "auto")
    try:
        strategy = ClusterStrategy(strategy_str)
    except ValueError:
        strategy = ClusterStrategy.AUTO
    
    min_size = int(data.get("min_cluster_size", 3))
    max_clusters = int(data.get("max_clusters", 10))
    provider_name = data.get("provider")
    
    try:
        provider = create_provider(provider_name)
        
        result = synth_engine.run_synthesis(
            provider=provider,
            strategy=strategy,
            min_cluster_size=min_size,
            max_clusters=max_clusters,
        )
        
        return api_response({
            "success": result.success,
            "patterns_created": result.patterns_created,
            "clusters_processed": result.clusters_processed,
            "patterns": [p.to_dict() for p in result.patterns],
            "errors": result.errors,
        })
        
    except Exception as e:
        logger.exception("Synthesis failed")
        return api_response(error=str(e), status=500)


@app.route("/api/synth/patterns", methods=["GET"])
def list_patterns():
    """
    List synthesized patterns.
    
    Query params:
        - pattern_type: behavioral, emotional, temporal, relational, etc.
        - status: detected, confirmed, rejected
        - min_strength: 0.0-1.0
        - limit: max results (default 100)
        - offset: pagination offset
    """
    pattern_type = request.args.get("pattern_type")
    status = request.args.get("status")
    min_strength = request.args.get("min_strength")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    
    result = synth_engine.list_patterns(
        pattern_type=pattern_type,
        status=status,
        min_strength=float(min_strength) if min_strength else None,
        limit=limit,
        offset=offset,
    )
    
    return api_response(result)


@app.route("/api/synth/patterns/<pattern_id>", methods=["GET"])
def get_pattern(pattern_id: str):
    """Get a single pattern by ID."""
    pattern = synth_engine.get_pattern(pattern_id)
    
    if not pattern:
        return api_response(error="Pattern not found", status=404)
    
    return api_response(pattern)


@app.route("/api/synth/patterns/<pattern_id>", methods=["PATCH"])
@require_json
def update_pattern(pattern_id: str):
    """
    Update a pattern's status.
    
    Body: {"status": "confirmed|rejected"}
    """
    data = request.get_json()
    new_status = data.get("status")
    
    if new_status not in ("detected", "confirmed", "rejected", "superseded"):
        return api_response(error="Invalid status", status=400)
    
    conn = _get_db_connection()
    try:
        now = datetime.utcnow().isoformat() + "Z"
        cursor = conn.execute(
            "UPDATE patterns SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, pattern_id)
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            pattern = synth_engine.get_pattern(pattern_id)
            return api_response(pattern)
        
        return api_response(error="Pattern not found", status=404)
    finally:
        conn.close()


@app.route("/api/synth/stats", methods=["GET"])
def synth_stats():
    """Get Synth Engine statistics."""
    stats = synth_engine.get_stats()
    return api_response(stats)


# =============================================================================
# STATIC FILES (for future frontend)
# =============================================================================

@app.route("/", methods=["GET"])
def index():
    """Serve index page or API info."""
    static_index = Path(__file__).parent / "static" / "index.html"
    if static_index.exists():
        return send_from_directory("static", "index.html")
    
    return api_response({
        "message": "ReCog Server API",
        "docs": "/api/info",
        "health": "/api/health",
    })


# =============================================================================
# MAIN
# =============================================================================

def create_app():
    """Application factory for WSGI servers."""
    return app


if __name__ == "__main__":
    port = int(os.environ.get("RECOG_PORT", 5100))
    debug = os.environ.get("RECOG_DEBUG", "false").lower() == "true"
    
    print(f"\n🔮 ReCog Server starting on http://localhost:{port}")
    print(f"   Database: {Config.DB_PATH}")
    print(f"   LLM providers: {', '.join(Config.AVAILABLE_PROVIDERS) or 'none'}")
    print()
    
    app.run(host="0.0.0.0", port=port, debug=debug)

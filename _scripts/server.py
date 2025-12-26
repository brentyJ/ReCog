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
    # Entity Graph
    EntityGraph,
    RelationshipType,
    # Insight Store
    InsightStore,
    # Synth Engine
    SynthEngine,
    ClusterStrategy,
    # Critique Engine
    CritiqueEngine,
    StrictnessLevel,
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
entity_graph = EntityGraph(Config.DB_PATH)  # Extended entity management
preflight_manager = PreflightManager(Config.DB_PATH, entity_registry)
insight_store = InsightStore(Config.DB_PATH)
synth_engine = SynthEngine(Config.DB_PATH, insight_store, entity_graph)
critique_engine = CritiqueEngine(Config.DB_PATH, StrictnessLevel.STANDARD)

# Load entity blacklist into tier0 module at startup
try:
    from recog_engine.tier0 import load_blacklist_from_db
    _blacklist = load_blacklist_from_db(Config.DB_PATH)
    logger.info(f"Loaded entity blacklist: {len(_blacklist)} entries")
except Exception as e:
    logger.warning(f"Could not load entity blacklist: {e}")


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
        "version": "0.6.0",
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
            "/api/entities/<id>/relationships",
            "/api/entities/<id>/network",
            "/api/entities/<id>/timeline",
            "/api/entities/<id>/sentiment",
            "/api/entities/graph/stats",
            "/api/relationships",
            "/api/relationships/<id>",
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
            "/api/critique/insight",
            "/api/critique/pattern",
            "/api/critique/refine",
            "/api/critique/<id>",
            "/api/critique/for/<type>/<id>",
            "/api/critique",
            "/api/critique/stats",
            "/api/critique/strictness",
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


@app.route("/api/entities/<int:entity_id>", methods=["DELETE"])
def delete_entity(entity_id: int):
    """
    Permanently delete an entity from the registry.
    
    Use this for complete removal. For false positives that should be
    blocked in future, use /api/entities/<id>/reject instead.
    """
    conn = _get_db_connection()
    try:
        # Check entity exists
        row = conn.execute(
            "SELECT raw_value FROM entity_registry WHERE id = ?",
            (entity_id,)
        ).fetchone()
        
        if not row:
            return api_response(error="Entity not found", status=404)
        
        # Delete the entity
        conn.execute("DELETE FROM entity_registry WHERE id = ?", (entity_id,))
        conn.commit()
        
        return api_response({
            "deleted": True,
            "entity_id": entity_id,
            "value": row["raw_value"],
        })
    finally:
        conn.close()


@app.route("/api/entities/<int:entity_id>/unconfirm", methods=["POST"])
def unconfirm_entity(entity_id: int):
    """
    Move an entity back to 'needs identification' status.
    
    Clears confirmed flag and user-provided metadata, keeping the
    entity in the registry for re-identification.
    """
    conn = _get_db_connection()
    try:
        # Check entity exists
        row = conn.execute(
            "SELECT raw_value, confirmed FROM entity_registry WHERE id = ?",
            (entity_id,)
        ).fetchone()
        
        if not row:
            return api_response(error="Entity not found", status=404)
        
        now = datetime.utcnow().isoformat() + "Z"
        
        # Reset to unconfirmed state
        conn.execute("""
            UPDATE entity_registry 
            SET confirmed = 0,
                display_name = NULL,
                relationship = NULL,
                notes = NULL,
                anonymise_in_prompts = 0,
                placeholder_name = NULL,
                updated_at = ?
            WHERE id = ?
        """, (now, entity_id))
        conn.commit()
        
        return api_response({
            "unconfirmed": True,
            "entity_id": entity_id,
            "value": row["raw_value"],
        })
    finally:
        conn.close()


@app.route("/api/entities/stats", methods=["GET"])
def entity_stats():
    """Get entity registry statistics."""
    stats = entity_registry.get_stats()
    return api_response(stats)


# =============================================================================
# ENTITY BLACKLIST (False Positive Management)
# =============================================================================

@app.route("/api/entities/<int:entity_id>/reject", methods=["POST"])
@require_json
def reject_entity(entity_id: int):
    """
    Reject an entity as a false positive (e.g., "Not a Person").
    
    Adds to blacklist and optionally deletes from entity registry.
    
    Body: {
        "reason": "not_a_person",  # or "common_word", "false_positive"
        "delete_entity": true      # Remove from registry (default true)
    }
    """
    data = request.get_json()
    reason = data.get("reason", "not_a_person")
    delete_entity = data.get("delete_entity", True)
    
    # Get entity details first
    entity = entity_registry.get_entity_by_id(entity_id)
    if not entity:
        return api_response(error="Entity not found", status=404)
    
    now = datetime.utcnow().isoformat() + "Z"
    
    conn = _get_db_connection()
    try:
        # Add to blacklist
        try:
            conn.execute("""
                INSERT INTO entity_blacklist (
                    entity_type, raw_value, normalised_value,
                    rejection_reason, rejected_by, source_context,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'user', ?, ?, ?)
            """, (
                entity.get("entity_type"),
                entity.get("raw_value"),
                entity.get("normalised_value") or entity.get("raw_value", "").lower(),
                reason,
                None,  # Could store source context
                now, now
            ))
        except Exception:
            # Already blacklisted - increment count
            conn.execute("""
                UPDATE entity_blacklist 
                SET rejection_count = rejection_count + 1, updated_at = ?
                WHERE entity_type = ? AND normalised_value = ?
            """, (now, entity.get("entity_type"), entity.get("normalised_value")))
        
        # Optionally delete from registry
        if delete_entity:
            conn.execute("DELETE FROM entity_registry WHERE id = ?", (entity_id,))
        
        conn.commit()
        
        # Update runtime blacklist
        from recog_engine.tier0 import add_to_blacklist
        add_to_blacklist(entity.get("normalised_value") or entity.get("raw_value"))
        
        return api_response({
            "rejected": True,
            "entity_id": entity_id,
            "value": entity.get("raw_value"),
            "reason": reason,
            "deleted": delete_entity,
        })
    finally:
        conn.close()


@app.route("/api/entities/blacklist", methods=["GET"])
def list_blacklist():
    """
    List blacklisted entity values.
    
    Query params:
        - type: Filter by entity type (person, phone, email)
        - limit: Max results (default 100)
    """
    entity_type = request.args.get("type", "person")
    limit = int(request.args.get("limit", 100))
    
    conn = _get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT id, entity_type, raw_value, normalised_value,
                   rejection_reason, rejected_by, rejection_count,
                   created_at, updated_at
            FROM entity_blacklist
            WHERE entity_type = ?
            ORDER BY rejection_count DESC, created_at DESC
            LIMIT ?
        """, (entity_type, limit))
        
        items = []
        for row in cursor.fetchall():
            items.append({
                "id": row["id"],
                "entity_type": row["entity_type"],
                "raw_value": row["raw_value"],
                "normalised_value": row["normalised_value"],
                "rejection_reason": row["rejection_reason"],
                "rejected_by": row["rejected_by"],
                "rejection_count": row["rejection_count"],
                "created_at": row["created_at"],
            })
        
        return api_response({
            "blacklist": items,
            "count": len(items),
        })
    finally:
        conn.close()


@app.route("/api/entities/blacklist/<int:blacklist_id>", methods=["DELETE"])
def remove_from_blacklist(blacklist_id: int):
    """Remove an entry from the blacklist (un-reject)."""
    conn = _get_db_connection()
    try:
        row = conn.execute(
            "SELECT normalised_value FROM entity_blacklist WHERE id = ?",
            (blacklist_id,)
        ).fetchone()
        
        if not row:
            return api_response(error="Blacklist entry not found", status=404)
        
        conn.execute("DELETE FROM entity_blacklist WHERE id = ?", (blacklist_id,))
        conn.commit()
        
        return api_response({
            "removed": True,
            "blacklist_id": blacklist_id,
        })
    finally:
        conn.close()


@app.route("/api/entities/blacklist/reload", methods=["POST"])
def reload_blacklist():
    """Reload blacklist from database into runtime memory."""
    from recog_engine.tier0 import load_blacklist_from_db
    
    blacklist = load_blacklist_from_db(Config.DB_PATH)
    
    return api_response({
        "reloaded": True,
        "count": len(blacklist),
    })


# =============================================================================
# ENTITY GRAPH (Relationships & Network)
# =============================================================================

@app.route("/api/entities/<int:entity_id>/relationships", methods=["GET"])
def get_entity_relationships(entity_id: int):
    """
    Get relationships for an entity.
    
    Query params:
        - type: Filter by relationship type
        - direction: 'outgoing', 'incoming', or 'both' (default)
        - min_strength: Minimum relationship strength (0-1)
    """
    rel_type = request.args.get("type")
    direction = request.args.get("direction", "both")
    min_strength = float(request.args.get("min_strength", 0.0))
    
    relationships = entity_graph.get_relationships(
        entity_id=entity_id,
        relationship_type=rel_type,
        direction=direction,
        min_strength=min_strength,
    )
    
    return api_response({
        "entity_id": entity_id,
        "relationships": [r.to_dict() for r in relationships],
        "count": len(relationships),
    })


@app.route("/api/entities/<int:entity_id>/relationships", methods=["POST"])
@require_json
def add_entity_relationship(entity_id: int):
    """
    Add a relationship from this entity to another.
    
    Body: {
        "target_entity_id": 123,
        "relationship_type": "manages",
        "strength": 0.8,
        "bidirectional": false,
        "context": "How we know this"
    }
    """
    data = request.get_json()
    
    target_id = data.get("target_entity_id")
    if not target_id:
        return api_response(error="target_entity_id required", status=400)
    
    rel_type = data.get("relationship_type", "associated_with")
    
    rel_id, is_new = entity_graph.add_relationship(
        source_entity_id=entity_id,
        target_entity_id=target_id,
        relationship_type=rel_type,
        strength=float(data.get("strength", 0.5)),
        bidirectional=bool(data.get("bidirectional", False)),
        context=data.get("context"),
    )
    
    return api_response({
        "relationship_id": rel_id,
        "is_new": is_new,
        "source_entity_id": entity_id,
        "target_entity_id": target_id,
        "relationship_type": rel_type,
    })


@app.route("/api/entities/<int:entity_id>/network", methods=["GET"])
def get_entity_network(entity_id: int):
    """
    Get the relationship network around an entity.
    
    Query params:
        - depth: How many hops to traverse (default 1)
        - min_strength: Minimum relationship strength (default 0.2)
    """
    depth = int(request.args.get("depth", 1))
    min_strength = float(request.args.get("min_strength", 0.2))
    
    network = entity_graph.get_network(
        entity_id=entity_id,
        depth=depth,
        min_strength=min_strength,
    )
    
    if not network:
        return api_response(error="Entity not found", status=404)
    
    return api_response({
        "center": network.center_entity,
        "relationships": network.relationships,
        "connected_entities": network.connected_entities,
        "co_occurrences": network.co_occurrences,
        "sentiment_summary": network.sentiment_summary,
    })


@app.route("/api/entities/<int:entity_id>/timeline", methods=["GET"])
def get_entity_timeline(entity_id: int):
    """
    Get a timeline of entity appearances and events.
    
    Query params:
        - limit: Max events to return (default 100)
    """
    limit = int(request.args.get("limit", 100))
    
    events = entity_graph.get_timeline(entity_id, limit=limit)
    
    return api_response({
        "entity_id": entity_id,
        "events": events,
        "count": len(events),
    })


@app.route("/api/entities/<int:entity_id>/sentiment", methods=["GET"])
def get_entity_sentiment(entity_id: int):
    """
    Get sentiment summary and history for an entity.
    
    Query params:
        - limit: Max history records (default 50)
    """
    limit = int(request.args.get("limit", 50))
    
    summary = entity_graph.get_sentiment_summary(entity_id)
    history = entity_graph.get_sentiment_history(entity_id, limit=limit)
    
    return api_response({
        "entity_id": entity_id,
        "summary": summary,
        "history": [{
            "id": s.id,
            "score": s.sentiment_score,
            "label": s.sentiment_label,
            "source_type": s.source_type,
            "source_id": s.source_id,
            "excerpt": s.excerpt,
            "recorded_at": s.recorded_at,
        } for s in history],
    })


@app.route("/api/entities/<int:entity_id>/sentiment", methods=["POST"])
@require_json
def record_entity_sentiment(entity_id: int):
    """
    Record sentiment for an entity.
    
    Body: {
        "score": 0.5,  # -1 to 1
        "source_type": "insight",
        "source_id": "abc123",
        "excerpt": "Relevant text..."
    }
    """
    data = request.get_json()
    
    score = data.get("score")
    if score is None:
        return api_response(error="score required", status=400)
    
    sentiment_id = entity_graph.record_sentiment(
        entity_id=entity_id,
        sentiment_score=float(score),
        source_type=data.get("source_type", "manual"),
        source_id=data.get("source_id", str(uuid4())),
        excerpt=data.get("excerpt"),
    )
    
    return api_response({
        "sentiment_id": sentiment_id,
        "entity_id": entity_id,
    })


@app.route("/api/entities/<int:entity_a_id>/path/<int:entity_b_id>", methods=["GET"])
def find_entity_path(entity_a_id: int, entity_b_id: int):
    """
    Find the shortest relationship path between two entities.
    
    Query params:
        - max_depth: Maximum hops to search (default 4)
    """
    max_depth = int(request.args.get("max_depth", 4))
    
    path = entity_graph.find_path(
        source_entity_id=entity_a_id,
        target_entity_id=entity_b_id,
        max_depth=max_depth,
    )
    
    if path is None:
        return api_response({
            "path_exists": False,
            "source_id": entity_a_id,
            "target_id": entity_b_id,
        })
    
    # Fetch entity details for path
    path_entities = [entity_graph.get_entity_by_id(eid) for eid in path]
    
    return api_response({
        "path_exists": True,
        "path_ids": path,
        "path_entities": path_entities,
        "hops": len(path) - 1,
    })


@app.route("/api/entities/graph/stats", methods=["GET"])
def entity_graph_stats():
    """Get entity graph statistics including relationships and sentiment."""
    stats = entity_graph.get_graph_stats()
    return api_response(stats)


@app.route("/api/relationships", methods=["GET"])
def list_relationships():
    """
    List all relationships.
    
    Query params:
        - type: Filter by relationship type
        - min_strength: Minimum strength
        - limit: Max results (default 100)
    """
    rel_type = request.args.get("type")
    min_strength = float(request.args.get("min_strength", 0.0))
    limit = int(request.args.get("limit", 100))
    
    conn = _get_db_connection()
    try:
        conditions = ["strength >= ?"]
        params = [min_strength]
        
        if rel_type:
            conditions.append("relationship_type = ?")
            params.append(rel_type)
        
        params.append(limit)
        
        cursor = conn.execute(f"""
            SELECT id, source_entity_id, target_entity_id, relationship_type,
                   strength, bidirectional, context, occurrence_count,
                   first_seen_at, last_seen_at
            FROM entity_relationships
            WHERE {' AND '.join(conditions)}
            ORDER BY strength DESC, occurrence_count DESC
            LIMIT ?
        """, params)
        
        relationships = []
        for row in cursor.fetchall():
            relationships.append({
                "id": row["id"],
                "source_entity_id": row["source_entity_id"],
                "target_entity_id": row["target_entity_id"],
                "relationship_type": row["relationship_type"],
                "strength": row["strength"],
                "bidirectional": bool(row["bidirectional"]),
                "context": row["context"],
                "occurrence_count": row["occurrence_count"],
                "first_seen_at": row["first_seen_at"],
                "last_seen_at": row["last_seen_at"],
            })
        
        return api_response({
            "relationships": relationships,
            "count": len(relationships),
        })
    finally:
        conn.close()


@app.route("/api/relationships/<int:relationship_id>", methods=["DELETE"])
def delete_relationship(relationship_id: int):
    """Delete a relationship."""
    success = entity_graph.remove_relationship(relationship_id)
    
    if success:
        return api_response({"deleted": True, "relationship_id": relationship_id})
    
    return api_response(error="Relationship not found", status=404)


@app.route("/api/relationships/types", methods=["GET"])
def list_relationship_types():
    """List available relationship types."""
    types = [t.value for t in RelationshipType]
    return api_response({"types": types})


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
        "provider": "openai|anthropic" (optional),
        "save": true (default, save insights to DB),
        "check_similarity": true (default, merge similar insights)
    }
    
    Response includes:
        - insights: Extracted insight objects
        - tier0: Flags and emotion signals from signal extraction
        - entity_resolution: Results of matching entities against registry
            - resolved: Entities matched to known people (context injected to LLM)
            - unknown: Entities not yet identified (for user review)
            - context_injected: Whether entity context was added to the prompt
    
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
    
    # Resolve entities against registry for context injection (Phase 5)
    entity_context = ""
    entity_resolution = None
    if pre_annotation.get("entities"):
        entity_resolution = entity_registry.resolve_for_prompt(pre_annotation["entities"])
        entity_context = entity_resolution.get("prompt_context", "")
        if entity_resolution.get("resolved"):
            logger.info(f"Resolved {len(entity_resolution['resolved'])} entities for extraction")
        if entity_resolution.get("unknown"):
            logger.debug(f"Found {len(entity_resolution['unknown'])} unknown entities")
    
    # Build prompt with entity context
    prompt = build_extraction_prompt(
        content=text,
        source_type=source_type,
        source_description=source_id,
        pre_annotation=pre_annotation,
        is_chat=is_chat,
        additional_context=entity_context,
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
        
        # Build entity resolution summary for response
        entity_resolution_summary = None
        if entity_resolution:
            entity_resolution_summary = {
                "resolved_count": len(entity_resolution.get("resolved", [])),
                "unknown_count": len(entity_resolution.get("unknown", [])),
                "resolved": entity_resolution.get("resolved", []),
                "unknown": entity_resolution.get("unknown", []),
                "context_injected": bool(entity_context),
            }
        
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
            "entity_resolution": entity_resolution_summary,
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
# CRITIQUE ENGINE (Validation Layer)
# =============================================================================

@app.route("/api/critique/insight", methods=["POST"])
@require_json
def critique_insight():
    """
    Run critique validation on an insight.
    
    Body: {
        "insight_id": "abc123",  # OR provide insight object directly
        "insight": {...},         # Direct insight object
        "provider": "openai|anthropic" (optional)
    }
    
    Returns critique report with pass/fail/warn/refine verdict.
    """
    if not Config.LLM_CONFIGURED:
        return api_response(
            error="LLM not configured. Set API keys in environment.",
            status=503
        )
    
    data = request.get_json()
    
    # Get insight either by ID or from body
    insight = data.get("insight")
    if not insight:
        insight_id = data.get("insight_id")
        if insight_id:
            insight = insight_store.get_insight(insight_id)
            if not insight:
                return api_response(error="Insight not found", status=404)
        else:
            return api_response(error="insight or insight_id required", status=400)
    
    provider_name = data.get("provider")
    
    try:
        provider = create_provider(provider_name)
        report = critique_engine.critique_insight(insight, provider)
        
        # Optionally save critique
        if data.get("save", True):
            critique_engine.save_critique(report)
        
        return api_response({
            "critique_id": report.id,
            "target_type": report.target_type,
            "target_id": report.target_id,
            "overall_result": report.overall_result,
            "overall_score": report.overall_score,
            "passed": report.passed,
            "needs_refinement": report.needs_refinement,
            "checks": [{
                "check_type": c.check_type,
                "result": c.result,
                "score": c.score,
                "reason": c.reason,
                "suggestions": c.suggestions,
            } for c in report.checks],
            "recommendation": report.recommendation,
            "refinement_prompt": report.refinement_prompt,
            "model_used": report.model_used,
        })
        
    except Exception as e:
        logger.exception("Critique failed")
        return api_response(error=str(e), status=500)


@app.route("/api/critique/pattern", methods=["POST"])
@require_json
def critique_pattern():
    """
    Run critique validation on a synthesised pattern.
    
    Body: {
        "pattern_id": "pat_123",
        "provider": "openai|anthropic" (optional)
    }
    
    Fetches pattern and supporting insights, then validates.
    """
    if not Config.LLM_CONFIGURED:
        return api_response(
            error="LLM not configured. Set API keys in environment.",
            status=503
        )
    
    data = request.get_json()
    pattern_id = data.get("pattern_id")
    
    if not pattern_id:
        return api_response(error="pattern_id required", status=400)
    
    # Get pattern
    pattern = synth_engine.get_pattern(pattern_id)
    if not pattern:
        return api_response(error="Pattern not found", status=404)
    
    # Get supporting insights
    supporting_insight_ids = pattern.get("supporting_insight_ids", [])
    supporting_insights = []
    for iid in supporting_insight_ids[:10]:  # Cap at 10
        ins = insight_store.get_insight(iid)
        if ins:
            supporting_insights.append(ins)
    
    provider_name = data.get("provider")
    
    try:
        provider = create_provider(provider_name)
        report = critique_engine.critique_pattern(pattern, supporting_insights, provider)
        
        # Optionally save critique
        if data.get("save", True):
            critique_engine.save_critique(report)
        
        return api_response({
            "critique_id": report.id,
            "target_type": report.target_type,
            "target_id": report.target_id,
            "overall_result": report.overall_result,
            "overall_score": report.overall_score,
            "passed": report.passed,
            "needs_refinement": report.needs_refinement,
            "checks": [{
                "check_type": c.check_type,
                "result": c.result,
                "score": c.score,
                "reason": c.reason,
                "suggestions": c.suggestions,
            } for c in report.checks],
            "recommendation": report.recommendation,
            "refinement_prompt": report.refinement_prompt,
            "model_used": report.model_used,
        })
        
    except Exception as e:
        logger.exception("Pattern critique failed")
        return api_response(error=str(e), status=500)


@app.route("/api/critique/refine", methods=["POST"])
@require_json
def critique_and_refine():
    """
    Run critique with automatic refinement loop.
    
    Body: {
        "insight_id": "abc123",
        "max_iterations": 2,
        "provider": "openai|anthropic" (optional)
    }
    
    Attempts to refine insight if critique suggests it, up to max_iterations.
    """
    if not Config.LLM_CONFIGURED:
        return api_response(
            error="LLM not configured. Set API keys in environment.",
            status=503
        )
    
    data = request.get_json()
    insight_id = data.get("insight_id")
    
    if not insight_id:
        return api_response(error="insight_id required", status=400)
    
    insight = insight_store.get_insight(insight_id)
    if not insight:
        return api_response(error="Insight not found", status=404)
    
    max_iterations = int(data.get("max_iterations", 2))
    critique_engine.max_refinements = max_iterations
    
    provider_name = data.get("provider")
    
    try:
        provider = create_provider(provider_name)
        
        final_insight, report, refinement_count = critique_engine.critique_with_refinement(
            insight, provider
        )
        
        # Save critique report
        critique_engine.save_critique(report)
        
        # Update insight if refined and passed
        insight_updated = False
        if refinement_count > 0 and report.passed:
            # Update the insight in the database with refined content
            insight_store.update_insight(
                insight_id,
                status="refined",
                significance=final_insight.get("significance"),
                themes=final_insight.get("themes"),
            )
            insight_updated = True
        
        return api_response({
            "critique_id": report.id,
            "overall_result": report.overall_result,
            "overall_score": report.overall_score,
            "passed": report.passed,
            "refinement_count": refinement_count,
            "insight_updated": insight_updated,
            "final_insight": final_insight,
            "checks": [{
                "check_type": c.check_type,
                "result": c.result,
                "score": c.score,
                "reason": c.reason,
            } for c in report.checks],
            "recommendation": report.recommendation,
        })
        
    except Exception as e:
        logger.exception("Critique refinement failed")
        return api_response(error=str(e), status=500)


@app.route("/api/critique/<critique_id>", methods=["GET"])
def get_critique(critique_id: str):
    """Get a critique report by ID."""
    critique = critique_engine.get_critique(critique_id)
    
    if not critique:
        return api_response(error="Critique not found", status=404)
    
    return api_response(critique)


@app.route("/api/critique/for/<target_type>/<target_id>", methods=["GET"])
def get_critiques_for_target(target_type: str, target_id: str):
    """
    Get all critiques for a specific insight or pattern.
    
    target_type: 'insight' or 'pattern'
    target_id: The ID of the target
    """
    if target_type not in ("insight", "pattern"):
        return api_response(error="target_type must be 'insight' or 'pattern'", status=400)
    
    critiques = critique_engine.get_critiques_for_target(target_type, target_id)
    
    return api_response({
        "target_type": target_type,
        "target_id": target_id,
        "critiques": critiques,
        "count": len(critiques),
    })


@app.route("/api/critique", methods=["GET"])
def list_critiques():
    """
    List critique reports.
    
    Query params:
        - target_type: 'insight' or 'pattern'
        - result: 'pass', 'fail', 'warn', 'refine'
        - limit: max results (default 100)
        - offset: pagination offset
    """
    target_type = request.args.get("target_type")
    result = request.args.get("result")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    
    data = critique_engine.list_critiques(
        target_type=target_type,
        result=result,
        limit=limit,
        offset=offset,
    )
    
    return api_response(data)


@app.route("/api/critique/stats", methods=["GET"])
def critique_stats():
    """Get critique statistics."""
    stats = critique_engine.get_stats()
    return api_response(stats)


@app.route("/api/critique/strictness", methods=["GET"])
def get_critique_strictness():
    """Get current critique strictness level."""
    return api_response({
        "strictness": critique_engine.strictness.value,
        "thresholds": {
            "min_overall_score": critique_engine.min_overall_score,
            "min_check_score": critique_engine.min_check_score,
            "require_all_pass": critique_engine.require_all_pass,
        },
    })


@app.route("/api/critique/strictness", methods=["POST"])
@require_json
def set_critique_strictness():
    """
    Set critique strictness level.
    
    Body: {"strictness": "lenient|standard|strict"}
    """
    data = request.get_json()
    level = data.get("strictness", "standard")
    
    try:
        critique_engine.strictness = StrictnessLevel(level)
        critique_engine._set_thresholds()
        
        return api_response({
            "strictness": critique_engine.strictness.value,
            "thresholds": {
                "min_overall_score": critique_engine.min_overall_score,
                "min_check_score": critique_engine.min_check_score,
                "require_all_pass": critique_engine.require_all_pass,
            },
        })
    except ValueError:
        return api_response(
            error=f"Invalid strictness level. Use: lenient, standard, strict",
            status=400
        )


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
    
    print(f"\n[RECOG] Server starting on http://localhost:{port}")
    print(f"        Database: {Config.DB_PATH}")
    print(f"        LLM providers: {', '.join(Config.AVAILABLE_PROVIDERS) or 'none'}")
    print()
    
    app.run(host="0.0.0.0", port=port, debug=debug)

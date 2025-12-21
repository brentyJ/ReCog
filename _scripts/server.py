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
)
from ingestion import detect_file, ingest_file
from db import init_database, check_database

# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """Server configuration."""
    DATA_DIR = Path(os.environ.get("RECOG_DATA_DIR", "./_data"))
    UPLOAD_DIR = DATA_DIR / "uploads"
    DB_PATH = DATA_DIR / "recog.db"
    
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {
        'txt', 'md', 'json', 'pdf', 'csv',
        'eml', 'msg', 'mbox',
    }
    
    # LLM config (optional - for extraction)
    LLM_PROVIDER = os.environ.get("RECOG_LLM_PROVIDER", "openai")
    LLM_API_KEY = os.environ.get("RECOG_LLM_API_KEY", "")
    LLM_MODEL = os.environ.get("RECOG_LLM_MODEL", "gpt-4o-mini")


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
        "llm_configured": bool(Config.LLM_API_KEY),
    })


@app.route("/api/info", methods=["GET"])
def info():
    """Server info endpoint."""
    return api_response({
        "name": "ReCog Server",
        "version": "0.1.0",
        "endpoints": [
            "/api/health",
            "/api/upload",
            "/api/detect",
            "/api/tier0",
            "/api/preflight/*",
            "/api/entities/*",
            "/api/insights/*",
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
        "is_chat": false
    }
    
    Requires RECOG_LLM_API_KEY environment variable.
    """
    if not Config.LLM_API_KEY:
        return api_response(error="LLM not configured. Set RECOG_LLM_API_KEY.", status=503)
    
    data = request.get_json()
    text = data.get("text", "")
    source_type = data.get("source_type", "unknown")
    source_id = data.get("source_id", str(uuid4()))
    is_chat = data.get("is_chat", False)
    
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
    
    # Call LLM
    try:
        import openai
        
        client = openai.OpenAI(api_key=Config.LLM_API_KEY)
        
        response = client.chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are an insight extraction system. Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        
        response_text = response.choices[0].message.content
        
        # Parse response
        result = parse_extraction_response(response_text, source_type, source_id)
        
        return api_response({
            "success": result.success,
            "insights": [i.to_dict() for i in result.insights],
            "content_quality": result.content_quality,
            "notes": result.notes,
            "tier0": {
                "flags": pre_annotation.get("flags", {}),
                "emotion_categories": pre_annotation.get("emotion_signals", {}).get("categories", []),
            },
        })
    
    except ImportError:
        return api_response(error="OpenAI package not installed", status=503)
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return api_response(error=str(e), status=500)


# =============================================================================
# INSIGHTS (Future: Database Storage)
# =============================================================================

@app.route("/api/insights", methods=["GET"])
def list_insights():
    """
    List extracted insights from database.
    
    Query params:
        - status: raw, refined, surfaced
        - min_significance: 0.0-1.0
        - limit: max results
    """
    # TODO: Implement database query
    return api_response({
        "insights": [],
        "message": "Database insight storage coming in Phase 4",
    })


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
    print(f"   LLM configured: {bool(Config.LLM_API_KEY)}")
    print()
    
    app.run(host="0.0.0.0", port=port, debug=debug)

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
from datetime import datetime, timezone
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
    # Case Architecture
    CaseStore,
    FindingsStore,
    TimelineStore,
    # Synth Engine
    SynthEngine,
    ClusterStrategy,
    # Critique Engine
    CritiqueEngine,
    StrictnessLevel,
)
from recog_engine.state_machine import CaseStateMachine
from recog_engine.cost_estimator import CostEstimator
from recog_engine.errors import (
    RecogError,
    FileTooLargeError,
    EmptyFileError,
    CorruptedFileError,
    UnsupportedFileTypeError,
    LLMNotConfiguredError,
    LLMProviderError,
    LLMAuthError,
    ValidationError,
    MissingFieldError,
    ResourceNotFoundError,
)
from recog_engine.core.providers import (
    create_provider,
    create_router,
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

# Case architecture stores
case_store = CaseStore(Config.DB_PATH)
findings_store = FindingsStore(Config.DB_PATH)
timeline_store = TimelineStore(Config.DB_PATH)

# Workflow state machine (v0.8)
state_machine = CaseStateMachine(Config.DB_PATH)
cost_estimator = CostEstimator(Config.DB_PATH)

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
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(RecogError)
def handle_recog_error(error: RecogError):
    """Handle all ReCog custom errors with user-friendly messages."""
    logger.error(f"ReCog error [{error.__class__.__name__}]: {error}")

    return api_response(
        error=error.user_message,
        data={"error_type": error.__class__.__name__},
        status=error.status_code
    )


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    """Handle unexpected errors - don't leak internal details."""
    logger.error(f"Unexpected error: {error}", exc_info=True)

    # Don't leak internal details in production
    if app.debug:
        error_detail = str(error)
    else:
        error_detail = "An unexpected error occurred. Please try again or contact support if the problem persists."

    return api_response(
        error=error_detail,
        data={"error_type": "UnexpectedError"},
        status=500
    )


@app.errorhandler(404)
def handle_not_found(error):
    """Handle 404 errors."""
    return api_response(
        error="Endpoint not found. Check /api/info for available endpoints.",
        status=404
    )


@app.errorhandler(405)
def handle_method_not_allowed(error):
    """Handle 405 errors."""
    return api_response(
        error=f"Method {request.method} not allowed for this endpoint.",
        status=405
    )


@app.errorhandler(413)
def handle_request_too_large(error):
    """Handle file too large errors from Flask/Werkzeug."""
    max_mb = app.config.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024) / (1024 * 1024)
    return api_response(
        error=f"File too large. Maximum size is {max_mb:.0f}MB.",
        status=413
    )


# =============================================================================
# HEALTH & INFO
# =============================================================================

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    db_status = check_database(Config.DB_PATH)
    
    # Get cases count
    cases_count = 0
    try:
        conn = _get_db_connection()
        cases_count = conn.execute("SELECT COUNT(*) FROM cases WHERE status = 'active'").fetchone()[0]
        conn.close()
    except:
        pass
    
    return api_response({
        "status": "healthy",
        "database": {
            "path": str(Config.DB_PATH),
            "tables": db_status.get("total_tables", 0),
            "rows": db_status.get("total_rows", 0),
            "cases": cases_count,
        },
        "llm_configured": Config.LLM_CONFIGURED,
        "available_providers": Config.AVAILABLE_PROVIDERS,
    })


@app.route("/api/info", methods=["GET"])
def info():
    """Server info endpoint."""
    return api_response({
        "name": "ReCog Server",
        "version": "0.8.0",
        "endpoints": [
            "/api/health",
            "/api/upload",
            "/api/upload/batch",
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
            "/api/entities/validate",
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
            "/api/cases",
            "/api/cases/<id>",
            "/api/cases/<id>/documents",
            "/api/cases/<id>/stats",
            "/api/cases/<id>/context",
            "/api/cases/<id>/progress",
            "/api/cases/<id>/estimate",
            "/api/cases/<id>/start-processing",
            "/api/cases/<id>/findings",
            "/api/cases/<id>/findings/auto-promote",
            "/api/cases/<id>/findings/stats",
            "/api/cases/<id>/timeline",
            "/api/cases/<id>/timeline/summary",
            "/api/cases/<id>/timeline/daily",
            "/api/cases/<id>/activity",
            "/api/findings",
            "/api/findings/<id>",
            "/api/findings/<id>/note",
            "/api/timeline/<id>/annotate",
            "/api/cypher/message",
            "/api/extraction/status/<case_id>",
            "/api/providers",
            "/api/providers/<provider>",
            "/api/providers/<provider>/verify",
        ],
    })


# =============================================================================
# PROVIDER MANAGEMENT
# =============================================================================

# Provider configuration with supported models
PROVIDER_CONFIG = {
    "openai": {
        "display_name": "OpenAI",
        "env_key": "RECOG_OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "verification_model": "gpt-4o-mini",
    },
    "anthropic": {
        "display_name": "Anthropic (Claude)",
        "env_key": "RECOG_ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
        "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
        "verification_model": "claude-sonnet-4-20250514",
    },
}


def _get_env_file_path():
    """Get path to .env file."""
    return Path(__file__).parent / ".env"


def _read_env_file():
    """Read .env file and return dict of key-value pairs."""
    env_path = _get_env_file_path()
    env_vars = {}

    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    env_vars[key] = value

    return env_vars


def _write_env_file(env_vars: dict):
    """Write dict of key-value pairs to .env file, preserving comments."""
    env_path = _get_env_file_path()

    # Keys we manage - don't preserve these if not in env_vars
    managed_keys = {config["env_key"] for config in PROVIDER_CONFIG.values()}

    # Read existing file to preserve comments and order
    lines = []
    existing_keys = set()

    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('#') or not stripped:
                    lines.append(line.rstrip('\n'))
                elif '=' in stripped:
                    key = stripped.split('=')[0].strip()
                    existing_keys.add(key)
                    if key in env_vars:
                        value = env_vars[key]
                        # Quote if contains spaces
                        if ' ' in value or not value:
                            value = f'"{value}"'
                        lines.append(f'{key}={value}')
                    elif key not in managed_keys:
                        # Preserve non-managed keys (user's other env vars)
                        lines.append(line.rstrip('\n'))
                    # else: managed key not in env_vars = deleted, skip it

    # Add new keys not in file
    for key, value in env_vars.items():
        if key not in existing_keys:
            if ' ' in value or not value:
                value = f'"{value}"'
            lines.append(f'{key}={value}')

    # Write back
    with open(env_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def _mask_api_key(key: str) -> str:
    """Mask API key for display (show first 4 and last 4 chars)."""
    if not key or len(key) < 12:
        return "****"
    return f"{key[:7]}...{key[-4:]}"


def _verify_provider(provider_name: str, api_key: str) -> dict:
    """
    Verify an API key works by making a minimal API call.
    Returns dict with 'valid', 'message', 'model' keys.
    """
    config = PROVIDER_CONFIG.get(provider_name)
    if not config:
        return {"valid": False, "message": f"Unknown provider: {provider_name}"}

    try:
        if provider_name == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            # List models - minimal cost operation
            models = client.models.list()
            return {
                "valid": True,
                "message": "API key verified successfully",
                "model": config["default_model"],
            }

        elif provider_name == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            # Minimal message - costs fraction of a cent
            response = client.messages.create(
                model=config["verification_model"],
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}]
            )
            return {
                "valid": True,
                "message": "API key verified successfully",
                "model": config["default_model"],
            }

    except Exception as e:
        error_str = str(e).lower()
        if "invalid" in error_str or "unauthorized" in error_str or "authentication" in error_str:
            return {"valid": False, "message": "Invalid API key"}
        elif "rate" in error_str or "quota" in error_str:
            return {"valid": False, "message": "Rate limit or quota exceeded"}
        elif "permission" in error_str:
            return {"valid": False, "message": "API key lacks required permissions"}
        else:
            return {"valid": False, "message": f"Verification failed: {str(e)[:100]}"}

    return {"valid": False, "message": "Unknown error during verification"}


@app.route("/api/providers", methods=["GET"])
def list_providers():
    """
    List all supported providers and their configuration status.

    Returns for each provider:
    - configured: Whether API key is set
    - active: Whether it's available for use
    - display_name: Human-readable name
    - masked_key: Masked API key (if configured)
    - last_verified: Timestamp of last verification (if any)
    """
    env_vars = _read_env_file()
    providers = []

    for name, config in PROVIDER_CONFIG.items():
        key = env_vars.get(config["env_key"], "") or os.environ.get(config["env_key"], "")
        is_configured = bool(key)

        providers.append({
            "name": name,
            "display_name": config["display_name"],
            "configured": is_configured,
            "active": name in Config.AVAILABLE_PROVIDERS,
            "masked_key": _mask_api_key(key) if is_configured else None,
            "default_model": config["default_model"],
            "models": config["models"],
        })

    # Sort: configured first, then alphabetically
    providers.sort(key=lambda p: (not p["configured"], p["name"]))

    return api_response({
        "providers": providers,
        "active_count": len([p for p in providers if p["active"]]),
        "configured_count": len([p for p in providers if p["configured"]]),
    })


@app.route("/api/providers/<provider>", methods=["GET"])
def get_provider(provider: str):
    """Get details for a specific provider."""
    if provider not in PROVIDER_CONFIG:
        raise ResourceNotFoundError("provider", provider)

    config = PROVIDER_CONFIG[provider]
    env_vars = _read_env_file()
    key = env_vars.get(config["env_key"], "") or os.environ.get(config["env_key"], "")
    is_configured = bool(key)

    return api_response({
        "name": provider,
        "display_name": config["display_name"],
        "configured": is_configured,
        "active": provider in Config.AVAILABLE_PROVIDERS,
        "masked_key": _mask_api_key(key) if is_configured else None,
        "default_model": config["default_model"],
        "models": config["models"],
        "env_key": config["env_key"],
    })


@app.route("/api/providers/<provider>", methods=["POST"])
@require_json
def configure_provider(provider: str):
    """
    Configure a provider with an API key.

    Body: {
        "api_key": "sk-...",
        "verify": true  (optional, default true)
    }

    Saves key to .env file and optionally verifies it.
    """
    if provider not in PROVIDER_CONFIG:
        raise ResourceNotFoundError("provider", provider)

    data = request.get_json()
    api_key = data.get("api_key", "").strip()
    should_verify = data.get("verify", True)

    if not api_key:
        raise MissingFieldError("api_key")

    config = PROVIDER_CONFIG[provider]

    # Verify first if requested
    verification = None
    if should_verify:
        verification = _verify_provider(provider, api_key)
        if not verification["valid"]:
            return api_response(
                error=verification["message"],
                data={"verified": False, "provider": provider},
                status=400
            )

    # Save to .env file
    env_vars = _read_env_file()
    env_vars[config["env_key"]] = api_key
    _write_env_file(env_vars)

    # Update os.environ so it takes effect immediately
    os.environ[config["env_key"]] = api_key

    # Refresh available providers
    Config.AVAILABLE_PROVIDERS = get_available_providers()
    Config.LLM_CONFIGURED = len(Config.AVAILABLE_PROVIDERS) > 0

    logger.info(f"Provider {provider} configured successfully")

    return api_response({
        "provider": provider,
        "configured": True,
        "verified": verification["valid"] if verification else None,
        "message": f"{config['display_name']} API key saved successfully",
        "active": provider in Config.AVAILABLE_PROVIDERS,
    })


@app.route("/api/providers/<provider>", methods=["DELETE"])
def remove_provider(provider: str):
    """
    Remove a provider's API key.

    This removes the key from .env and makes the provider unavailable.
    """
    if provider not in PROVIDER_CONFIG:
        raise ResourceNotFoundError("provider", provider)

    config = PROVIDER_CONFIG[provider]

    # Remove from .env file
    env_vars = _read_env_file()
    if config["env_key"] in env_vars:
        del env_vars[config["env_key"]]
        _write_env_file(env_vars)

    # Remove from os.environ
    if config["env_key"] in os.environ:
        del os.environ[config["env_key"]]

    # Refresh available providers
    Config.AVAILABLE_PROVIDERS = get_available_providers()
    Config.LLM_CONFIGURED = len(Config.AVAILABLE_PROVIDERS) > 0

    logger.info(f"Provider {provider} removed")

    return api_response({
        "provider": provider,
        "configured": False,
        "message": f"{config['display_name']} API key removed",
    })


@app.route("/api/providers/<provider>/verify", methods=["POST"])
def verify_provider(provider: str):
    """
    Verify a provider's API key is working.

    Makes a minimal API call to test the key.
    Returns whether the key is valid and any error message.
    """
    if provider not in PROVIDER_CONFIG:
        raise ResourceNotFoundError("provider", provider)

    config = PROVIDER_CONFIG[provider]
    env_vars = _read_env_file()
    api_key = env_vars.get(config["env_key"], "") or os.environ.get(config["env_key"], "")

    if not api_key:
        return api_response(
            error=f"No API key configured for {config['display_name']}",
            data={"configured": False, "valid": False},
            status=400
        )

    result = _verify_provider(provider, api_key)

    if result["valid"]:
        return api_response({
            "provider": provider,
            "valid": True,
            "message": result["message"],
            "model": result.get("model"),
        })
    else:
        return api_response(
            error=result["message"],
            data={"provider": provider, "valid": False},
            status=400
        )


@app.route("/api/providers/status", methods=["GET"])
def providers_status():
    """
    Quick status check for all providers.

    Returns a simple status for router display:
    - primary: First available provider (preferred for quality)
    - fallback: Second available provider (if any)
    - failover_enabled: Whether automatic failover is possible
    """
    available = Config.AVAILABLE_PROVIDERS

    # Determine primary and fallback based on preference
    # Anthropic preferred for quality, OpenAI as fallback
    primary = None
    fallback = None

    if "anthropic" in available:
        primary = "anthropic"
        if "openai" in available:
            fallback = "openai"
    elif "openai" in available:
        primary = "openai"

    return api_response({
        "configured": len(available) > 0,
        "primary": primary,
        "primary_name": PROVIDER_CONFIG[primary]["display_name"] if primary else None,
        "fallback": fallback,
        "fallback_name": PROVIDER_CONFIG[fallback]["display_name"] if fallback else None,
        "failover_enabled": primary is not None and fallback is not None,
        "available_providers": available,
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
    Upload file and create preflight session with auto-progression.

    Accepts multipart form data:
        - file: The file to upload
        - case_id: Optional case UUID to link for context injection
        - auto_process: Optional bool to enable auto-progression (default: true)

    Returns preflight session ID and case state for workflow.

    v0.8: Auto-creates case if none provided, transitions to scanning state.
    """
    if "file" not in request.files:
        return api_response(error="No file provided", status=400)

    file = request.files["file"]
    if file.filename == "":
        return api_response(error="No file selected", status=400)

    # Get optional case_id from form data
    case_id = request.form.get("case_id")
    auto_process = request.form.get("auto_process", "true").lower() != "false"

    # Save file
    filename = secure_filename(file.filename)
    file_id = uuid4().hex[:8]
    saved_path = Config.UPLOAD_DIR / f"{file_id}_{filename}"
    file.save(str(saved_path))

    logger.info(f"Uploaded: {saved_path}" + (f" (case: {case_id})" if case_id else ""))

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

    # Create preflight session with optional case link
    try:
        # v0.8: Auto-create case if not provided
        case_created = False
        if not case_id and auto_process:
            case = case_store.create_case(
                title=f"Analysis {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                context="",
            )
            case_id = case.id
            case_created = True
            logger.info(f"Auto-created case {case_id}")

        session_id = preflight_manager.create_session(
            session_type="single_file",
            source_files=[str(saved_path)],
            case_id=case_id,
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

        # Scan session (runs Tier 0)
        scan_result = preflight_manager.scan_session(session_id)

        # v0.8: Transition case state after Tier 0 completes
        case_state = None
        if case_id and auto_process:
            # Tier 0 is complete, advance from uploading -> scanning -> next
            state_machine.transition_to(case_id, "scanning")

            # Determine next state based on unknown entities
            if scan_result["unknown_entities"] > 0:
                state_machine.advance_case(case_id, {
                    "tier0_complete": True,
                    "unknown_entities": True
                })
                case_state = "clarifying"
            else:
                state_machine.advance_case(case_id, {
                    "tier0_complete": True,
                    "unknown_entities": False
                })
                case_state = "processing"

            # Update estimated cost on case
            estimate = cost_estimator.estimate_extraction_cost(case_id)
            cost_estimator.update_estimated_cost(case_id, estimate["estimated_cost_usd"])

        return api_response({
            "uploaded": True,
            "file_id": file_id,
            "filename": filename,
            "supported": True,
            "preflight_session_id": session_id,
            "case_id": case_id,
            "case_created": case_created,
            "case_state": case_state,
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


@app.route("/api/upload/batch", methods=["POST"])
def upload_batch():
    """
    Upload multiple files into a single preflight session with auto-progression.

    Accepts multipart form data with multiple files:
        - files: Multiple files to upload
        - case_id: Optional case UUID to link for context injection
        - auto_process: Optional bool to enable auto-progression (default: true)

    Returns preflight session ID with all items for review.

    v0.8: Auto-creates case if none provided, transitions to scanning state.
    """
    if "files" not in request.files:
        return api_response(error="No files provided", status=400)

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return api_response(error="No files selected", status=400)

    # Get optional case_id from form data
    case_id = request.form.get("case_id")
    auto_process = request.form.get("auto_process", "true").lower() != "false"

    # Save all files first
    saved_files = []
    for file in files:
        if file.filename == "":
            continue
        filename = secure_filename(file.filename)
        file_id = uuid4().hex[:8]
        saved_path = Config.UPLOAD_DIR / f"{file_id}_{filename}"
        file.save(str(saved_path))
        saved_files.append({
            "path": saved_path,
            "filename": filename,
            "file_id": file_id,
        })

    if not saved_files:
        return api_response(error="No valid files to process", status=400)

    logger.info(f"Batch upload: {len(saved_files)} files" + (f" (case: {case_id})" if case_id else ""))

    # Create ONE preflight session for all files
    try:
        # v0.8: Auto-create case if not provided
        case_created = False
        if not case_id and auto_process:
            case = case_store.create_case(
                title=f"Analysis {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                context="",
            )
            case_id = case.id
            case_created = True
            logger.info(f"Auto-created case {case_id}")

        session_id = preflight_manager.create_session(
            session_type="batch",
            source_files=[str(f["path"]) for f in saved_files],
            case_id=case_id,
        )

        results = []
        total_items = 0
        total_words = 0

        for file_info in saved_files:
            saved_path = file_info["path"]
            filename = file_info["filename"]

            # Detect format
            detection = detect_file(str(saved_path))

            if not detection.supported:
                results.append({
                    "filename": filename,
                    "supported": False,
                    "message": detection.action_message,
                })
                continue

            # Ingest and add to preflight session
            try:
                documents = ingest_file(str(saved_path))

                for doc in documents:
                    preflight_manager.add_item(
                        session_id=session_id,
                        source_type=doc.source_type,
                        content=doc.content,
                        source_id=doc.id,
                        title=doc.metadata.get("title", filename) if doc.metadata else filename,
                    )
                    total_items += 1

                results.append({
                    "filename": filename,
                    "supported": True,
                    "items": len(documents),
                })
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                results.append({
                    "filename": filename,
                    "supported": False,
                    "error": str(e),
                })

        # Scan session (runs Tier 0)
        scan_result = preflight_manager.scan_session(session_id)

        # v0.8: Transition case state after Tier 0 completes
        case_state = None
        if case_id and auto_process:
            # Tier 0 is complete, advance from uploading -> scanning -> next
            state_machine.transition_to(case_id, "scanning")

            # Determine next state based on unknown entities
            if scan_result["unknown_entities"] > 0:
                state_machine.advance_case(case_id, {
                    "tier0_complete": True,
                    "unknown_entities": True
                })
                case_state = "clarifying"
            else:
                state_machine.advance_case(case_id, {
                    "tier0_complete": True,
                    "unknown_entities": False
                })
                case_state = "processing"

            # Update estimated cost on case
            estimate = cost_estimator.estimate_extraction_cost(case_id)
            cost_estimator.update_estimated_cost(case_id, estimate["estimated_cost_usd"])

        return api_response({
            "uploaded": True,
            "file_count": len(saved_files),
            "preflight_session_id": session_id,
            "case_id": case_id,
            "case_created": case_created,
            "case_state": case_state,
            "items": scan_result["item_count"],
            "words": scan_result["total_words"],
            "entities": scan_result["total_entities"],
            "unknown_entities": scan_result["unknown_entities"],
            "estimated_cost_cents": scan_result["estimated_cost_cents"],
            "questions": scan_result["questions"][:5],
            "file_results": results,
        })

    except Exception as e:
        logger.error(f"Batch upload processing error: {e}")
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


@app.route("/api/entities/validate", methods=["POST"])
def validate_entities():
    """
    Validate unconfirmed person entities using LLM.

    Uses AI to identify false positives (e.g., "Foundation", "Research", "Protocol")
    and removes them from the registry, adding to the blacklist.

    Request body (optional):
        {
            "batch_size": 50  // Number of entities to validate (default 50)
        }

    Returns:
        {
            "validated": int,        // Total entities checked
            "removed": int,          // Number removed as false positives
            "kept": int,             // Number kept as valid
            "removed_names": [...],  // Names that were removed
            "message": str
        }
    """
    try:
        data = request.get_json() or {}
        batch_size = int(data.get("batch_size", 50))

        # Validate using the registry method
        result = entity_registry.validate_unconfirmed_persons(batch_size=batch_size)

        # Refresh tier0 blacklist after validation
        if result.get('removed', 0) > 0:
            from recog_engine.tier0 import load_blacklist_from_db
            load_blacklist_from_db(Config.DB_PATH)

        return api_response(result)

    except Exception as e:
        logger.error(f"Entity validation failed: {e}", exc_info=True)
        return api_response(error=str(e), status=500)


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
        "case_id": "optional-case-uuid" (for case context injection),
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
        - case_context_injected: Whether case context was added to the prompt
    
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
    case_id = data.get("case_id")  # Optional case for context injection
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
    
    # Get case context if case_id provided
    case_context_dict = None
    case_context_injected = False
    if case_id:
        case_obj = case_store.get_case(case_id)
        if case_obj:
            case_context_dict = {
                "title": case_obj.title,
                "context": case_obj.context,
                "focus_areas": case_obj.focus_areas or [],
            }
            case_context_injected = True
            logger.info(f"Injecting case context: {case_obj.title}")
        else:
            logger.warning(f"Case {case_id} not found, proceeding without case context")
    
    # Build prompt with entity and case context
    prompt = build_extraction_prompt(
        content=text,
        source_type=source_type,
        source_description=source_id,
        pre_annotation=pre_annotation,
        is_chat=is_chat,
        additional_context=entity_context,
        case_context=case_context_dict,
    )
    
    # Call LLM via router with automatic failover
    try:
        # Use router for automatic failover between providers
        # If provider_name specified, prefer that provider first
        preference = [provider_name] if provider_name else None
        router = create_router(provider_preference=preference)

        response = router.generate(
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
                    case_id=case_id,  # Associate insights with case
                )
                save_results = batch_result.get("results", [])
                logger.info(f"Saved {batch_result['created']} new, merged {batch_result['merged']} insights")
                
                # Log timeline event if case_id provided
                if case_id and batch_result.get("created", 0) > 0:
                    timeline_store.log_event(
                        case_id,
                        "insights_extracted",
                        {
                            "count": batch_result.get("created", 0),
                            "source_type": source_type,
                            "source_id": source_id,
                        },
                    )

        # Register entities from Tier 0 extraction
        entity_registration = None
        if pre_annotation.get("entities") and data.get("save", True):
            entity_registration = entity_registry.register_from_tier0(
                pre_annotation["entities"],
                source_type=source_type,
                source_id=source_id,
            )
            new_count = sum(1 for results in entity_registration.values() for _, is_new in results if is_new)
            if new_count > 0:
                logger.info(f"Registered {new_count} new entities")

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
        
        # Build entity registration summary
        entities_registered = None
        if entity_registration:
            entities_registered = {
                entity_type: {"total": len(results), "new": sum(1 for _, is_new in results if is_new)}
                for entity_type, results in entity_registration.items()
                if results
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
            "entities_registered": entities_registered,
            "case_id": case_id,
            "case_context_injected": case_context_injected,
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


@app.route("/api/insights/activity", methods=["GET"])
def insight_activity():
    """
    Get insight creation activity over time.

    Query params:
        - days: Number of days to look back (default 30)

    Returns daily counts of insights created.
    """
    days = int(request.args.get("days", 30))

    conn = _get_db_connection()
    try:
        rows = conn.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM insights
            WHERE created_at >= datetime('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """, (f'-{days} days',)).fetchall()

        activity = [{"date": row["date"], "count": row["count"]} for row in rows]

        return api_response({
            "activity": activity,
            "days": days,
            "total": sum(r["count"] for r in activity),
        })
    finally:
        conn.close()


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
# CASE MANAGEMENT
# =============================================================================

@app.route("/api/cases", methods=["POST"])
@require_json
def create_case():
    """
    Create a new case.
    
    Body: {
        "title": "Q3 Sales Investigation",
        "context": "Revenue dropped 15%, need root cause",
        "focus_areas": ["pricing", "competition", "market"]
    }
    """
    data = request.get_json()
    
    title = data.get("title")
    if not title:
        return api_response(error="title required", status=400)
    
    case = case_store.create_case(
        title=title,
        context=data.get("context", ""),
        focus_areas=data.get("focus_areas"),
    )
    
    return api_response(case.to_dict())


@app.route("/api/cases", methods=["GET"])
def list_cases():
    """
    List all cases.
    
    Query params:
        - status: active, archived
        - limit: max results (default 100)
        - offset: pagination offset
        - order_by: created_at, updated_at, title, document_count
        - order_dir: ASC or DESC
    """
    status = request.args.get("status")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    order_by = request.args.get("order_by", "updated_at")
    order_dir = request.args.get("order_dir", "DESC")
    
    result = case_store.list_cases(
        status=status,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_dir=order_dir,
    )
    
    return api_response(result)


@app.route("/api/cases/<case_id>", methods=["GET"])
def get_case(case_id: str):
    """Get case details by ID."""
    case = case_store.get_case(case_id)
    
    if not case:
        return api_response(error="Case not found", status=404)
    
    return api_response(case.to_dict())


@app.route("/api/cases/<case_id>", methods=["PATCH"])
@require_json
def update_case(case_id: str):
    """
    Update case fields.
    
    Body: {
        "title": "Updated title",
        "context": "Updated context",
        "focus_areas": ["new", "areas"],
        "status": "archived"
    }
    """
    data = request.get_json()
    
    success = case_store.update_case(
        case_id,
        title=data.get("title"),
        context=data.get("context"),
        focus_areas=data.get("focus_areas"),
        status=data.get("status"),
    )
    
    if success:
        case = case_store.get_case(case_id)
        return api_response(case.to_dict())
    
    return api_response(error="Case not found or update failed", status=404)


@app.route("/api/cases/<case_id>", methods=["DELETE"])
def delete_case(case_id: str):
    """Delete a case and all related data (cascade)."""
    success = case_store.delete_case(case_id)
    
    if success:
        return api_response({"deleted": True, "case_id": case_id})
    
    return api_response(error="Case not found", status=404)


@app.route("/api/cases/<case_id>/documents", methods=["GET"])
def list_case_documents(case_id: str):
    """List all documents in a case."""
    docs = case_store.list_documents(case_id)
    return api_response({
        "case_id": case_id,
        "documents": docs,
        "count": len(docs),
    })


@app.route("/api/cases/<case_id>/documents", methods=["POST"])
@require_json
def add_case_document(case_id: str):
    """
    Add a document to a case.
    
    Body: {
        "document_id": "preflight_item_123",
        "impact_notes": "This document contains key financial data"
    }
    """
    data = request.get_json()
    
    document_id = data.get("document_id")
    if not document_id:
        return api_response(error="document_id required", status=400)
    
    doc = case_store.add_document(
        case_id,
        document_id,
        impact_notes=data.get("impact_notes", ""),
    )
    
    if doc:
        return api_response(doc.to_dict())
    
    return api_response(error="Case not found or document already linked", status=400)


@app.route("/api/cases/<case_id>/documents/<document_id>", methods=["DELETE"])
def remove_case_document(case_id: str, document_id: str):
    """Remove a document from a case."""
    success = case_store.remove_document(case_id, document_id)

    if success:
        return api_response({"removed": True, "document_id": document_id})

    return api_response(error="Document not found in case", status=404)


# =============================================================================
# DOCUMENT TEXT RETRIEVAL
# =============================================================================

@app.route("/api/documents/<doc_id>/text", methods=["GET"])
def get_document_text(doc_id: str):
    """
    Get the original text of an uploaded document.

    Retrieves text from:
    - Preflight items (recently uploaded)
    - Document chunks (processed documents)

    Returns:
        {
            "document_id": str,
            "filename": str,
            "text": str,
            "format": str,
            "line_count": int,
            "char_count": int
        }
    """
    import sqlite3

    conn = sqlite3.connect(str(Config.DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Try preflight_items first (most recent uploads)
        # doc_id might be "preflight_item_123" or just "123"
        item_id = doc_id.replace("preflight_item_", "") if doc_id.startswith("preflight_item_") else doc_id

        cursor.execute("""
            SELECT id, title, content, source_type
            FROM preflight_items
            WHERE id = ? OR source_id = ?
        """, (item_id, doc_id))

        row = cursor.fetchone()

        if row and row['content']:
            text = row['content']
            return api_response({
                "document_id": doc_id,
                "filename": row['title'] or f"Document {row['id']}",
                "text": text,
                "format": _detect_text_format(text, row['source_type']),
                "line_count": text.count('\n') + 1,
                "char_count": len(text),
            })

        # Try document_chunks (ingested documents)
        cursor.execute("""
            SELECT d.id, d.filename, d.file_type,
                   GROUP_CONCAT(c.content, '\n\n---\n\n') as full_text
            FROM ingested_documents d
            LEFT JOIN document_chunks c ON c.document_id = d.id
            WHERE d.id = ? OR d.file_hash = ?
            GROUP BY d.id
        """, (doc_id, doc_id))

        row = cursor.fetchone()

        if row and row['full_text']:
            text = row['full_text']
            return api_response({
                "document_id": doc_id,
                "filename": row['filename'] or f"Document {row['id']}",
                "text": text,
                "format": row['file_type'] or 'txt',
                "line_count": text.count('\n') + 1,
                "char_count": len(text),
            })

        # Document not found
        return api_response(
            error="Document not found",
            status=404
        )

    finally:
        conn.close()


def _detect_text_format(text: str, source_type: str = None) -> str:
    """Detect text format from content or source type."""
    if source_type:
        source_lower = source_type.lower()
        if 'markdown' in source_lower or 'md' in source_lower:
            return 'markdown'
        if 'json' in source_lower:
            return 'json'
        if 'csv' in source_lower:
            return 'csv'

    # Simple content-based detection
    text_start = text[:500] if text else ''
    if text_start.strip().startswith('{') or text_start.strip().startswith('['):
        return 'json'
    if text_start.startswith('#') or '\n## ' in text or '\n### ' in text:
        return 'markdown'

    return 'txt'


@app.route("/api/cases/<case_id>/stats", methods=["GET"])
def get_case_stats(case_id: str):
    """Get detailed statistics for a case."""
    stats = case_store.get_stats(case_id)
    
    if stats:
        return api_response(stats)
    
    return api_response(error="Case not found", status=404)


@app.route("/api/cases/<case_id>/context", methods=["GET"])
def get_case_context(case_id: str):
    """
    Get case context formatted for prompt injection.
    
    Returns the context string that would be injected into extraction prompts.
    """
    context = case_store.get_context(case_id)
    
    if context:
        return api_response({
            "case_id": case_id,
            "title": context.title,
            "context": context.context,
            "focus_areas": context.focus_areas,
            "prompt_string": context.to_prompt_string(),
        })
    
    return api_response(error="Case not found", status=404)


# =============================================================================
# FINDINGS MANAGEMENT
# =============================================================================

@app.route("/api/findings", methods=["POST"])
@require_json
def promote_to_finding():
    """
    Promote an insight to a finding.
    
    Body: {
        "case_id": "case_uuid",
        "insight_id": "insight_uuid",
        "auto_verify": false,
        "tags": ["important", "key-evidence"],
        "user_notes": "This is crucial for the investigation"
    }
    """
    data = request.get_json()
    
    case_id = data.get("case_id")
    insight_id = data.get("insight_id")
    
    if not case_id or not insight_id:
        return api_response(error="case_id and insight_id required", status=400)
    
    finding = findings_store.promote_insight(
        case_id,
        insight_id,
        auto_verify=data.get("auto_verify", False),
        tags=data.get("tags"),
        user_notes=data.get("user_notes", ""),
    )
    
    if finding:
        return api_response(finding.to_dict())
    
    return api_response(error="Case/insight not found or already promoted", status=400)


@app.route("/api/cases/<case_id>/findings", methods=["GET"])
def list_case_findings(case_id: str):
    """
    List findings for a case.
    
    Query params:
        - status: verified, needs_verification, rejected
        - tags: comma-separated tag filter
        - limit: max results (default 100)
        - offset: pagination offset
    """
    status = request.args.get("status")
    tags_str = request.args.get("tags")
    tags = tags_str.split(",") if tags_str else None
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    
    result = findings_store.list_findings(
        case_id,
        status=status,
        tags=tags,
        limit=limit,
        offset=offset,
    )
    
    return api_response(result)


@app.route("/api/findings/<finding_id>", methods=["GET"])
def get_finding(finding_id: str):
    """Get a finding by ID."""
    finding = findings_store.get_finding(finding_id)
    
    if not finding:
        return api_response(error="Finding not found", status=404)
    
    return api_response(finding.to_dict())


@app.route("/api/findings/<finding_id>", methods=["PATCH"])
@require_json
def update_finding(finding_id: str):
    """
    Update finding status or tags.
    
    Body: {
        "status": "verified|needs_verification|rejected",
        "tags": ["updated", "tags"]
    }
    """
    data = request.get_json()
    
    status = data.get("status")
    tags = data.get("tags")
    
    if status:
        success = findings_store.update_status(
            finding_id,
            status,
            verified_by="user",
        )
        if not success:
            return api_response(error="Finding not found", status=404)
    
    if tags is not None:
        findings_store.update_tags(finding_id, tags)
    
    finding = findings_store.get_finding(finding_id)
    return api_response(finding.to_dict() if finding else {"updated": True})


@app.route("/api/findings/<finding_id>/note", methods=["POST"])
@require_json
def add_finding_note(finding_id: str):
    """
    Add or update user notes on a finding.
    
    Body: {"note": "My analysis notes..."}
    """
    data = request.get_json()
    note = data.get("note", "")
    
    success = findings_store.add_note(finding_id, note)
    
    if success:
        return api_response({"noted": True, "finding_id": finding_id})
    
    return api_response(error="Finding not found", status=404)


@app.route("/api/findings/<finding_id>", methods=["DELETE"])
def delete_finding(finding_id: str):
    """Delete a finding (demote insight back to standalone)."""
    success = findings_store.delete_finding(finding_id)
    
    if success:
        return api_response({"deleted": True, "finding_id": finding_id})
    
    return api_response(error="Finding not found", status=404)


@app.route("/api/cases/<case_id>/findings/auto-promote", methods=["POST"])
@require_json
def auto_promote_findings(case_id: str):
    """
    Auto-promote high-quality insights to findings.
    
    Body: {
        "insight_ids": ["id1", "id2", ...],
        "min_confidence": 0.7,
        "min_significance": 0.6
    }
    """
    data = request.get_json()
    
    insight_ids = data.get("insight_ids", [])
    if not insight_ids:
        return api_response(error="insight_ids required", status=400)
    
    result = findings_store.auto_promote_insights(
        case_id,
        insight_ids,
        min_confidence=data.get("min_confidence", 0.7),
        min_significance=data.get("min_significance", 0.6),
    )
    
    return api_response(result)


@app.route("/api/cases/<case_id>/findings/stats", methods=["GET"])
def get_findings_stats(case_id: str):
    """Get findings statistics for a case."""
    stats = findings_store.get_stats(case_id)
    return api_response(stats)


# =============================================================================
# CASE TIMELINE
# =============================================================================

@app.route("/api/cases/<case_id>/timeline", methods=["GET"])
def get_case_timeline(case_id: str):
    """
    Get timeline events for a case.
    
    Query params:
        - event_types: comma-separated filter (case_created,doc_added,finding_verified,...)
        - since: ISO datetime filter (events after)
        - until: ISO datetime filter (events before)
        - limit: max results (default 100)
        - offset: pagination offset
        - order: ASC (oldest first) or DESC (newest first, default)
    """
    event_types_str = request.args.get("event_types")
    event_types = event_types_str.split(",") if event_types_str else None
    
    since = request.args.get("since")
    until = request.args.get("until")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    order = request.args.get("order", "DESC")
    
    result = timeline_store.get_timeline(
        case_id,
        event_types=event_types,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
        order=order,
    )
    
    return api_response(result)


@app.route("/api/cases/<case_id>/timeline", methods=["POST"])
@require_json
def add_timeline_annotation(case_id: str):
    """
    Add a human annotation/note to the timeline.
    
    Body: {
        "note": "Key discovery: This contradicts our initial hypothesis"
    }
    """
    data = request.get_json()
    note = data.get("note", "")
    
    if not note:
        return api_response(error="note required", status=400)
    
    event = timeline_store.log_event(
        case_id,
        "note_added",
        {"note": note},
        human_annotation=note,
    )
    
    return api_response(event.to_dict())


@app.route("/api/timeline/<event_id>/annotate", methods=["POST"])
@require_json
def annotate_timeline_event(event_id: str):
    """
    Add human annotation to an existing timeline event.
    
    Body: {"annotation": "This was a turning point in the investigation"}
    """
    data = request.get_json()
    annotation = data.get("annotation", "")
    
    success = timeline_store.add_annotation(event_id, annotation)
    
    if success:
        return api_response({"annotated": True, "event_id": event_id})
    
    return api_response(error="Event not found", status=404)


@app.route("/api/cases/<case_id>/timeline/summary", methods=["GET"])
def get_timeline_summary(case_id: str):
    """Get timeline summary statistics."""
    summary = timeline_store.get_summary(case_id)
    return api_response(summary)


@app.route("/api/cases/<case_id>/timeline/daily", methods=["GET"])
def get_daily_timeline(case_id: str):
    """
    Get daily event counts.
    
    Query params:
        - days: Number of days to summarize (default 7)
    """
    days = int(request.args.get("days", 7))
    daily = timeline_store.get_daily_summary(case_id, days=days)
    return api_response({
        "case_id": case_id,
        "daily": daily,
    })


@app.route("/api/cases/<case_id>/activity", methods=["GET"])
def get_case_activity(case_id: str):
    """
    Get recent activity for a case (convenience endpoint).
    
    Query params:
        - limit: Number of recent events (default 10)
    """
    limit = int(request.args.get("limit", 10))
    activity = timeline_store.get_recent_activity(case_id, limit=limit)
    return api_response({
        "case_id": case_id,
        "recent_activity": activity,
    })


# =============================================================================
# CASE PROGRESS & COST ESTIMATION (v0.8)
# =============================================================================

@app.route("/api/cases/<case_id>/progress", methods=["GET"])
def get_case_progress(case_id: str):
    """
    Get real-time progress for case processing.

    Returns:
        - stage: Current processing stage (tier0, extraction, synthesis)
        - status: Stage status (pending, running, complete, failed)
        - progress: 0.0-1.0 completion percentage
        - current_item: What's being processed
        - total_items: Total items to process
        - completed_items: Items done
        - recent_insight: Latest discovery for terminal display
        - top_insights: Top 5 insights by significance
    """
    # Get case to verify it exists
    case = case_store.get_case(case_id)
    if not case:
        return api_response(error="Case not found", status=404)

    # Get progress from state machine
    progress = state_machine.get_case_progress(case_id)

    # Get top insights for this case
    conn = _get_db_connection()
    try:
        top_insights = conn.execute("""
            SELECT id, summary, significance, confidence
            FROM insights
            WHERE case_id = ?
            ORDER BY significance DESC
            LIMIT 5
        """, (case_id,)).fetchall()

        progress["top_insights"] = [
            {
                "id": row["id"],
                "content": row["summary"],
                "significance": row["significance"],
                "confidence": row["confidence"],
            }
            for row in top_insights
        ]
    finally:
        conn.close()

    # Add case state
    progress["case_state"] = case.status if hasattr(case, 'status') else state_machine.get_case_state(case_id)

    return api_response(progress)


@app.route("/api/cases/<case_id>/estimate", methods=["GET"])
def get_case_cost_estimate(case_id: str):
    """
    Get cost estimate for case processing.

    Query params:
        - model: Optional model override (default: gpt-4o-mini)

    Returns:
        - extraction: Extraction cost breakdown
        - synthesis: Synthesis cost breakdown
        - total_tokens: Combined token estimate
        - total_cost_usd: Combined cost in USD
    """
    case = case_store.get_case(case_id)
    if not case:
        return api_response(error="Case not found", status=404)

    model = request.args.get("model")
    estimate = cost_estimator.estimate_total_cost(case_id, model)

    return api_response({
        "case_id": case_id,
        **estimate
    })


@app.route("/api/cases/<case_id>/start-processing", methods=["POST"])
def start_case_processing(case_id: str):
    """
    Manually start processing for a case in 'clarifying' state.

    This allows the user to confirm cost and begin extraction/synthesis
    after entity clarification is complete.

    Body: {
        "confirm_cost": true  # Required to acknowledge cost
    }
    """
    case = case_store.get_case(case_id)
    if not case:
        return api_response(error="Case not found", status=404)

    current_state = state_machine.get_case_state(case_id)
    if current_state not in ("clarifying", "complete"):
        return api_response(
            error=f"Cannot start processing from state: {current_state}",
            status=400
        )

    data = request.get_json() or {}
    if not data.get("confirm_cost"):
        # Return cost estimate for confirmation
        estimate = cost_estimator.estimate_extraction_cost(case_id)
        return api_response({
            "requires_confirmation": True,
            "estimated_cost_usd": estimate["estimated_cost_usd"],
            "document_count": estimate["document_count"],
            "message": "Set confirm_cost: true to proceed"
        })

    # Transition to processing
    success = state_machine.transition_to(case_id, "processing")

    if success:
        return api_response({
            "started": True,
            "case_id": case_id,
            "state": "processing",
            "message": "Processing started. Watch progress via /api/cases/<id>/progress"
        })

    return api_response(error="Failed to start processing", status=500)


# =============================================================================
# CYPHER - Conversational Analysis Interface
# =============================================================================

# Initialize Anthropic client for Cypher (optional - for LLM fallback)
_anthropic_client = None
try:
    import anthropic
    _api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("RECOG_ANTHROPIC_API_KEY")
    if _api_key:
        _anthropic_client = anthropic.Anthropic(api_key=_api_key)
        logger.info("Cypher: Anthropic client initialized for LLM fallback")
except ImportError:
    logger.warning("Cypher: anthropic package not installed, LLM fallback disabled")
except Exception as e:
    logger.warning(f"Cypher: Could not initialize Anthropic client: {e}")


@app.route("/api/cypher/message", methods=["POST"])
def cypher_message():
    """
    Handle Cypher conversational interface messages.

    Request body:
        - message: User's message text
        - case_id: Optional case context
        - context: Additional context (current_view, processing_status, etc.)

    Response:
        - reply: Cypher's response text
        - actions: Backend actions executed
        - ui_updates: Frontend UI updates needed
        - suggestions: Contextual action buttons
        - metadata: Intent classification info
    """
    import time
    start_time = time.time()

    try:
        data = request.json or {}
        message = data.get("message", "").strip()
        case_id = data.get("case_id")
        context = data.get("context", {})

        if not message:
            return api_response(error="Message required", status=400)

        # Import Cypher modules
        from recog_engine.cypher import (
            classify_intent,
            CypherActionRouter,
            format_cypher_response,
        )

        # Add case context if we have a case_id
        if case_id:
            try:
                case = case_store.get(case_id)
                if case:
                    context["case_title"] = case.get("title", "Unknown")
                    context["case_context"] = case.get("context_summary", "")
            except Exception as e:
                logger.warning(f"Could not load case context: {e}")

        # Classify intent
        intent, entities, confidence = classify_intent(
            message,
            context,
            _anthropic_client
        )

        # Route to action handler
        router = CypherActionRouter(
            db_path=str(Config.DB_PATH),
            entity_registry=entity_registry,
            insight_store=insight_store,
            case_store=case_store
        )

        result = router.execute(intent, entities, context)

        # Format response in Cypher voice
        result = format_cypher_response(
            intent,
            result,
            context,
            _anthropic_client
        )

        # Add metadata
        processing_time_ms = int((time.time() - start_time) * 1000)
        result["metadata"] = {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "processing_time_ms": processing_time_ms,
        }

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Cypher message failed: {e}", exc_info=True)
        return jsonify({
            "reply": "Communication error. System malfunction logged.",
            "actions": [],
            "ui_updates": {},
            "suggestions": [],
            "metadata": {"error": str(e)}
        }), 500


@app.route("/api/extraction/status/<case_id>", methods=["GET"])
def extraction_status(case_id: str):
    """
    Get current extraction/processing status for a case.
    Used by Cypher for real-time progress updates.

    Returns:
        - status: "idle" | "processing" | "complete" | "error"
        - current: Current document number (if processing)
        - total: Total documents (if processing)
        - current_doc: Current document name (if processing)
        - insights_extracted: Count of insights
        - entities_identified: Count of entities
        - recent_event: Most recent processing event
    """
    try:
        import sqlite3
        conn = sqlite3.connect(str(Config.DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check processing queue for this case
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM processing_queue
            WHERE case_id = ?
            GROUP BY status
        """, (case_id,))

        queue_status = {row["status"]: row["count"] for row in cursor.fetchall()}

        pending = queue_status.get("pending", 0)
        processing = queue_status.get("processing", 0)
        completed = queue_status.get("completed", 0)
        failed = queue_status.get("failed", 0)

        total = pending + processing + completed + failed

        # Determine overall status
        if processing > 0:
            status = "processing"
        elif pending > 0:
            status = "pending"
        elif failed > 0 and completed == 0:
            status = "error"
        elif total > 0:
            status = "complete"
        else:
            status = "idle"

        # Get current processing item
        current_doc = None
        if status == "processing":
            cursor.execute("""
                SELECT source_name FROM processing_queue
                WHERE case_id = ? AND status = 'processing'
                LIMIT 1
            """, (case_id,))
            row = cursor.fetchone()
            if row:
                current_doc = row["source_name"]

        # Get insight/entity counts for this case
        cursor.execute("""
            SELECT COUNT(*) FROM insights WHERE case_id = ?
        """, (case_id,))
        insights_count = cursor.fetchone()[0]

        # Entity count is trickier - we'd need to join through documents
        # For now, get total unconfirmed entities as a proxy
        cursor.execute("""
            SELECT COUNT(*) FROM entity_registry WHERE confirmed = 0
        """)
        entities_count = cursor.fetchone()[0]

        conn.close()

        return api_response({
            "case_id": case_id,
            "status": status,
            "current": completed + 1 if status == "processing" else completed,
            "total": total,
            "current_doc": current_doc,
            "insights_extracted": insights_count,
            "entities_identified": entities_count,
            "queue_breakdown": queue_status,
        })

    except Exception as e:
        logger.error(f"Extraction status failed: {e}")
        return api_response(error=str(e), status=500)



@app.route("/api/extraction/status", methods=["GET"])
def extraction_status_global():
    """Get global extraction/processing status across all cases."""
    try:
        import sqlite3
        conn = sqlite3.connect(str(Config.DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM processing_queue
            GROUP BY status
        """)
        queue_status = {row["status"]: row["count"] for row in cursor.fetchall()}

        pending = queue_status.get("pending", 0)
        processing = queue_status.get("processing", 0)
        completed = queue_status.get("completed", 0)
        failed = queue_status.get("failed", 0)
        total = pending + processing + completed + failed

        if processing > 0:
            status = "processing"
        elif pending > 0:
            status = "pending"
        elif total > 0:
            status = "complete"
        else:
            status = "idle"

        current_doc = None
        active_case_id = None
        if status in ("processing", "pending"):
            cursor.execute("""
                SELECT source_name, case_id FROM processing_queue
                WHERE status IN ('processing', 'pending')
                ORDER BY status DESC, queued_at ASC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                current_doc = row["source_name"]
                active_case_id = row["case_id"]

        cursor.execute("""
            SELECT DISTINCT pq.case_id, c.title
            FROM processing_queue pq
            LEFT JOIN cases c ON c.id = pq.case_id
            WHERE pq.status IN ('processing', 'pending')
        """)
        active_cases = [
            {"case_id": row["case_id"], "title": row["title"] or "Untitled"}
            for row in cursor.fetchall() if row["case_id"]
        ]

        conn.close()

        return api_response({
            "status": status,
            "current": completed,
            "total": total,
            "pending": pending,
            "processing": processing,
            "current_doc": current_doc,
            "active_case_id": active_case_id,
            "active_cases": active_cases,
        })

    except Exception as e:
        logger.error(f"Global extraction status failed: {e}")
        return api_response(error=str(e), status=500)


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

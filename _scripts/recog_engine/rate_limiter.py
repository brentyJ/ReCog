"""
ReCog - Rate Limiting v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Rate limits API endpoints to prevent cost overruns and abuse.

Default: In-memory storage (single instance)
Optional: Redis backend for distributed deployments
"""

import logging
import os
from functools import wraps
from typing import Optional, Callable, Any

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Rate limit defaults (per minute unless specified)
DEFAULT_LIMIT = "60 per minute"  # General endpoints
EXPENSIVE_LIMIT = "10 per minute"  # LLM operations (extract, synth)
UPLOAD_LIMIT = "20 per minute"  # File uploads
HEALTH_LIMIT = "120 per minute"  # Health checks (more permissive)

# Environment variable overrides
RATE_LIMIT_STORAGE = os.environ.get("RECOG_RATE_LIMIT_STORAGE", "memory://")
RATE_LIMIT_DEFAULT = os.environ.get("RECOG_RATE_LIMIT_DEFAULT", DEFAULT_LIMIT)
RATE_LIMIT_EXPENSIVE = os.environ.get("RECOG_RATE_LIMIT_EXPENSIVE", EXPENSIVE_LIMIT)
RATE_LIMIT_UPLOAD = os.environ.get("RECOG_RATE_LIMIT_UPLOAD", UPLOAD_LIMIT)
RATE_LIMIT_ENABLED = os.environ.get("RECOG_RATE_LIMIT_ENABLED", "true").lower() == "true"


# =============================================================================
# KEY FUNCTIONS
# =============================================================================

def get_rate_limit_key() -> str:
    """
    Get the rate limit key for the current request.

    Uses X-Forwarded-For header if behind proxy, otherwise remote address.
    Can be extended to use user ID for authenticated requests.
    """
    # Check for user-provided key (for testing or per-user limits)
    user_key = request.headers.get("X-Rate-Limit-Key")
    if user_key:
        return f"user:{user_key}"

    # Use IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take first IP in the chain (original client)
        return forwarded.split(",")[0].strip()

    return get_remote_address()


# =============================================================================
# LIMITER INSTANCE
# =============================================================================

# Global limiter instance (initialized by init_rate_limiter)
_limiter: Optional[Limiter] = None


def init_rate_limiter(app: Flask) -> Optional[Limiter]:
    """
    Initialize rate limiter for the Flask app.

    Args:
        app: Flask application instance

    Returns:
        Limiter instance or None if disabled
    """
    global _limiter

    if not RATE_LIMIT_ENABLED:
        logger.info("Rate limiting is disabled (RECOG_RATE_LIMIT_ENABLED=false)")
        return None

    # Configure limiter
    _limiter = Limiter(
        key_func=get_rate_limit_key,
        app=app,
        default_limits=[RATE_LIMIT_DEFAULT],
        storage_uri=RATE_LIMIT_STORAGE,
        strategy="fixed-window",  # Simple and predictable
        headers_enabled=True,  # Add X-RateLimit-* headers
    )

    # Register custom error handler for 429
    @app.errorhandler(429)
    def ratelimit_handler(e):
        """Return JSON response for rate limit exceeded."""
        retry_after = e.description.split("retry after ")[1].split(" ")[0] if "retry after" in str(e.description) else "60"

        logger.warning(
            f"Rate limit exceeded for {get_rate_limit_key()}: {e.description}",
            extra={"key": get_rate_limit_key(), "description": str(e.description)}
        )

        response = jsonify({
            "success": False,
            "error": f"Too many requests. Please wait {retry_after} seconds and try again.",
            "data": {
                "error_type": "RateLimitError",
                "retry_after_seconds": int(retry_after) if retry_after.isdigit() else 60,
            }
        })
        response.status_code = 429
        response.headers["Retry-After"] = retry_after
        return response

    logger.info(
        f"Rate limiter initialized: storage={RATE_LIMIT_STORAGE}, "
        f"default={RATE_LIMIT_DEFAULT}, expensive={RATE_LIMIT_EXPENSIVE}"
    )

    return _limiter


def get_limiter() -> Optional[Limiter]:
    """Get the global limiter instance."""
    return _limiter


# =============================================================================
# DECORATORS
# =============================================================================

def rate_limit_expensive(f: Callable) -> Callable:
    """
    Apply expensive operation rate limit (10/min default).

    Use for LLM operations: extraction, synthesis, validation.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)

    # Only apply if limiter is initialized
    if _limiter is not None:
        return _limiter.limit(RATE_LIMIT_EXPENSIVE)(decorated_function)
    return decorated_function


def rate_limit_upload(f: Callable) -> Callable:
    """
    Apply upload rate limit (20/min default).

    Use for file upload endpoints.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)

    if _limiter is not None:
        return _limiter.limit(RATE_LIMIT_UPLOAD)(decorated_function)
    return decorated_function


def rate_limit_health(f: Callable) -> Callable:
    """
    Apply health check rate limit (120/min default).

    More permissive for monitoring systems.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)

    if _limiter is not None:
        return _limiter.limit(HEALTH_LIMIT)(decorated_function)
    return decorated_function


def exempt_from_rate_limit(f: Callable) -> Callable:
    """
    Exempt an endpoint from rate limiting.

    Use sparingly for internal endpoints.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)

    if _limiter is not None:
        return _limiter.exempt(decorated_function)
    return decorated_function


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_rate_limit_status(key: Optional[str] = None) -> dict:
    """
    Get current rate limit status for a key.

    Args:
        key: Rate limit key (defaults to current request key if in request context)

    Returns:
        Dict with limit info
    """
    if _limiter is None:
        return {"enabled": False}

    # Try to get key from request context if not provided
    if key is None:
        try:
            key = get_rate_limit_key()
        except RuntimeError:
            # Outside request context
            key = "N/A (no request context)"

    return {
        "enabled": True,
        "key": key,
        "storage": RATE_LIMIT_STORAGE,
        "limits": {
            "default": RATE_LIMIT_DEFAULT,
            "expensive": RATE_LIMIT_EXPENSIVE,
            "upload": RATE_LIMIT_UPLOAD,
        }
    }


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Initialization
    "init_rate_limiter",
    "get_limiter",
    # Decorators
    "rate_limit_expensive",
    "rate_limit_upload",
    "rate_limit_health",
    "exempt_from_rate_limit",
    # Utilities
    "get_rate_limit_key",
    "get_rate_limit_status",
    # Constants
    "DEFAULT_LIMIT",
    "EXPENSIVE_LIMIT",
    "UPLOAD_LIMIT",
    "RATE_LIMIT_ENABLED",
]

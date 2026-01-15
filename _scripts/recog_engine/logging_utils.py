"""
ReCog Structured Logging - Production-grade logging utilities

Provides consistent logging with:
- Request ID tracking
- JSON structured output (optional)
- Level-based filtering
- Performance timing
- Log rotation for production
- LLM call tracking with cost metrics
- Extraction pipeline monitoring

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io
"""

import logging
import logging.handlers
import sys
import time
import json
import re
from datetime import datetime, timezone
from functools import wraps
from typing import Optional, Any, Dict, Callable, List, Tuple
from uuid import uuid4
from contextvars import ContextVar
from pathlib import Path

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
case_id_var: ContextVar[str] = ContextVar("case_id", default="")
session_id_var: ContextVar[str] = ContextVar("session_id", default="")


# =============================================================================
# SECRETS SANITIZATION
# =============================================================================

class SecretsSanitizer(logging.Filter):
    """
    Log filter that redacts sensitive information from log messages.

    Catches API keys, passwords, tokens, and other secrets that may
    accidentally appear in log output (e.g., in error messages).
    """

    # Patterns to detect and redact (pattern, replacement)
    PATTERNS: List[Tuple[re.Pattern, str]] = [
        # OpenAI API keys
        (re.compile(r'sk-[a-zA-Z0-9]{20,}'), '[OPENAI_KEY]'),
        # Anthropic API keys
        (re.compile(r'sk-ant-[a-zA-Z0-9\-]{20,}'), '[ANTHROPIC_KEY]'),
        # Generic API keys (various formats)
        (re.compile(r'api[_-]?key\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{20,})["\']?', re.IGNORECASE),
         r'api_key=[REDACTED]'),
        # Bearer tokens
        (re.compile(r'Bearer\s+[a-zA-Z0-9\-_\.]{20,}', re.IGNORECASE), 'Bearer [REDACTED]'),
        # Password fields
        (re.compile(r'(password|passwd|pwd)\s*[:=]\s*["\']?[^\s"\']+["\']?', re.IGNORECASE),
         r'\1=[REDACTED]'),
        # Secret fields
        (re.compile(r'(secret|token|credential)\s*[:=]\s*["\']?[^\s"\']+["\']?', re.IGNORECASE),
         r'\1=[REDACTED]'),
        # Connection strings with passwords
        (re.compile(r'(://[^:]+:)[^@]+(@)', re.IGNORECASE), r'\1[REDACTED]\2'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and sanitize log record messages.

        Returns True to allow the record through (after sanitization).
        """
        # Sanitize the message
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)

        # Also sanitize args if present (for % formatting)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize(v) if isinstance(v, str) else v
                              for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._sanitize(a) if isinstance(a, str) else a
                                   for a in record.args)

        # Sanitize extra fields that might contain secrets
        if hasattr(record, 'error_context') and record.error_context:
            record.error_context = self._sanitize(str(record.error_context))

        return True  # Always allow record through after sanitization

    def _sanitize(self, text: str) -> str:
        """Apply all sanitization patterns to text."""
        if not text:
            return text
        for pattern, replacement in self.PATTERNS:
            text = pattern.sub(replacement, text)
        return text


# Global sanitizer instance
_secrets_sanitizer = SecretsSanitizer()


# =============================================================================
# LOG ROTATION CONFIGURATION
# =============================================================================

class LogRotationConfig:
    """Configuration for log file rotation."""

    def __init__(
        self,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB default
        backup_count: int = 5,
        when: str = "midnight",  # For time-based rotation
        interval: int = 1,
    ):
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.when = when
        self.interval = interval


DEFAULT_ROTATION_CONFIG = LogRotationConfig()


class StructuredFormatter(logging.Formatter):
    """
    Formatter that outputs structured log entries.
    
    In JSON mode, outputs machine-readable JSON.
    In text mode, outputs human-readable logs with context.
    """
    
    def __init__(self, json_output: bool = False):
        super().__init__()
        self.json_output = json_output
    
    def format(self, record: logging.LogRecord) -> str:
        request_id = request_id_var.get()
        case_id = case_id_var.get()
        session_id = session_id_var.get()

        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context IDs if present
        if request_id:
            log_data["request_id"] = request_id
        if case_id:
            log_data["case_id"] = case_id
        if session_id:
            log_data["session_id"] = session_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        extra_fields = (
            # Request/response fields
            "duration_ms", "endpoint", "status_code", "method", "path", "user_agent",
            # Entity/insight fields
            "entity_id", "insight_id",
            # LLM tracking fields
            "provider", "model", "tokens_used", "prompt_tokens", "completion_tokens",
            "cost_cents", "llm_duration_ms",
            # Extraction pipeline fields
            "stage", "entities_found", "insights_found", "documents_processed",
            # Error context
            "error_type", "error_context",
        )
        for key in extra_fields:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)
        
        if self.json_output:
            return json.dumps(log_data)
        else:
            # Human readable format
            parts = [
                f"[{log_data['timestamp']}]",
                f"[{record.levelname:8}]",
            ]

            # Add context IDs (abbreviated)
            context_parts = []
            if request_id:
                context_parts.append(f"req:{request_id[:8]}")
            if case_id:
                context_parts.append(f"case:{case_id[:8]}")
            if session_id:
                context_parts.append(f"sess:{session_id[:8]}")

            if context_parts:
                parts.append(f"[{'/'.join(context_parts)}]")

            parts.append(record.getMessage())

            # Add extra context for key metrics
            extras = []
            for key in ("duration_ms", "endpoint", "status_code", "tokens_used", "cost_cents"):
                if hasattr(record, key):
                    extras.append(f"{key}={getattr(record, key)}")

            if extras:
                parts.append(f"({', '.join(extras)})")

            result = " ".join(parts)

            if record.exc_info:
                result += "\n" + self.formatException(record.exc_info)

            return result


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[str] = None,
    rotation_config: Optional[LogRotationConfig] = None,
    use_time_rotation: bool = False,
) -> logging.Logger:
    """
    Configure application logging with optional rotation.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON logs (for production)
        log_file: Optional file path for log output
        rotation_config: Optional rotation configuration (uses defaults if None)
        use_time_rotation: If True, use time-based rotation instead of size-based

    Returns:
        Root logger
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    # Attach secrets sanitizer to filter sensitive data from all logs
    root_logger.addFilter(_secrets_sanitizer)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter(json_output=json_output))
    root_logger.addHandler(console_handler)

    # File handler with rotation (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        config = rotation_config or DEFAULT_ROTATION_CONFIG

        if use_time_rotation:
            # Time-based rotation (e.g., daily)
            file_handler = logging.handlers.TimedRotatingFileHandler(
                log_file,
                when=config.when,
                interval=config.interval,
                backupCount=config.backup_count,
            )
        else:
            # Size-based rotation
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
            )

        file_handler.setFormatter(StructuredFormatter(json_output=True))  # Always JSON to file
        root_logger.addHandler(file_handler)

    # Reduce noise from libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)


def set_request_id(request_id: Optional[str] = None) -> str:
    """Set or generate request ID for current context."""
    if request_id is None:
        request_id = str(uuid4())
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> str:
    """Get current request ID."""
    return request_id_var.get()


def set_case_id(case_id: Optional[str] = None) -> str:
    """Set case ID for current context."""
    if case_id is None:
        case_id = ""
    case_id_var.set(case_id)
    return case_id


def get_case_id() -> str:
    """Get current case ID."""
    return case_id_var.get()


def set_session_id(session_id: Optional[str] = None) -> str:
    """Set session ID for current context."""
    if session_id is None:
        session_id = str(uuid4())
    session_id_var.set(session_id)
    return session_id


def get_session_id() -> str:
    """Get current session ID."""
    return session_id_var.get()


def log_request(logger: logging.Logger):
    """
    Decorator to log request start/end with timing.
    
    Usage:
        @log_request(logger)
        def my_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import request
            
            # Generate request ID
            request_id = set_request_id(request.headers.get("X-Request-ID"))
            
            start_time = time.time()
            
            logger.info(
                f"Request started: {request.method} {request.path}",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "endpoint": f.__name__,
                    "user_agent": request.headers.get("User-Agent", "")[:100],
                }
            )
            
            try:
                result = f(*args, **kwargs)
                
                # Extract status code from result
                if isinstance(result, tuple):
                    status_code = result[1] if len(result) > 1 else 200
                else:
                    status_code = 200
                
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info(
                    f"Request completed: {request.method} {request.path}",
                    extra={
                        "method": request.method,
                        "path": request.path,
                        "endpoint": f.__name__,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.exception(
                    f"Request failed: {request.method} {request.path}",
                    extra={
                        "method": request.method,
                        "path": request.path,
                        "endpoint": f.__name__,
                        "status_code": 500,
                        "duration_ms": round(duration_ms, 2),
                    }
                )
                raise
        
        return wrapper
    return decorator


class Timer:
    """
    Context manager for timing code blocks.
    
    Usage:
        with Timer(logger, "database query"):
            db.execute(...)
    """
    
    def __init__(self, logger: logging.Logger, operation: str, level: int = logging.DEBUG):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type:
            self.logger.log(
                logging.ERROR,
                f"Operation failed: {self.operation}",
                extra={"duration_ms": round(self.duration_ms, 2)}
            )
        else:
            self.logger.log(
                self.level,
                f"Operation completed: {self.operation}",
                extra={"duration_ms": round(self.duration_ms, 2)}
            )
        
        return False  # Don't suppress exceptions


# =============================================================================
# PRODUCTION LOGGING FUNCTIONS
# =============================================================================

def log_api_call(
    logger: logging.Logger,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    error: Optional[str] = None,
) -> None:
    """
    Log an API call with standardized format.

    Args:
        logger: Logger instance to use
        endpoint: API endpoint path
        method: HTTP method (GET, POST, etc.)
        status_code: HTTP response status code
        duration_ms: Request duration in milliseconds
        error: Optional error message if request failed
    """
    level = logging.INFO if status_code < 400 else logging.WARNING if status_code < 500 else logging.ERROR

    message = f"API {method} {endpoint}"
    if error:
        message += f" - {error}"

    logger.log(
        level,
        message,
        extra={
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "error_context": error,
        }
    )


def log_llm_call(
    logger: logging.Logger,
    provider: str,
    model: str,
    tokens_used: int,
    cost_cents: float,
    case_id: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    duration_ms: Optional[float] = None,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """
    Log an LLM API call with cost and token metrics.

    Args:
        logger: Logger instance to use
        provider: LLM provider (e.g., "openai", "anthropic")
        model: Model name/ID
        tokens_used: Total tokens used
        cost_cents: Estimated cost in cents
        case_id: Optional case ID for context
        prompt_tokens: Optional prompt token count
        completion_tokens: Optional completion token count
        duration_ms: Optional call duration in milliseconds
        success: Whether the call succeeded
        error: Optional error message if call failed
    """
    level = logging.INFO if success else logging.ERROR

    message = f"LLM call to {provider}/{model}"
    if not success and error:
        message += f" failed: {error}"

    extra = {
        "provider": provider,
        "model": model,
        "tokens_used": tokens_used,
        "cost_cents": round(cost_cents, 4),
    }

    if prompt_tokens is not None:
        extra["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        extra["completion_tokens"] = completion_tokens
    if duration_ms is not None:
        extra["llm_duration_ms"] = round(duration_ms, 2)
    if error:
        extra["error_context"] = error

    # Set case context if provided
    if case_id:
        set_case_id(case_id)

    logger.log(level, message, extra=extra)


def log_extraction_pipeline(
    logger: logging.Logger,
    session_id: str,
    stage: str,
    duration_ms: float,
    entities_found: int = 0,
    insights_found: int = 0,
    documents_processed: int = 0,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """
    Log extraction pipeline progress and metrics.

    Args:
        logger: Logger instance to use
        session_id: Preflight session ID
        stage: Pipeline stage (e.g., "tier0", "tier1", "tier2", "complete")
        duration_ms: Stage duration in milliseconds
        entities_found: Number of entities extracted
        insights_found: Number of insights extracted
        documents_processed: Number of documents processed
        success: Whether the stage succeeded
        error: Optional error message if stage failed
    """
    level = logging.INFO if success else logging.ERROR

    message = f"Pipeline stage '{stage}'"
    if not success and error:
        message += f" failed: {error}"
    else:
        message += f" completed"

    # Set session context
    set_session_id(session_id)

    logger.log(
        level,
        message,
        extra={
            "stage": stage,
            "duration_ms": round(duration_ms, 2),
            "entities_found": entities_found,
            "insights_found": insights_found,
            "documents_processed": documents_processed,
            "error_context": error if error else None,
        }
    )


def timed(
    logger: logging.Logger,
    operation: str,
    level: int = logging.DEBUG,
) -> Callable:
    """
    Decorator for timing function execution.

    Usage:
        @timed(logger, "database query")
        def fetch_records():
            ...

    Args:
        logger: Logger instance to use
        operation: Description of the operation
        level: Log level for timing output
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = f(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.log(
                    level,
                    f"{operation} completed",
                    extra={"duration_ms": round(duration_ms, 2)}
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.log(
                    logging.ERROR,
                    f"{operation} failed: {type(e).__name__}",
                    extra={
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                        "error_context": str(e),
                    }
                )
                raise
        return wrapper
    return decorator


__all__ = [
    # Setup and config
    "setup_logging",
    "get_logger",
    "LogRotationConfig",
    "DEFAULT_ROTATION_CONFIG",
    # Context management
    "set_request_id",
    "get_request_id",
    "set_case_id",
    "get_case_id",
    "set_session_id",
    "get_session_id",
    # Decorators
    "log_request",
    "timed",
    # Classes
    "Timer",
    "StructuredFormatter",
    "SecretsSanitizer",
    # Production logging functions
    "log_api_call",
    "log_llm_call",
    "log_extraction_pipeline",
]

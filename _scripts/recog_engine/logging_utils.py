"""
ReCog Structured Logging

Provides consistent logging with:
- Request ID tracking
- JSON structured output (optional)
- Level-based filtering
- Performance timing

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import logging
import sys
import time
import json
from datetime import datetime
from functools import wraps
from typing import Optional, Any, Dict
from uuid import uuid4
from contextvars import ContextVar

# Context variable for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


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
        
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if request_id:
            log_data["request_id"] = request_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        for key in ("duration_ms", "endpoint", "status_code", "method", "path",
                    "session_id", "entity_id", "insight_id", "user_agent"):
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
            
            if request_id:
                parts.append(f"[{request_id[:8]}]")
            
            parts.append(record.getMessage())
            
            # Add extra context
            extras = []
            for key in ("duration_ms", "endpoint", "status_code"):
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
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON logs (for production)
        log_file: Optional file path for log output
    
    Returns:
        Root logger
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter(json_output=json_output))
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
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


__all__ = [
    "setup_logging",
    "get_logger",
    "set_request_id",
    "get_request_id",
    "log_request",
    "Timer",
    "StructuredFormatter",
]

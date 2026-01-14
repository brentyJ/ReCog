"""
ReCog - Config Validation v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Validates configuration at startup to fail fast with helpful messages.
Better to crash on startup than fail mysteriously in production.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION SCHEMA
# =============================================================================

@dataclass
class ConfigCheck:
    """A single configuration check."""
    name: str
    env_var: str
    required: bool = False
    pattern: Optional[str] = None  # Regex pattern for validation
    min_length: Optional[int] = None
    description: str = ""
    default: Optional[str] = None


@dataclass
class ConfigValidationResult:
    """Result of configuration validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    config_values: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# VALIDATION SCHEMA
# =============================================================================

# Core configuration checks
CONFIG_SCHEMA = [
    # LLM Providers (at least one should be configured for full functionality)
    ConfigCheck(
        name="OpenAI API Key",
        env_var="RECOG_OPENAI_API_KEY",
        required=False,  # Not strictly required if Anthropic is configured
        pattern=r"^sk-[a-zA-Z0-9\-_]{20,}$",
        min_length=20,
        description="OpenAI API key for GPT models (starts with sk-)",
    ),
    ConfigCheck(
        name="Anthropic API Key",
        env_var="RECOG_ANTHROPIC_API_KEY",
        required=False,  # Not strictly required if OpenAI is configured
        pattern=r"^sk-ant-[a-zA-Z0-9\-_]{20,}$",
        min_length=20,
        description="Anthropic API key for Claude models (starts with sk-ant-)",
    ),

    # Data paths
    ConfigCheck(
        name="Data Directory",
        env_var="RECOG_DATA_DIR",
        required=False,
        description="Directory for data storage (default: ./_data)",
        default="./_data",
    ),

    # Server config
    ConfigCheck(
        name="Server Port",
        env_var="RECOG_PORT",
        required=False,
        pattern=r"^\d{1,5}$",
        description="Server port (default: 5100)",
        default="5100",
    ),

    # File upload limits
    ConfigCheck(
        name="Max File Size (MB)",
        env_var="RECOG_MAX_FILE_SIZE_MB",
        required=False,
        pattern=r"^\d+(\.\d+)?$",
        description="Maximum file upload size in MB (default: 10)",
        default="10",
    ),

    # Logging
    ConfigCheck(
        name="Log Level",
        env_var="RECOG_LOG_LEVEL",
        required=False,
        pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level (default: INFO)",
        default="INFO",
    ),

    # Cache
    ConfigCheck(
        name="Cache Enabled",
        env_var="RECOG_CACHE_ENABLED",
        required=False,
        pattern=r"^(true|false)$",
        description="Enable response caching (default: true)",
        default="true",
    ),
    ConfigCheck(
        name="Cache TTL Hours",
        env_var="RECOG_CACHE_TTL_HOURS",
        required=False,
        pattern=r"^\d+$",
        description="Cache TTL in hours (default: 24)",
        default="24",
    ),

    # Rate limiting
    ConfigCheck(
        name="Rate Limit Enabled",
        env_var="RECOG_RATE_LIMIT_ENABLED",
        required=False,
        pattern=r"^(true|false)$",
        description="Enable rate limiting (default: true)",
        default="true",
    ),
]


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_config(schema: List[ConfigCheck] = None) -> ConfigValidationResult:
    """
    Validate configuration against schema.

    Args:
        schema: List of ConfigCheck objects (defaults to CONFIG_SCHEMA)

    Returns:
        ConfigValidationResult with errors and warnings
    """
    if schema is None:
        schema = CONFIG_SCHEMA

    result = ConfigValidationResult(valid=True)

    for check in schema:
        value = os.environ.get(check.env_var)

        # Store config value (use default if not set)
        result.config_values[check.env_var] = value or check.default

        # Check required
        if check.required and not value:
            result.errors.append(
                f"Missing required config: {check.name} ({check.env_var})\n"
                f"  Description: {check.description}"
            )
            result.valid = False
            continue

        # Skip further validation if not set and not required
        if not value:
            continue

        # Check minimum length
        if check.min_length and len(value) < check.min_length:
            result.errors.append(
                f"Invalid {check.name}: value too short (min {check.min_length} chars)\n"
                f"  Environment variable: {check.env_var}"
            )
            result.valid = False
            continue

        # Check pattern
        if check.pattern and not re.match(check.pattern, value, re.IGNORECASE):
            result.errors.append(
                f"Invalid {check.name}: value doesn't match expected format\n"
                f"  Environment variable: {check.env_var}\n"
                f"  Expected pattern: {check.pattern}\n"
                f"  Description: {check.description}"
            )
            result.valid = False

    # Special validation: at least one LLM provider should be configured
    openai_key = os.environ.get("RECOG_OPENAI_API_KEY")
    anthropic_key = os.environ.get("RECOG_ANTHROPIC_API_KEY")

    if not openai_key and not anthropic_key:
        result.warnings.append(
            "No LLM provider configured!\n"
            "  Set RECOG_OPENAI_API_KEY or RECOG_ANTHROPIC_API_KEY for extraction features.\n"
            "  Tier 0 signal extraction will still work without LLM."
        )

    # Validate data directory is writable
    data_dir = Path(os.environ.get("RECOG_DATA_DIR", "./_data"))
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        test_file = data_dir / ".config_test"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        result.errors.append(
            f"Data directory not writable: {data_dir}\n"
            f"  Error: {e}\n"
            f"  Set RECOG_DATA_DIR to a writable directory."
        )
        result.valid = False

    return result


def validate_on_startup(
    strict: bool = False,
    exit_on_error: bool = True,
) -> ConfigValidationResult:
    """
    Validate configuration on server startup.

    Args:
        strict: If True, treat warnings as errors
        exit_on_error: If True, exit process on validation failure

    Returns:
        ConfigValidationResult
    """
    result = validate_config()

    # Print banner
    print("\n" + "=" * 60)
    print("ReCog Configuration Validation")
    print("=" * 60)

    # Print errors
    if result.errors:
        print("\nERRORS:")
        for i, error in enumerate(result.errors, 1):
            print(f"\n  [{i}] {error}")

    # Print warnings
    if result.warnings:
        print("\nWARNINGS:")
        for i, warning in enumerate(result.warnings, 1):
            print(f"\n  [{i}] {warning}")

    # Determine final status
    if strict and result.warnings:
        result.valid = False
        print("\n  (Strict mode: warnings treated as errors)")

    # Print summary
    if result.valid:
        print("\nConfiguration: OK")
        if result.warnings:
            print(f"  ({len(result.warnings)} warning(s) - non-critical)")
    else:
        print(f"\nConfiguration: FAILED ({len(result.errors)} error(s))")

    print("=" * 60 + "\n")

    # Exit if invalid and exit_on_error is True
    if not result.valid and exit_on_error:
        print("Server cannot start with invalid configuration.")
        print("Please fix the errors above and restart.\n")
        raise SystemExit(1)

    return result


def get_config_summary() -> Dict[str, Any]:
    """
    Get a summary of current configuration.

    Returns:
        Dict with configuration values (sensitive values masked)
    """
    summary = {}

    for check in CONFIG_SCHEMA:
        value = os.environ.get(check.env_var)

        # Mask sensitive values
        if value and "KEY" in check.env_var:
            if len(value) > 8:
                masked = value[:4] + "*" * (len(value) - 8) + value[-4:]
            else:
                masked = "*" * len(value)
            summary[check.env_var] = masked
        else:
            summary[check.env_var] = value or f"(default: {check.default})"

    return summary


def print_config_help():
    """Print help text for all configuration options."""
    print("\n" + "=" * 60)
    print("ReCog Configuration Options")
    print("=" * 60)

    for check in CONFIG_SCHEMA:
        required = " [REQUIRED]" if check.required else ""
        default = f" (default: {check.default})" if check.default else ""

        print(f"\n{check.env_var}{required}{default}")
        print(f"  {check.description}")
        if check.pattern:
            print(f"  Format: {check.pattern}")

    print("\n" + "=" * 60 + "\n")


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "ConfigCheck",
    "ConfigValidationResult",
    "CONFIG_SCHEMA",
    "validate_config",
    "validate_on_startup",
    "get_config_summary",
    "print_config_help",
]

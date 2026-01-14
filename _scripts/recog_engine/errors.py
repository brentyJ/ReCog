# recog_engine/errors.py
"""
ReCog - Custom Exceptions v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

User-friendly error types for ReCog operations.
Each exception includes both a technical message (for logs) and
a user-friendly message (for API responses).
"""


class RecogError(Exception):
    """Base exception for ReCog errors."""

    def __init__(self, message: str, user_message: str = None, status_code: int = 500):
        super().__init__(message)
        self.user_message = user_message or message
        self.status_code = status_code


# =============================================================================
# FILE ERRORS
# =============================================================================

class FileError(RecogError):
    """File-related errors."""
    pass


class FileTooLargeError(FileError):
    """File exceeds size limit."""

    def __init__(self, size_mb: float, limit_mb: float):
        super().__init__(
            f"File size {size_mb:.1f}MB exceeds limit {limit_mb}MB",
            f"This file is too large ({size_mb:.1f}MB). Maximum size is {limit_mb}MB. "
            f"Try compressing it or splitting it into smaller documents.",
            413
        )
        self.size_mb = size_mb
        self.limit_mb = limit_mb


class EmptyFileError(FileError):
    """File is empty."""

    def __init__(self):
        super().__init__(
            "File is empty",
            "This file appears to be empty. Please check that you uploaded the correct file.",
            400
        )


class CorruptedFileError(FileError):
    """File is corrupted or unreadable."""

    def __init__(self, details: str = ""):
        detail_suffix = f" {details}" if details else ""
        super().__init__(
            f"File is corrupted: {details}",
            f"This file appears to be corrupted or in an unsupported format. "
            f"Try opening it in its native application to verify it's valid.{detail_suffix}",
            400
        )


class UnsupportedFileTypeError(FileError):
    """File type not supported."""

    def __init__(self, file_type: str, supported_types: list):
        types_str = ', '.join(supported_types[:5])
        if len(supported_types) > 5:
            types_str += ', ...'
        super().__init__(
            f"Unsupported file type: {file_type}",
            f"This file type ({file_type}) is not supported. "
            f"Supported types: {types_str}",
            415
        )
        self.file_type = file_type
        self.supported_types = supported_types


class NoExtractableTextError(FileError):
    """File has no extractable text content."""

    def __init__(self, file_type: str = "file"):
        super().__init__(
            f"No extractable text in {file_type}",
            f"This {file_type} doesn't contain extractable text. "
            f"It may be an image-only PDF or scanned document. "
            f"Try using OCR software first to extract the text.",
            400
        )


# =============================================================================
# LLM ERRORS
# =============================================================================

class LLMError(RecogError):
    """LLM provider errors."""
    pass


class LLMNotConfiguredError(LLMError):
    """No LLM providers are configured."""

    def __init__(self):
        super().__init__(
            "No LLM providers configured",
            "No AI provider is configured. Go to Settings to add your OpenAI or Anthropic API key.",
            503
        )


class LLMProviderError(LLMError):
    """LLM provider is unavailable."""

    def __init__(self, provider: str, original_error: str):
        super().__init__(
            f"LLM provider {provider} failed: {original_error}",
            f"The AI service ({provider}) is temporarily unavailable. "
            f"This usually resolves within a few minutes. Try again shortly.",
            503
        )
        self.provider = provider
        self.original_error = original_error


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    def __init__(self, timeout_seconds: int = 30):
        super().__init__(
            f"LLM request timed out after {timeout_seconds}s",
            "This document took too long to process. Try breaking it into "
            "smaller sections or simplifying the analysis request.",
            504
        )
        self.timeout_seconds = timeout_seconds


class LLMAuthError(LLMError):
    """LLM API key is invalid or expired."""

    def __init__(self, provider: str):
        super().__init__(
            f"Invalid API key for {provider}",
            f"Your {provider} API key is invalid or expired. "
            f"Please check your API key in Settings.",
            401
        )
        self.provider = provider


class LLMQuotaError(LLMError):
    """LLM quota/rate limit exceeded."""

    def __init__(self, provider: str, retry_after: int = None):
        retry_msg = f" Try again in {retry_after} seconds." if retry_after else ""
        super().__init__(
            f"Rate limit exceeded for {provider}",
            f"You've hit the rate limit for {provider}.{retry_msg} "
            f"If this persists, check your API usage limits.",
            429
        )
        self.provider = provider
        self.retry_after = retry_after


class AllProvidersFailedError(LLMError):
    """All configured LLM providers failed."""

    def __init__(self, errors: list):
        error_summary = "; ".join(errors[:3])
        if len(errors) > 3:
            error_summary += f" (+{len(errors) - 3} more)"
        super().__init__(
            f"All LLM providers failed: {error_summary}",
            "All AI providers are currently unavailable. This usually means:\n"
            "1. API keys are invalid or expired\n"
            "2. Rate limits exceeded on all providers\n"
            "3. Network connectivity issues\n\n"
            "Wait a few minutes and try again. If this persists, check your API keys in Settings.",
            503
        )
        self.errors = errors


# =============================================================================
# VALIDATION ERRORS
# =============================================================================

class ValidationError(RecogError):
    """Input validation failed."""

    def __init__(self, field: str, issue: str):
        super().__init__(
            f"Validation error: {field} - {issue}",
            f"Invalid input for '{field}': {issue}",
            400
        )
        self.field = field
        self.issue = issue


class MissingFieldError(ValidationError):
    """Required field is missing."""

    def __init__(self, field: str):
        super().__init__(
            field,
            f"'{field}' is required but was not provided."
        )


# =============================================================================
# RESOURCE ERRORS
# =============================================================================

class ResourceNotFoundError(RecogError):
    """Requested resource doesn't exist."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type} not found: {resource_id}",
            f"The requested {resource_type} could not be found. It may have been deleted.",
            404
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class RateLimitError(RecogError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            "Rate limit exceeded",
            f"Too many requests. Please wait {retry_after} seconds and try again.",
            429
        )
        self.retry_after = retry_after


class BudgetExceededError(RecogError):
    """Daily budget limit exceeded."""

    def __init__(self, spent: float, limit: float):
        super().__init__(
            f"Budget exceeded: ${spent:.2f} / ${limit:.2f}",
            f"Daily budget limit reached (${limit:.2f}). Usage resets at midnight UTC.",
            402  # Payment Required
        )
        self.spent = spent
        self.limit = limit


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Base
    "RecogError",
    # File
    "FileError",
    "FileTooLargeError",
    "EmptyFileError",
    "CorruptedFileError",
    "UnsupportedFileTypeError",
    "NoExtractableTextError",
    # LLM
    "LLMError",
    "LLMNotConfiguredError",
    "LLMProviderError",
    "LLMTimeoutError",
    "LLMAuthError",
    "LLMQuotaError",
    "AllProvidersFailedError",
    # Validation
    "ValidationError",
    "MissingFieldError",
    # Resources
    "ResourceNotFoundError",
    "RateLimitError",
    "BudgetExceededError",
]

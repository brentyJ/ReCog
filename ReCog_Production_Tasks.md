# ReCog Production Readiness: Priority Tasks

## Context
ReCog is a working Flask app for document intelligence. It already has:
- ✅ Provider factory (OpenAI + Anthropic)
- ✅ Role-based provider selection (extraction vs synthesis)
- ✅ Basic error handling
- ✅ Config management (.env files)
- ✅ Health check endpoint
- ✅ Database with SQLite

What's missing is the reliability layer that prevents it breaking in weird ways when colleagues use it.

---

## TOP 2 PRIORITY TASKS

### 1. LLM Provider Failover (CRITICAL)
**Why this is #1:** Right now when Claude or OpenAI has an outage, ReCog just fails. Users will think your tool is broken, not that the provider is down. With failover, it keeps working seamlessly.

**Current situation:** The provider factory creates individual providers, but there's no automatic retry/fallback logic. If create_provider("anthropic") fails, the whole request fails.

**What needs to happen:** Implement LiteLLM Router-style failover so if Claude times out or rate limits, it automatically tries OpenAI, then fails gracefully if both are down.

**Business impact:** Without this, every time a provider has issues (which happens regularly), users can't use ReCog. With it, they never notice.

---

### 2. User-Friendly Error Handling (CRITICAL)
**Why this is #2:** Currently when something breaks, users see generic errors or stack traces. They'll message you asking "what does this mean?" Good error messages = less support burden.

**Current situation:** There's some try/catch blocks but errors are either logged and returned as generic strings, or worse, leak stack traces. No validation of file uploads, no helpful messages.

**What needs to happen:** 
- Catch specific error types (FileTooBigError, LLMProviderError, etc.)
- Return user-friendly JSON responses with actionable messages
- Validate inputs before expensive operations
- Handle common failures gracefully (corrupted PDFs, empty files, etc.)

**Business impact:** Reduces your support burden from dozens of "it didn't work" messages to maybe a few.

---

## ALL OTHER TASKS (Prioritized)

### Week 1: Make It Reliable
**3. Cost Tracking**
- Track tokens and costs per request
- Log to SQLite table: user_id, feature, provider, tokens, cost, timestamp
- Simple CLI command to view costs: `python recog_cli.py cost-report --last-7-days`
- **Why:** Need visibility before costs spiral
- **Effort:** 1 day

**4. Input Validation**
- Check file sizes before upload (10MB limit)
- Validate file types with magic bytes, not just extensions
- Check for empty/corrupted files
- Validate document has extractable text
- **Why:** Prevents weird failures and wasted LLM tokens
- **Effort:** 4-6 hours

**5. Basic Logging**
- Structure logs properly (timestamp, level, message, context)
- Log every request: user, endpoint, params
- Log every LLM call: provider, model, tokens, latency
- Log errors with full context
- Use rotating file handler (10MB max, 5 backups)
- **Why:** When users say "it didn't work", you can actually debug it
- **Effort:** 2-3 hours

---

### Week 2: Control Costs
**6. Response Caching**
- Cache document analysis by content hash (24 hours)
- Cache entity extraction results (24 hours)  
- Use Flask-Caching with Redis backend (or filesystem fallback)
- **Why:** Same document analyzed twice = paying twice. 30-70% cost reduction typical
- **Effort:** 6-8 hours

**7. Rate Limiting**
- Limit API endpoints (10 req/min for expensive operations)
- Use Flask-Limiter with Redis backend
- Return HTTP 429 with Retry-After header
- **Why:** Prevents accidental cost overruns from hammering the API
- **Effort:** 3-4 hours

**8. Config Validation on Startup**
- Check required env vars exist (API keys)
- Validate values (not empty, correct format)
- Fail fast with helpful messages if misconfigured
- **Why:** Better to crash on startup with clear error than fail mysteriously later
- **Effort:** 1 hour

---

### Week 3: Polish
**9. Async Job Processing**
- Use Huey (simpler than Celery) for long-running tasks
- POST returns 202 Accepted + job_id immediately
- User polls /api/jobs/{id} for status
- **Why:** Document processing takes time, don't block HTTP connections
- **Effort:** 1 day

**10. Progress Indicators**
- Server-Sent Events (SSE) for real-time progress
- Emit events: extracting_text (10%), analyzing (40%), generating_insights (70%), complete (100%)
- **Why:** Users need to know it's working, not frozen
- **Effort:** 6-8 hours

**11. Better API Docs**
- Good README with curl examples
- Document common errors and fixes
- Show example requests/responses
- **Why:** Users can help themselves instead of asking you
- **Effort:** 2-3 hours

**12. Health Check Improvements**
- Check LLM providers are accessible (test API call)
- Check database is writable
- Check disk space
- Return 503 if unhealthy
- **Why:** External monitoring can catch issues before users notice
- **Effort:** 2 hours

---

### Post-Launch: Future Improvements
**13. Semantic Caching**
- Recognize similar queries and reuse results
- Use GPTCache library
- **Why:** "analyze this doc" and "extract insights from this doc" could share results
- **When:** After you have real usage patterns
- **Effort:** 2-3 days

**14. Batch Processing Endpoint**
- Accept multiple files in one request
- Process them all in parallel
- Return batch job_id
- **Why:** Some users want to analyze 50 documents
- **Effort:** 4-6 hours

**15. Export Formats**
- JSON (already have)
- CSV for entities
- Markdown for insights report
- **Why:** Users want to use insights elsewhere
- **Effort:** 2-3 hours per format

**16. Simple User Management**
- API key generation
- Per-user rate limits
- Usage tracking by user
- **Why:** If opening beyond colleagues, need to track who's using what
- **Effort:** 2 days

---

## IMPLEMENTATION SPECS FOR TOP 2

### TASK 1: LLM Provider Failover

**Objective:** Automatic failover between Claude and OpenAI with exponential backoff and graceful degradation.

**Files to modify:**
- `recog_engine/core/providers/factory.py` - add Router class
- `recog_engine/core/llm.py` - update LLMProvider interface if needed
- `server.py` - use Router instead of create_provider

**New file to create:**
- `recog_engine/core/providers/router.py` - main Router implementation

**Dependencies to add:**
```
tenacity==8.2.3  # For retry with exponential backoff
```

**Core logic:**
```python
# recog_engine/core/providers/router.py

import logging
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime, timedelta

from .base import LLMProvider, LLMResponse
from .factory import create_provider, get_available_providers

logger = logging.getLogger(__name__)


class ProviderRouter:
    """
    Routes LLM requests across multiple providers with automatic failover.
    
    Fallback chain:
    1. Primary provider (Claude Sonnet for quality)
    2. Secondary provider (GPT-4o-mini for cost)
    3. Graceful failure with user-friendly error
    
    Features:
    - Automatic retry with exponential backoff
    - Provider health tracking (circuit breaker)
    - Request logging for cost/performance analysis
    """
    
    def __init__(
        self,
        provider_preference: Optional[List[str]] = None,
        max_retries: int = 2,
        timeout: int = 30,
    ):
        """
        Initialize router with provider preference.
        
        Args:
            provider_preference: Ordered list of providers to try
                                Default: ["anthropic", "openai"]
            max_retries: Retry attempts per provider
            timeout: Request timeout in seconds
        """
        self.available_providers = get_available_providers()
        
        if not self.available_providers:
            raise ValueError("No LLM providers configured. Set API keys in .env")
        
        # Use preference or default to available providers
        if provider_preference:
            self.provider_chain = [
                p for p in provider_preference 
                if p in self.available_providers
            ]
        else:
            # Default: Anthropic first (quality), OpenAI second (cost)
            default_chain = ["anthropic", "openai"]
            self.provider_chain = [
                p for p in default_chain 
                if p in self.available_providers
            ]
        
        if not self.provider_chain:
            raise ValueError(
                f"No configured providers match preference. "
                f"Available: {self.available_providers}"
            )
        
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Circuit breaker: track provider failures
        self.provider_health: Dict[str, Dict[str, Any]] = {
            name: {
                "failures": 0,
                "last_failure": None,
                "cooldown_until": None,
            }
            for name in self.provider_chain
        }
        
        logger.info(f"Provider router initialized: {' -> '.join(self.provider_chain)}")
    
    def _is_provider_healthy(self, provider_name: str) -> bool:
        """Check if provider is healthy (not in cooldown)."""
        health = self.provider_health[provider_name]
        
        if health["cooldown_until"] is None:
            return True
        
        if datetime.now() > health["cooldown_until"]:
            # Cooldown expired, reset
            health["failures"] = 0
            health["cooldown_until"] = None
            return True
        
        return False
    
    def _mark_provider_failure(self, provider_name: str):
        """Record provider failure and trigger cooldown if threshold met."""
        health = self.provider_health[provider_name]
        health["failures"] += 1
        health["last_failure"] = datetime.now()
        
        # Circuit breaker: 3 failures = 5 minute cooldown
        if health["failures"] >= 3:
            health["cooldown_until"] = datetime.now() + timedelta(minutes=5)
            logger.warning(
                f"Provider {provider_name} in cooldown until "
                f"{health['cooldown_until'].isoformat()}"
            )
    
    def _mark_provider_success(self, provider_name: str):
        """Record provider success, reset failure counter."""
        health = self.provider_health[provider_name]
        health["failures"] = 0
        health["cooldown_until"] = None
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_provider(
        self,
        provider: LLMProvider,
        prompt: str,
        **kwargs
    ) -> LLMResponse:
        """Call provider with retry logic."""
        return provider.generate(prompt=prompt, **kwargs)
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response with automatic failover.
        
        Tries each provider in chain until one succeeds.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Max response tokens
            **kwargs: Additional provider-specific args
        
        Returns:
            LLMResponse from first successful provider
        
        Raises:
            RuntimeError: All providers failed
        """
        errors = []
        
        for provider_name in self.provider_chain:
            # Skip unhealthy providers
            if not self._is_provider_healthy(provider_name):
                logger.info(f"Skipping {provider_name} (in cooldown)")
                errors.append(f"{provider_name}: In cooldown")
                continue
            
            try:
                logger.info(f"Attempting provider: {provider_name}")
                provider = create_provider(provider_name)
                
                response = self._call_provider(
                    provider,
                    prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                if response.success:
                    self._mark_provider_success(provider_name)
                    logger.info(
                        f"✓ {provider_name} succeeded "
                        f"({response.usage.get('total_tokens', 0)} tokens)"
                    )
                    return response
                
                # Provider returned unsuccessful response
                logger.warning(f"{provider_name} returned error: {response.error}")
                errors.append(f"{provider_name}: {response.error}")
                self._mark_provider_failure(provider_name)
                
            except Exception as e:
                logger.error(f"{provider_name} failed: {e}")
                errors.append(f"{provider_name}: {str(e)}")
                self._mark_provider_failure(provider_name)
        
        # All providers failed
        error_summary = "; ".join(errors)
        raise RuntimeError(
            f"All LLM providers failed. Errors: {error_summary}\n\n"
            f"This usually means:\n"
            f"1. API keys are invalid/expired\n"
            f"2. Rate limits exceeded on all providers\n"
            f"3. Network connectivity issues\n\n"
            f"Wait a few minutes and try again. If persists, check API keys."
        )


# Update factory.py to expose Router
def create_router(
    provider_preference: Optional[List[str]] = None,
    max_retries: int = 2,
    timeout: int = 30,
) -> ProviderRouter:
    """
    Create a provider router for automatic failover.
    
    This is the recommended way to call LLMs in production.
    
    Example:
        router = create_router(["anthropic", "openai"])
        response = router.generate("Analyze this text...")
    """
    return ProviderRouter(provider_preference, max_retries, timeout)
```

**Update server.py usage:**
```python
# Old way (in server.py)
provider = create_provider(provider_name)
response = provider.generate(prompt=prompt, ...)

# New way
from recog_engine.core.providers import create_router

router = create_router(["anthropic", "openai"])
response = router.generate(prompt=prompt, ...)
```

**Testing:**
```python
# Test script: test_router.py
from recog_engine.core.providers import create_router

router = create_router()

# Should succeed with primary provider
response = router.generate("Say hello")
print(f"✓ Primary provider: {response.content}")

# Test failover by corrupting primary API key temporarily
# (manually or via test harness)
```

---

### TASK 2: User-Friendly Error Handling

**Objective:** Clear, actionable error messages that don't require you to debug for users.

**Files to modify:**
- `server.py` - add error handler decorators, custom exceptions
- Create: `recog_engine/errors.py` - custom exception types

**New exceptions file:**
```python
# recog_engine/errors.py

class RecogError(Exception):
    """Base exception for ReCog errors."""
    def __init__(self, message: str, user_message: str = None, status_code: int = 500):
        super().__init__(message)
        self.user_message = user_message or message
        self.status_code = status_code


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
        super().__init__(
            f"File is corrupted: {details}",
            f"This file appears to be corrupted or in an unsupported format. "
            f"Try opening it in its native application to verify it's valid. {details}",
            400
        )


class UnsupportedFileTypeError(FileError):
    """File type not supported."""
    def __init__(self, file_type: str, supported_types: list):
        super().__init__(
            f"Unsupported file type: {file_type}",
            f"This file type ({file_type}) is not supported. "
            f"Supported types: {', '.join(supported_types)}",
            415
        )


class LLMError(RecogError):
    """LLM provider errors."""
    pass


class LLMProviderError(LLMError):
    """LLM provider is unavailable."""
    def __init__(self, provider: str, original_error: str):
        super().__init__(
            f"LLM provider {provider} failed: {original_error}",
            "The AI service is temporarily unavailable. This usually resolves "
            "within a few minutes. Try again shortly.",
            503
        )


class LLMTimeoutError(LLMError):
    """LLM request timed out."""
    def __init__(self):
        super().__init__(
            "LLM request timed out",
            "This document took too long to process. Try breaking it into "
            "smaller sections or simplifying the analysis request.",
            504
        )


class RateLimitError(RecogError):
    """Rate limit exceeded."""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            "Rate limit exceeded",
            f"Too many requests. Please wait {retry_after} seconds and try again.",
            429
        )


class BudgetExceededError(RecogError):
    """Daily budget limit exceeded."""
    def __init__(self, spent: float, limit: float):
        super().__init__(
            f"Budget exceeded: ${spent:.2f} / ${limit:.2f}",
            f"Daily budget limit reached (${limit:.2f}). Usage resets at midnight UTC.",
            402  # Payment Required
        )


class ValidationError(RecogError):
    """Input validation failed."""
    def __init__(self, field: str, issue: str):
        super().__init__(
            f"Validation error: {field} - {issue}",
            f"Invalid input: {field}. {issue}",
            400
        )
```

**Update server.py with error handlers:**
```python
# server.py additions

from recog_engine.errors import (
    RecogError, FileTooLargeError, EmptyFileError, CorruptedFileError,
    UnsupportedFileTypeError, LLMProviderError, LLMTimeoutError,
    RateLimitError, BudgetExceededError, ValidationError
)


@app.errorhandler(RecogError)
def handle_recog_error(error: RecogError):
    """Handle all ReCog custom errors."""
    logger.error(f"ReCog error: {error}", exc_info=True)
    
    return api_response(
        error=error.user_message,
        data={"error_type": error.__class__.__name__},
        status=error.status_code
    )


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unexpected error: {error}", exc_info=True)
    
    # Don't leak internal details in production
    if app.debug:
        error_detail = str(error)
    else:
        error_detail = "An unexpected error occurred. The error has been logged."
    
    return api_response(
        error=error_detail,
        data={"error_type": "UnexpectedError"},
        status=500
    )


@app.errorhandler(404)
def handle_not_found(error):
    """Handle 404 errors."""
    return api_response(
        error="Endpoint not found. Check the API documentation at /api/info",
        status=404
    )


@app.errorhandler(405)
def handle_method_not_allowed(error):
    """Handle 405 errors."""
    return api_response(
        error=f"Method not allowed. This endpoint doesn't support {request.method}",
        status=405
    )


# Update file upload validation
def validate_uploaded_file(file) -> None:
    """
    Validate uploaded file or raise appropriate error.
    
    Raises:
        EmptyFileError: File is empty
        FileTooLargeError: File exceeds size limit
        UnsupportedFileTypeError: File type not supported
        CorruptedFileError: File is corrupted
    """
    import magic
    
    # Check not empty
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset
    
    if size == 0:
        raise EmptyFileError()
    
    # Check size limit (50MB from Config)
    max_size = app.config['MAX_CONTENT_LENGTH']
    size_mb = size / (1024 * 1024)
    max_size_mb = max_size / (1024 * 1024)
    
    if size > max_size:
        raise FileTooLargeError(size_mb, max_size_mb)
    
    # Check actual file type with magic bytes
    try:
        file_type = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)
    except Exception as e:
        raise CorruptedFileError(f"Could not read file: {e}")
    
    # Verify against allowed types
    allowed = {
        'text/plain', 'text/markdown', 'text/csv',
        'application/pdf', 'application/json',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }
    
    if file_type not in allowed:
        raise UnsupportedFileTypeError(file_type, list(allowed))
    
    # PDF-specific check: verify it's actually readable
    if file_type == 'application/pdf':
        try:
            # Quick check that we can open it
            import PyPDF2
            PyPDF2.PdfReader(file)
            file.seek(0)
        except Exception as e:
            raise CorruptedFileError(f"PDF appears corrupted: {str(e)[:100]}")


# Update upload endpoint to use validation
@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        raise ValidationError("file", "No file provided in request")
    
    file = request.files["file"]
    if file.filename == "":
        raise ValidationError("file", "No file selected")
    
    # Validate file - will raise appropriate error if invalid
    validate_uploaded_file(file)
    
    # Rest of upload logic...
```

**Testing error responses:**
```bash
# Empty file
curl -X POST http://localhost:5100/api/upload -F "file=@empty.txt"
# Expected: {"success": false, "error": "This file appears to be empty..."}

# Too large file
curl -X POST http://localhost:5100/api/upload -F "file=@huge.pdf"
# Expected: {"success": false, "error": "This file is too large (75.3MB)..."}

# Unsupported type
curl -X POST http://localhost:5100/api/upload -F "file=@video.mp4"
# Expected: {"success": false, "error": "This file type (video/mp4) is not supported..."}
```

---

## Summary Timeline

**Week 1 (Reliability):**
- Day 1-2: Provider failover
- Day 3-4: Error handling
- Day 5: Cost tracking + input validation + logging

**Week 2 (Cost Control):**
- Day 1-2: Caching
- Day 3: Rate limiting
- Day 4: Config validation
- Day 5: Testing & polish

**Week 3 (UX Polish):**
- Day 1-2: Async jobs
- Day 3: Progress indicators
- Day 4: API docs
- Day 5: Health checks

After 3 weeks, ReCog will be reliable enough that colleagues can use it without bugging you every time something goes wrong. The tool will automatically handle provider outages, give clear error messages, track costs, and provide progress feedback.

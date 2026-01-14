# recog_engine/core/providers/router.py
"""
ReCog Core - LLM Provider Router v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Routes LLM requests across multiple providers with automatic failover.
"""

import logging
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime, timedelta

from ..llm import LLMProvider, LLMResponse
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
                        f"Provider {provider_name} succeeded "
                        f"({response.usage.get('total_tokens', 0) if response.usage else 0} tokens)"
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


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "ProviderRouter",
    "create_router",
]

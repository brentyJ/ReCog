"""
ReCog Core - Anthropic Provider v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Anthropic Claude API integration for ReCog LLM operations.
"""

import logging
from typing import Optional, Dict, Any

from ..llm import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude API provider for ReCog.
    
    Uses the Anthropic Python SDK for API communication.
    Supports Claude 4 (Sonnet, Opus) and Claude 3.5 models.
    """
    
    # Default models for different use cases
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    PROCESSING_MODEL = "claude-sonnet-4-20250514"
    SYNTHESIS_MODEL = "claude-sonnet-4-20250514"
    
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: Optional[str] = None,
    ):
        """
        Initialise Anthropic provider.
        
        Args:
            api_key: Anthropic API key
            model: Model identifier (default: claude-sonnet-4-20250514)
            base_url: Optional custom API endpoint
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._client = None
        
        logger.info(f"Anthropic provider initialised with model: {model}")
    
    @property
    def name(self) -> str:
        return "anthropic"
    
    @property
    def model(self) -> str:
        return self._model
    
    def _get_client(self):
        """Lazy initialisation of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                
                kwargs = {"api_key": self._api_key}
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                
                self._client = anthropic.Anthropic(**kwargs)
            except ImportError:
                raise RuntimeError(
                    "Anthropic package not installed. Run: pip install anthropic"
                )
        return self._client
    
    def is_available(self) -> bool:
        """Check if provider is configured and can connect."""
        if not self._api_key:
            return False
        
        try:
            self._get_client()
            return True
        except Exception as e:
            logger.warning(f"Anthropic provider unavailable: {e}")
            return False
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Generate a response using Anthropic API.
        
        Args:
            prompt: User message content
            system_prompt: Optional system instructions
            temperature: Randomness (0.0-1.0)
            max_tokens: Maximum response tokens
            
        Returns:
            LLMResponse with content or error
        """
        try:
            client = self._get_client()
            
            kwargs = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            
            # Anthropic uses temperature 0.0-1.0
            # Clamp to valid range
            kwargs["temperature"] = max(0.0, min(1.0, temperature))
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = client.messages.create(**kwargs)
            
            # Extract text from content blocks
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text
            
            # Extract usage info
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                }
            
            logger.debug(
                f"Anthropic response: {len(content)} chars, "
                f"{usage.get('total_tokens', 0) if usage else 0} tokens"
            )
            
            return LLMResponse.success_response(
                content=content,
                model=response.model,
                usage=usage,
            )
        
        except ImportError as e:
            return LLMResponse.error_response(str(e))
        
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return LLMResponse.error_response(str(e))
    
    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Generate response expecting JSON output.
        
        Note: Anthropic doesn't have a native JSON mode like OpenAI.
        We rely on prompt engineering to get JSON responses.
        
        Args:
            prompt: User message (should request JSON output)
            system_prompt: Optional system instructions
            temperature: Randomness
            max_tokens: Maximum tokens
            
        Returns:
            LLMResponse with JSON content
        """
        # Enhance system prompt to request JSON
        json_system = system_prompt or ""
        if json_system:
            json_system += "\n\n"
        json_system += "IMPORTANT: Return valid JSON only. No markdown, no backticks, no explanation."
        
        return self.generate(
            prompt=prompt,
            system_prompt=json_system,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = ["AnthropicProvider"]

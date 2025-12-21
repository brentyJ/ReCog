"""
ReCog Core - OpenAI Provider v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

OpenAI API integration for ReCog LLM operations.
"""

import logging
from typing import Optional, Dict, Any

from ..llm import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider for ReCog.
    
    Uses the OpenAI Python SDK for API communication.
    Supports GPT-4o, GPT-4o-mini, and other chat completion models.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ):
        """
        Initialise OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model: Model identifier (default: gpt-4o-mini for cost efficiency)
            base_url: Optional custom API endpoint (for Azure OpenAI or proxies)
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._client = None
        
        logger.info(f"OpenAI provider initialised with model: {model}")
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def model(self) -> str:
        return self._model
    
    def _get_client(self):
        """Lazy initialisation of OpenAI client."""
        if self._client is None:
            try:
                import openai
                
                kwargs = {"api_key": self._api_key}
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                
                self._client = openai.OpenAI(**kwargs)
            except ImportError:
                raise RuntimeError(
                    "OpenAI package not installed. Run: pip install openai"
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
            logger.warning(f"OpenAI provider unavailable: {e}")
            return False
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Generate a response using OpenAI API.
        
        Args:
            prompt: User message content
            system_prompt: Optional system instructions
            temperature: Randomness (0.0-2.0)
            max_tokens: Maximum response tokens
            
        Returns:
            LLMResponse with content or error
        """
        try:
            client = self._get_client()
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            content = response.choices[0].message.content
            
            # Extract usage info
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            
            logger.debug(
                f"OpenAI response: {len(content)} chars, "
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
            logger.error(f"OpenAI API error: {e}")
            return LLMResponse.error_response(str(e))
    
    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Generate response with JSON mode enabled.
        
        Args:
            prompt: User message (should request JSON output)
            system_prompt: Optional system instructions
            temperature: Randomness
            max_tokens: Maximum tokens
            
        Returns:
            LLMResponse with JSON content
        """
        try:
            client = self._get_client()
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            
            return LLMResponse.success_response(
                content=content,
                model=response.model,
                usage=usage,
            )
        
        except Exception as e:
            logger.error(f"OpenAI JSON mode error: {e}")
            return LLMResponse.error_response(str(e))


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = ["OpenAIProvider"]

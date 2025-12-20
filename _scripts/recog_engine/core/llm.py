"""
ReCog Core - LLM Interface v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Abstract LLM interface for ReCog. Implementations wrap specific
providers (OpenAI, Anthropic, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class LLMResponse:
    """Response from an LLM call."""
    success: bool
    content: str = ""
    error: Optional[str] = None
    usage: Optional[Dict[str, int]] = None  # tokens used
    model: Optional[str] = None
    
    @classmethod
    def success_response(cls, content: str, model: str = None, 
                         usage: Dict[str, int] = None) -> "LLMResponse":
        """Create a successful response."""
        return cls(success=True, content=content, model=model, usage=usage)
    
    @classmethod
    def error_response(cls, error: str) -> "LLMResponse":
        """Create an error response."""
        return cls(success=False, error=error)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Implement this to connect ReCog to your LLM of choice.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'anthropic')."""
        pass
    
    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier (e.g., 'gpt-4o-mini', 'claude-sonnet')."""
        pass
    
    @abstractmethod
    def generate(self, 
                 prompt: str,
                 system_prompt: Optional[str] = None,
                 temperature: float = 0.3,
                 max_tokens: int = 2000) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User prompt / main content
            system_prompt: System instructions (optional)
            temperature: Randomness (0.0-1.0)
            max_tokens: Maximum response length
            
        Returns:
            LLMResponse with success/content or error
        """
        pass
    
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        return True


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider for testing.
    
    Returns canned responses without making API calls.
    """
    
    def __init__(self, responses: Dict[str, str] = None):
        """
        Args:
            responses: Map of prompt substrings to responses.
                       If prompt contains key, return value.
        """
        self._responses = responses or {}
        self._default_response = '{"insights": [], "meta": {"content_quality": "low"}}'
        self._calls = []
    
    @property
    def name(self) -> str:
        return "mock"
    
    @property
    def model(self) -> str:
        return "mock-model"
    
    def generate(self,
                 prompt: str,
                 system_prompt: Optional[str] = None,
                 temperature: float = 0.3,
                 max_tokens: int = 2000) -> LLMResponse:
        """Return mock response."""
        self._calls.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })
        
        # Check for matching response
        for key, response in self._responses.items():
            if key in prompt:
                return LLMResponse.success_response(response, self.model)
        
        return LLMResponse.success_response(self._default_response, self.model)
    
    def set_response(self, key: str, response: str) -> None:
        """Set a canned response for prompts containing key."""
        self._responses[key] = response
    
    def set_default_response(self, response: str) -> None:
        """Set default response when no key matches."""
        self._default_response = response
    
    def get_calls(self):
        """Get list of all calls made."""
        return self._calls
    
    def clear_calls(self):
        """Clear call history."""
        self._calls = []


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "LLMResponse",
    "LLMProvider", 
    "MockLLMProvider",
]

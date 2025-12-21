"""
ReCog Core - LLM Provider Factory v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Factory functions for creating LLM providers based on configuration.
"""

import os
import logging
from typing import Optional, Dict, List
from pathlib import Path

from ..llm import LLMProvider, MockLLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)


# =============================================================================
# ENVIRONMENT VARIABLE NAMES
# =============================================================================

ENV_OPENAI_KEY = "RECOG_OPENAI_API_KEY"
ENV_OPENAI_MODEL = "RECOG_OPENAI_MODEL"

ENV_ANTHROPIC_KEY = "RECOG_ANTHROPIC_API_KEY"
ENV_ANTHROPIC_MODEL = "RECOG_ANTHROPIC_MODEL"

ENV_DEFAULT_PROVIDER = "RECOG_LLM_PROVIDER"

# Legacy support
ENV_LEGACY_KEY = "RECOG_LLM_API_KEY"
ENV_LEGACY_MODEL = "RECOG_LLM_MODEL"


# =============================================================================
# DEFAULT MODELS
# =============================================================================

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
}


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def load_env_file(env_path: Path = None) -> Dict[str, str]:
    """
    Load environment variables from .env file.
    
    Args:
        env_path: Path to .env file. Defaults to current directory.
        
    Returns:
        Dict of loaded variables (also updates os.environ)
    """
    if env_path is None:
        env_path = Path.cwd() / ".env"
    
    loaded = {}
    
    if not env_path.exists():
        return loaded
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    os.environ[key] = value
                    loaded[key] = value
        
        logger.debug(f"Loaded {len(loaded)} variables from {env_path}")
    except Exception as e:
        logger.warning(f"Failed to load .env: {e}")
    
    return loaded


def get_available_providers() -> List[str]:
    """
    Get list of providers that have API keys configured.
    
    Returns:
        List of available provider names
    """
    available = []
    
    # Check OpenAI
    if os.environ.get(ENV_OPENAI_KEY) or os.environ.get(ENV_LEGACY_KEY):
        available.append("openai")
    
    # Check Anthropic
    if os.environ.get(ENV_ANTHROPIC_KEY):
        available.append("anthropic")
    
    return available


def create_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    """
    Create an LLM provider instance.
    
    Provider selection order:
    1. Explicit provider_name parameter
    2. RECOG_LLM_PROVIDER environment variable
    3. First available configured provider
    4. MockLLMProvider if nothing configured
    
    Args:
        provider_name: "openai", "anthropic", or "mock"
        api_key: Override API key (otherwise uses environment)
        model: Override model (otherwise uses environment/default)
        
    Returns:
        Configured LLMProvider instance
    """
    # Resolve provider name
    if provider_name is None:
        provider_name = os.environ.get(ENV_DEFAULT_PROVIDER, "").lower()
    
    if not provider_name:
        # Auto-detect from available keys
        available = get_available_providers()
        if available:
            provider_name = available[0]
            logger.info(f"Auto-selected provider: {provider_name}")
        else:
            logger.warning("No LLM providers configured, using mock")
            return MockLLMProvider()
    
    provider_name = provider_name.lower()
    
    # Create OpenAI provider
    if provider_name == "openai":
        key = api_key or os.environ.get(ENV_OPENAI_KEY) or os.environ.get(ENV_LEGACY_KEY)
        
        if not key:
            raise ValueError(
                f"OpenAI API key not configured. "
                f"Set {ENV_OPENAI_KEY} environment variable."
            )
        
        mdl = model or os.environ.get(ENV_OPENAI_MODEL) or os.environ.get(ENV_LEGACY_MODEL) or DEFAULT_MODELS["openai"]
        
        return OpenAIProvider(api_key=key, model=mdl)
    
    # Create Anthropic provider
    if provider_name in ("anthropic", "claude"):
        key = api_key or os.environ.get(ENV_ANTHROPIC_KEY)
        
        if not key:
            raise ValueError(
                f"Anthropic API key not configured. "
                f"Set {ENV_ANTHROPIC_KEY} environment variable."
            )
        
        mdl = model or os.environ.get(ENV_ANTHROPIC_MODEL) or DEFAULT_MODELS["anthropic"]
        
        return AnthropicProvider(api_key=key, model=mdl)
    
    # Mock provider for testing
    if provider_name == "mock":
        return MockLLMProvider()
    
    raise ValueError(f"Unknown provider: {provider_name}")


def create_extraction_provider() -> LLMProvider:
    """
    Create provider optimised for extraction (Tier 1).
    
    Uses cheaper models suitable for high-volume extraction work.
    
    Returns:
        LLMProvider for extraction tasks
    """
    available = get_available_providers()
    
    # Prefer OpenAI for extraction (GPT-4o-mini is cheaper)
    if "openai" in available:
        return create_provider("openai", model="gpt-4o-mini")
    
    if "anthropic" in available:
        return create_provider("anthropic")
    
    logger.warning("No LLM configured for extraction, using mock")
    return MockLLMProvider()


def create_synthesis_provider() -> LLMProvider:
    """
    Create provider optimised for synthesis (Tier 3).
    
    Uses higher-quality models for complex synthesis work.
    
    Returns:
        LLMProvider for synthesis tasks
    """
    available = get_available_providers()
    
    # Prefer Anthropic for synthesis (better reasoning)
    if "anthropic" in available:
        return create_provider("anthropic")
    
    if "openai" in available:
        return create_provider("openai", model="gpt-4o")
    
    logger.warning("No LLM configured for synthesis, using mock")
    return MockLLMProvider()


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "create_provider",
    "create_extraction_provider",
    "create_synthesis_provider",
    "get_available_providers",
    "load_env_file",
    "ENV_OPENAI_KEY",
    "ENV_ANTHROPIC_KEY",
    "ENV_DEFAULT_PROVIDER",
]

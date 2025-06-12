"""
Agent module initialization for the media planning agent.

This module provides the main interface for creating and managing AI agents,
with support for different LLM providers.
"""

from typing import Optional
import logging

from .base import BaseAgent, AgentError, AgentConfigurationError, AgentCommunicationError
from .session import SessionState, StrategicContext
from .claude_agent import ClaudeAgent

logger = logging.getLogger(__name__)

# Try to import OpenAI agent (may not be available)
try:
    # This will be implemented in Phase 3
    # from .openai_agent import OpenAIAgent
    OPENAI_AVAILABLE = False
    OpenAIAgent = None
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAIAgent = None


def create_agent(provider: str = "claude", model_name: Optional[str] = None, **kwargs) -> BaseAgent:
    """
    Factory function to create AI agents.

    Args:
        provider: AI provider ("claude" or "openai")
        model_name: Specific model to use (optional, uses defaults if not specified)
        **kwargs: Additional arguments passed to agent constructor

    Returns:
        Initialized agent instance

    Raises:
        AgentConfigurationError: If provider is not supported or configuration fails
    """
    provider = provider.lower()

    logger.info(f"Creating agent with provider: {provider}")

    if provider == "claude":
        model_name = model_name or "claude-3-5-sonnet-20241022"
        try:
            agent = ClaudeAgent(model_name=model_name, **kwargs)
            logger.info(f"Successfully created Claude agent: {model_name}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create Claude agent: {e}")
            raise AgentConfigurationError(f"Failed to create Claude agent: {str(e)}")

    elif provider == "openai":
        if not OPENAI_AVAILABLE:
            raise AgentConfigurationError(
                "OpenAI support not available. This will be implemented in Phase 3. "
                "For now, please use provider='claude'."
            )

        # Implementation placeholder for Phase 3
        model_name = model_name or "gpt-4-turbo-preview"
        try:
            agent = OpenAIAgent(model_name=model_name, **kwargs)
            logger.info(f"Successfully created OpenAI agent: {model_name}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create OpenAI agent: {e}")
            raise AgentConfigurationError(f"Failed to create OpenAI agent: {str(e)}")

    else:
        supported_providers = ["claude"]
        if OPENAI_AVAILABLE:
            supported_providers.append("openai")

        raise AgentConfigurationError(
            f"Unsupported provider: {provider}. "
            f"Supported providers: {', '.join(supported_providers)}"
        )


def get_available_providers() -> list:
    """
    Get list of available AI providers.

    Returns:
        List of supported provider names
    """
    providers = ["claude"]
    if OPENAI_AVAILABLE:
        providers.append("openai")
    return providers


def validate_provider(provider: str) -> bool:
    """
    Check if a provider is available.

    Args:
        provider: Provider name to check

    Returns:
        True if provider is available
    """
    return provider.lower() in get_available_providers()


def get_default_models() -> dict:
    """
    Get default model names for each provider.

    Returns:
        Dictionary mapping provider names to default model names
    """
    defaults = {
        "claude": "claude-3-5-sonnet-20241022"
    }

    if OPENAI_AVAILABLE:
        defaults["openai"] = "gpt-4-turbo-preview"

    return defaults


def test_agent_configuration(provider: str, **kwargs) -> bool:
    """
    Test if an agent can be configured successfully.

    Args:
        provider: Provider name to test
        **kwargs: Configuration arguments

    Returns:
        True if configuration is successful

    Raises:
        AgentConfigurationError: If configuration fails
    """
    try:
        agent = create_agent(provider=provider, **kwargs)
        return agent.validate_configuration()
    except Exception as e:
        logger.error(f"Agent configuration test failed for {provider}: {e}")
        raise AgentConfigurationError(f"Configuration test failed: {str(e)}")


# Export main interfaces
__all__ = [
    # Main factory function
    'create_agent',

    # Base classes
    'BaseAgent',
    'SessionState',
    'StrategicContext',

    # Specific agents
    'ClaudeAgent',

    # Exceptions
    'AgentError',
    'AgentConfigurationError',
    'AgentCommunicationError',

    # Utility functions
    'get_available_providers',
    'validate_provider',
    'get_default_models',
    'test_agent_configuration'
]

# Add OpenAI agent to exports if available
if OPENAI_AVAILABLE:
    __all__.append('OpenAIAgent')
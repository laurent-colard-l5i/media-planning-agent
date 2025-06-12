"""
Base agent interface for the media planning agent.

This module defines the abstract base class that all AI agent implementations
must inherit from, ensuring consistent behavior across different LLM providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

from .session import SessionState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for AI agents.

    This class defines the interface that all agent implementations (Claude, OpenAI, etc.)
    must implement to ensure consistent behavior and interoperability.
    """

    def __init__(self, model_name: str = None):
        """
        Initialize the base agent.

        Args:
            model_name: Name/ID of the specific model to use
        """
        self.model_name = model_name
        self.session_state = SessionState()

        # Agent metadata
        self.provider_name = "unknown"
        self.supports_function_calling = False
        self.max_tokens = 4000

        logger.info(f"Initialized {self.__class__.__name__} with model: {model_name}")

    @abstractmethod
    def chat(self, message: str, use_tools: bool = True) -> str:
        """
        Send a message to the agent and get a response.

        Args:
            message: User message to send to the agent
            use_tools: Whether to enable tool/function calling

        Returns:
            Agent's response as a string

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    @abstractmethod
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools for function calling.

        Returns:
            List of tool schemas compatible with the agent's function calling format

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    def reset_session(self) -> None:
        """Reset the session state, starting fresh."""
        logger.info(f"Resetting session for {self.__class__.__name__}")
        self.session_state = SessionState()

    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about the current session.

        Returns:
            Dictionary with session information
        """
        return {
            "agent_class": self.__class__.__name__,
            "provider": self.provider_name,
            "model": self.model_name,
            "supports_function_calling": self.supports_function_calling,
            "session_info": self.session_state.get_session_summary()
        }

    def set_system_context(self, context: str) -> None:
        """
        Set system context/instructions for the agent.

        Args:
            context: System context or instructions

        Note:
            Not all agents may support runtime system context changes.
            This is a hook for agents that do support it.
        """
        logger.debug(f"System context set for {self.__class__.__name__}")
        # Base implementation does nothing - override in subclasses if supported

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Get the conversation history from the session.

        Returns:
            List of conversation turns with timestamps
        """
        return self.session_state.conversation_history

    def add_strategic_context(self, context: Dict[str, Any]) -> None:
        """
        Add strategic context to the session.

        Args:
            context: Strategic context information
        """
        logger.debug(f"Adding strategic context to {self.__class__.__name__} session")
        self.session_state.update_strategic_context(context)

    def get_strategic_summary(self) -> str:
        """
        Get strategic summary from current session.

        Returns:
            Strategic summary string for use in media plan comments
        """
        return self.session_state.generate_strategic_summary()

    def validate_configuration(self) -> bool:
        """
        Validate that the agent is properly configured.

        Returns:
            True if configuration is valid, False otherwise

        Note:
            Base implementation always returns True.
            Override in subclasses for specific validation.
        """
        return True

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary with model information
        """
        return {
            "provider": self.provider_name,
            "model_name": self.model_name,
            "supports_function_calling": self.supports_function_calling,
            "max_tokens": self.max_tokens
        }

    def handle_error(self, error: Exception, context: str = "") -> str:
        """
        Handle errors that occur during agent operations.

        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred

        Returns:
            User-friendly error message
        """
        error_msg = f"Sorry, I encountered an error"
        if context:
            error_msg += f" while {context}"
        error_msg += f": {str(error)}"

        logger.error(f"Agent error in {self.__class__.__name__}: {error}")

        return error_msg


class AgentError(Exception):
    """Base exception for agent-related errors."""
    pass


class AgentConfigurationError(AgentError):
    """Exception raised when agent configuration is invalid."""
    pass


class AgentCommunicationError(AgentError):
    """Exception raised when communication with the agent fails."""
    pass


class ToolExecutionError(AgentError):
    """Exception raised when tool execution fails within an agent."""
    pass


# Utility functions for agent implementations

def format_tool_error(tool_name: str, error: Exception) -> Dict[str, Any]:
    """
    Format a tool execution error for consistent error handling.

    Args:
        tool_name: Name of the tool that failed
        error: The exception that occurred

    Returns:
        Formatted error dictionary
    """
    return {
        "success": False,
        "error": f"Tool '{tool_name}' execution failed: {str(error)}",
        "tool_name": tool_name,
        "error_type": type(error).__name__
    }


def validate_tool_result(result: Any) -> bool:
    """
    Validate that a tool result has the expected structure.

    Args:
        result: Tool execution result to validate

    Returns:
        True if result is valid, False otherwise
    """
    if not isinstance(result, dict):
        return False

    if "success" not in result:
        return False

    if not isinstance(result["success"], bool):
        return False

    return True


def create_agent_response(message: str, **metadata) -> str:
    """
    Create a standardized agent response.

    Args:
        message: The main response message
        **metadata: Additional metadata (for logging/debugging)

    Returns:
        Formatted response string
    """
    # For now, just return the message
    # In the future, could add metadata formatting
    return message
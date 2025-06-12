"""
Tool registry and base classes for the media planning agent.

This module provides the foundation for creating and managing tools that
the agent can use to interact with the MediaPlanPy SDK and workspace.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Callable, Optional, Type, get_type_hints
from functools import wraps
import inspect
import logging

logger = logging.getLogger(__name__)

class Tool(ABC):
    """Abstract base class for agent tools."""

    def __init__(self, name: str, description: str, original_func: Optional[Callable] = None):
        self.name = name
        self.description = description
        self.original_func = original_func  # Store reference to original function

    @abstractmethod
    def execute(self, session_state, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool with given parameters.

        Args:
            session_state: Current session state object
            **kwargs: Tool-specific parameters

        Returns:
            Dictionary with 'success' boolean and additional data/messages
        """
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for Claude function calling (Anthropic format)."""
        # Use original function signature if available, otherwise fall back to execute method
        func_to_inspect = self.original_func if self.original_func else self.execute
        sig = inspect.signature(func_to_inspect)

        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            # Skip session_state and **kwargs
            if param_name in ['session_state', 'kwargs']:
                continue

            # Skip **kwargs parameters
            if param.kind == param.VAR_KEYWORD:
                continue

            # Get parameter type
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else str

            # Create property definition
            properties[param_name] = {
                "type": self._python_type_to_json_type(param_type),
                "description": self._get_param_description(param_name, param)
            }

            # Check if parameter is required (no default value)
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        # Return Claude-compatible format (uses "input_schema" not "parameters")
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

    def _python_type_to_json_type(self, python_type) -> str:
        """Convert Python type to JSON schema type."""
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }

        # Handle Optional types
        if hasattr(python_type, '__origin__'):
            if python_type.__origin__ is type(None):
                return "string"  # Default for None
            elif hasattr(python_type, '__args__'):
                # Handle Union types (like Optional[str])
                non_none_types = [arg for arg in python_type.__args__ if arg is not type(None)]
                if non_none_types:
                    return self._python_type_to_json_type(non_none_types[0])

        return type_mapping.get(python_type, "string")

    def _get_param_description(self, param_name: str, param: inspect.Parameter) -> str:
        """Generate description for parameter."""
        # Try to extract from docstring if available
        # For now, generate basic description
        type_str = ""
        if param.annotation != inspect.Parameter.empty:
            type_str = f" ({param.annotation.__name__ if hasattr(param.annotation, '__name__') else str(param.annotation)})"

        optional_str = "" if param.default == inspect.Parameter.empty else " (optional)"

        return f"Parameter {param_name}{type_str}{optional_str}"

class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._tool_categories: Dict[str, List[str]] = {}

    def register(self, tool: Tool, category: str = "general") -> None:
        """Register a tool in the registry."""
        if tool.name in self.tools:
            logger.warning(f"Tool '{tool.name}' is already registered. Overwriting.")

        self.tools[tool.name] = tool

        # Add to category
        if category not in self._tool_categories:
            self._tool_categories[category] = []
        if tool.name not in self._tool_categories[category]:
            self._tool_categories[category].append(tool.name)

        logger.debug(f"Registered tool '{tool.name}' in category '{category}'")

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool by name."""
        return self.tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools."""
        return list(self.tools.values())

    def get_tools_by_category(self, category: str) -> List[Tool]:
        """Get all tools in a specific category."""
        tool_names = self._tool_categories.get(category, [])
        return [self.tools[name] for name in tool_names if name in self.tools]

    def get_tool_names(self) -> List[str]:
        """Get list of all tool names."""
        return list(self.tools.keys())

    def get_categories(self) -> List[str]:
        """Get list of all categories."""
        return list(self._tool_categories.keys())

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all tools for Claude function calling."""
        schemas = []
        for tool in self.tools.values():
            try:
                schema = tool.get_schema()
                schemas.append(schema)
                logger.debug(f"Generated schema for tool '{tool.name}': {schema}")
            except Exception as e:
                logger.error(f"Failed to generate schema for tool '{tool.name}': {e}")
                # Skip tools with invalid schemas rather than failing completely
                continue
        return schemas

    def get_tool_info(self) -> Dict[str, Any]:
        """Get comprehensive information about all registered tools."""
        return {
            "total_tools": len(self.tools),
            "categories": {
                category: len(tool_names)
                for category, tool_names in self._tool_categories.items()
            },
            "tools": {
                name: {
                    "description": tool.description,
                    "category": self._get_tool_category(name)
                }
                for name, tool in self.tools.items()
            }
        }

    def _get_tool_category(self, tool_name: str) -> str:
        """Get category for a specific tool."""
        for category, tool_names in self._tool_categories.items():
            if tool_name in tool_names:
                return category
        return "unknown"

# Global tool registry instance
tool_registry = ToolRegistry()

def register_tool(name: str, description: str, category: str = "general"):
    """Decorator to register a tool function."""
    def decorator(func: Callable) -> Callable:
        class FunctionTool(Tool):
            def __init__(self):
                super().__init__(name, description, original_func=func)  # Pass original function

            def execute(self, session_state, **kwargs):
                try:
                    return func(session_state, **kwargs)
                except Exception as e:
                    logger.error(f"Tool '{name}' execution failed: {e}")
                    return {
                        "success": False,
                        "message": f"❌ Tool execution failed: {str(e)}",
                        "error": str(e)
                    }

        # Create and register the tool
        tool = FunctionTool()
        tool_registry.register(tool, category)

        # Log successful registration
        logger.info(f"Registered tool: {name}")

        # Return the original function (for potential direct use)
        return func

    return decorator

def get_tool_registry(use_json: bool = True, json_path: Optional[str] = None):
    """
    Get tool registry - supports both JSON and decorator approaches.

    Args:
        use_json: If True, use JSON registry. If False, use decorator registry.
        json_path: Path to JSON registry file (optional)

    Returns:
        Tool registry instance
    """
    if use_json:
        try:
            from ..agent.json_registry import get_json_tool_registry
            return get_json_tool_registry(json_path)
        except Exception as e:
            logger.warning(f"Failed to load JSON registry: {e}")
            logger.info("Falling back to decorator-based registry")

    # Fallback to original decorator-based registry
    return tool_registry  # Your existing global registry

class ToolExecutionError(Exception):
    """Exception raised when tool execution fails."""
    pass

class ToolNotFoundError(Exception):
    """Exception raised when requested tool is not found."""
    pass

def execute_tool(tool_name: str, session_state, **kwargs) -> Dict[str, Any]:
    """
    Execute a tool by name with error handling.

    Args:
        tool_name: Name of the tool to execute
        session_state: Current session state
        **kwargs: Tool parameters

    Returns:
        Tool execution result

    Raises:
        ToolNotFoundError: If tool is not registered
        ToolExecutionError: If tool execution fails
    """
    tool = tool_registry.get_tool(tool_name)
    if not tool:
        raise ToolNotFoundError(f"Tool '{tool_name}' not found in registry")

    try:
        return tool.execute(session_state, **kwargs)
    except Exception as e:
        logger.error(f"Failed to execute tool '{tool_name}': {e}")
        raise ToolExecutionError(f"Tool execution failed: {str(e)}") from e

# Utility functions for tool development
def validate_tool_result(result: Dict[str, Any]) -> bool:
    """Validate that a tool result has the expected structure."""
    if not isinstance(result, dict):
        return False

    if "success" not in result:
        return False

    if not isinstance(result["success"], bool):
        return False

    # Optional but recommended fields
    recommended_fields = ["message"]
    for field in recommended_fields:
        if field in result and not isinstance(result[field], str):
            return False

    return True

def create_success_result(message: str, **extra_data) -> Dict[str, Any]:
    """Helper to create a standardized success result."""
    result = {
        "success": True,
        "message": message
    }
    result.update(extra_data)
    return result

def create_error_result(message: str, error: Optional[str] = None, **extra_data) -> Dict[str, Any]:
    """Helper to create a standardized error result."""
    result = {
        "success": False,
        "message": message
    }
    if error:
        result["error"] = error
    result.update(extra_data)
    return result
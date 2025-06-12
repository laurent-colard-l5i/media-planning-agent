"""
Tools module initialization for the media planning agent.

This module initializes the tool registry and imports all available tools
to make them available for agent use.
"""

from .base import (
    Tool,
    ToolRegistry,
    register_tool,
    get_tool_registry,
    execute_tool,
    ToolExecutionError,
    ToolNotFoundError,
    validate_tool_result,
    create_success_result,
    create_error_result
)

# Import tool modules to register tools
from . import workspace_tools
from . import mediaplan_tools

# Get the global registry instance
tool_registry = get_tool_registry()


def get_available_tools():
    """Get list of all available tools."""
    return tool_registry.get_all_tools()


def get_tool_info():
    """Get comprehensive information about registered tools."""
    return tool_registry.get_tool_info()


def list_tools_by_category():
    """Get tools organized by category."""
    info = tool_registry.get_tool_info()
    return {
        "categories": info["categories"],
        "tools_by_category": {
            category: [
                tool_name for tool_name, tool_info in info["tools"].items()
                if tool_info["category"] == category
            ]
            for category in info["categories"].keys()
        }
    }


# Export main interfaces
__all__ = [
    # Base classes and utilities
    'Tool',
    'ToolRegistry',
    'register_tool',
    'get_tool_registry',
    'execute_tool',

    # Exceptions
    'ToolExecutionError',
    'ToolNotFoundError',

    # Utility functions
    'validate_tool_result',
    'create_success_result',
    'create_error_result',
    'get_available_tools',
    'get_tool_info',
    'list_tools_by_category',

    # Registry instance
    'tool_registry'
]
"""
Media Planning Agent - An interactive AI agent for media plan creation and management.

This package provides tools for creating, managing, and optimizing media plans
using the MediaPlanPy SDK with AI assistance from various LLM providers.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

# Import main interfaces for easy access
from .agent import (
    create_agent,
    BaseAgent,
    ClaudeAgent,
    SessionState,
    StrategicContext,
    get_available_providers,
    get_default_models
)

from .tools import (
    get_tool_registry,
    get_available_tools,
    get_tool_info,
    list_tools_by_category
)

# Version info
version_info = tuple(int(x) for x in __version__.split('.'))

# Package metadata
__title__ = "media-planning-agent"
__description__ = "Interactive AI agent for media plan creation and management"
__url__ = "https://github.com/your-org/media-planning-agent"
__license__ = "MIT"

# Export main interfaces
__all__ = [
    # Version info
    '__version__',
    'version_info',

    # Agent interfaces
    'create_agent',
    'BaseAgent',
    'ClaudeAgent',
    'SessionState',
    'StrategicContext',
    'get_available_providers',
    'get_default_models',

    # Tool interfaces
    'get_tool_registry',
    'get_available_tools',
    'get_tool_info',
    'list_tools_by_category'
]


def get_package_info():
    """Get comprehensive package information."""
    return {
        "name": __title__,
        "version": __version__,
        "description": __description__,
        "author": __author__,
        "license": __license__,
        "available_providers": get_available_providers(),
        "default_models": get_default_models(),
        "total_tools": len(get_available_tools()),
        "tool_categories": list_tools_by_category()["categories"]
    }


# Add package info to exports
__all__.append('get_package_info')
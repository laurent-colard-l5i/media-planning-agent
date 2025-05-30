"""
JSON Tool Registry - Proof of Concept Implementation
Focused on clean separation between decision data and behavioral guidance.
"""

import json
import importlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class JsonToolRegistry:
    """Tool registry that loads metadata from JSON configuration."""

    def __init__(self, registry_path: Optional[str] = None):
        """
        Initialize the registry.

        Args:
            registry_path: Path to the JSON registry file
        """
        self.tools: Dict[str, 'JsonTool'] = {}
        self.registry_data: Dict[str, Any] = {}

        # Default to tool_registry.json in the agent directory
        if not registry_path:
            registry_path = Path(__file__).parent / "tool_registry.json"

        self.registry_path = Path(registry_path)
        self.load_registry()

    def load_registry(self) -> None:
        """Load tool definitions from JSON file."""
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                self.registry_data = json.load(f)

            logger.info(f"Loaded tool registry from: {self.registry_path}")
            self._register_tools_from_json()

        except FileNotFoundError:
            logger.error(f"Tool registry file not found: {self.registry_path}")
            logger.info("Falling back to decorator-based registry")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in registry file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load tool registry: {e}")
            raise

    def _register_tools_from_json(self) -> None:
        """Register all tools defined in the JSON registry."""
        tool_registry = self.registry_data.get("tool_registry", {})

        # Process each category of tools
        for category_name, category_tools in tool_registry.items():
            logger.debug(f"Processing category: {category_name}")

            for tool_name, tool_config in category_tools.items():
                try:
                    self._register_single_tool(tool_name, tool_config, category_name)
                except Exception as e:
                    logger.error(f"Failed to register tool '{tool_name}': {e}")
                    continue

    def _register_single_tool(self, tool_name: str, config: Dict[str, Any], category: str) -> None:
        """Register a single tool from JSON configuration."""

        # Import the function dynamically
        module_path = config.get("module_path")
        function_name = config.get("function_name")

        if not module_path or not function_name:
            raise ValueError(f"Tool {tool_name} missing module_path or function_name")

        try:
            module = importlib.import_module(module_path)
            func = getattr(module, function_name)
        except ImportError as e:
            raise ImportError(f"Cannot import {module_path}: {e}")
        except AttributeError as e:
            raise AttributeError(f"Function {function_name} not found in {module_path}: {e}")

        # Create JsonTool instance
        tool = JsonTool(
            name=tool_name,
            config=config,
            function=func,
            category=category
        )

        self.tools[tool_name] = tool
        logger.debug(f"Registered tool: {tool_name}")

    def get_tool(self, name: str) -> Optional['JsonTool']:
        """Get tool by name."""
        return self.tools.get(name)

    def get_all_tools(self) -> List['JsonTool']:
        """Get all registered tools."""
        return list(self.tools.values())

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get Claude-compatible schemas for all tools."""
        schemas = []
        for tool in self.tools.values():
            try:
                schema = tool.get_schema()
                schemas.append(schema)
                logger.debug(f"Generated schema for tool '{tool.name}'")
            except Exception as e:
                logger.error(f"Failed to generate schema for tool '{tool.name}': {e}")
                continue
        return schemas

    def get_tool_names(self) -> List[str]:
        """Get list of all tool names."""
        return list(self.tools.keys())

    def reload_registry(self) -> None:
        """Reload the registry from file (useful for development)."""
        logger.info("Reloading tool registry...")
        old_count = len(self.tools)
        self.tools.clear()
        self.load_registry()
        new_count = len(self.tools)
        logger.info(f"Registry reloaded: {old_count} → {new_count} tools")


class JsonTool:
    """Tool instance created from JSON configuration."""

    def __init__(self, name: str, config: Dict[str, Any], function: Callable, category: str):
        self.name = name
        self.config = config
        self.function = function
        self.category = category

        # Extract commonly used fields
        self.description = config.get("description", "")
        self.parameters = config.get("parameters", {})
        self.triggers = config.get("triggers", {})

    def execute(self, session_state, **kwargs) -> Dict[str, Any]:
        """Execute the tool function."""
        try:
            return self.function(session_state, **kwargs)
        except Exception as e:
            logger.error(f"Tool '{self.name}' execution failed: {e}")
            return {
                "success": False,
                "message": f"❌ Tool execution failed: {str(e)}",
                "error": str(e)
            }

    def get_schema(self) -> Dict[str, Any]:
        """Generate Claude-compatible schema from JSON configuration."""
        properties = {}
        required = []

        for param_name, param_config in self.parameters.items():
            properties[param_name] = {
                "type": param_config.get("type", "string"),
                "description": param_config.get("description", f"Parameter {param_name}")
            }

            # Add additional schema properties if defined
            if "format" in param_config:
                properties[param_name]["format"] = param_config["format"]
            if "examples" in param_config:
                properties[param_name]["examples"] = param_config["examples"]
            if "enum" in param_config:
                properties[param_name]["enum"] = param_config["enum"]
            if "default" in param_config:
                properties[param_name]["default"] = param_config["default"]

            # Check if required
            if param_config.get("required", False):
                required.append(param_name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

    def matches_user_intent(self, user_input: str) -> bool:
        """Check if user input matches this tool's triggers."""
        user_input_lower = user_input.lower().strip()

        # Check user_intents from triggers
        user_intents = self.triggers.get("user_intents", [])
        for intent in user_intents:
            if intent.lower() in user_input_lower:
                return True

        return False

    def get_display_requirements(self) -> Dict[str, Any]:
        """Get display requirements for this tool."""
        return self.config.get("display_requirements", {})


# Global registry instance
_json_tool_registry = None


def get_json_tool_registry(registry_path: Optional[str] = None) -> JsonToolRegistry:
    """Get the global JSON tool registry instance."""
    global _json_tool_registry
    if _json_tool_registry is None:
        _json_tool_registry = JsonToolRegistry(registry_path)
    return _json_tool_registry


def generate_system_prompt_enhancement(registry: JsonToolRegistry) -> str:
    """
    Generate system prompt enhancements from registry metadata.
    This adds structured guidance based on tool configurations.
    """

    enhancements = []

    # Add display requirements for tools that have them
    display_tools = []
    for tool in registry.get_all_tools():
        display_reqs = tool.get_display_requirements()
        if display_reqs:
            rules = []
            if display_reqs.get("never_summarize"):
                rules.append(f"- NEVER summarize results from {tool.name}")
            if display_reqs.get("always_include"):
                items = ", ".join(display_reqs["always_include"])
                rules.append(f"- ALWAYS include: {items}")
            if display_reqs.get("show_individual_plans"):
                rules.append(f"- Show each item individually with complete details")

            if rules:
                display_tools.append(f"### {tool.name}\n" + "\n".join(rules))

    if display_tools:
        enhancements.append("## Tool-Specific Display Requirements\n" + "\n\n".join(display_tools))

    # Add consultation requirements
    consultation_tools = []
    for tool in registry.get_all_tools():
        prerequisites = tool.triggers.get("prerequisites", [])
        if "strategic_consultation_completed" in prerequisites:
            consultation_tools.append(f"- **{tool.name}**: Requires strategic consultation before execution")

    if consultation_tools:
        enhancements.append("## Strategic Consultation Required\n" + "\n".join(consultation_tools))

    return "\n\n".join(enhancements) if enhancements else ""


# Backward compatibility function
def get_tool_registry(use_json: bool = True, json_path: Optional[str] = None):
    """
    Get tool registry - supports both JSON and decorator approaches.

    Args:
        use_json: If True, use JSON registry. If False, fall back to decorator registry.
        json_path: Path to JSON registry file (optional)

    Returns:
        Tool registry instance
    """
    if use_json:
        try:
            return get_json_tool_registry(json_path)
        except Exception as e:
            logger.warning(f"Failed to load JSON registry: {e}")
            logger.info("Falling back to decorator-based registry")
            use_json = False

    if not use_json:
        # Import the original decorator-based registry
        from .base import tool_registry
        return tool_registry
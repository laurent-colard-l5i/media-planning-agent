"""
Claude agent implementation with JSON tool registry support.
Combines external system prompt with registry-based tool metadata.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date
from decimal import Decimal
import logging

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from .base import BaseAgent, AgentConfigurationError, AgentCommunicationError
from .json_registry import get_json_tool_registry, generate_system_prompt_enhancement

logger = logging.getLogger(__name__)

def safe_log_text(text: str, max_length: int = 100) -> str:
    """
    Safely log text by removing problematic Unicode characters for Windows console.

    Args:
        text: Text to log
        max_length: Maximum length to log

    Returns:
        Safe text for logging
    """
    try:
        # Try to encode with cp1252 to test compatibility
        safe_text = text[:max_length]
        safe_text.encode('cp1252')
        return safe_text + ("..." if len(text) > max_length else "")
    except UnicodeEncodeError:
        # Remove or replace problematic characters
        safe_text = text[:max_length].encode('cp1252', errors='replace').decode('cp1252')
        return safe_text + ("..." if len(text) > max_length else "")
    except Exception:
        # Fallback: ASCII only
        safe_text = ''.join(c if ord(c) < 128 else '?' for c in text[:max_length])
        return safe_text + ("..." if len(text) > max_length else "")

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles date, datetime, and Decimal objects."""

    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

class ClaudeAgent(BaseAgent):
    """Claude-powered media planning agent with JSON tool registry support."""

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022",
                 api_key: Optional[str] = None,
                 system_prompt_path: Optional[str] = None,
                 tool_registry_path: Optional[str] = None):
        """
        Initialize Claude agent with JSON tool registry.

        Args:
            model_name: Claude model to use
            api_key: Anthropic API key (if not provided, will use environment variable)
            system_prompt_path: Path to system prompt markdown file (optional)
            tool_registry_path: Path to tool registry JSON file (optional)

        Raises:
            AgentConfigurationError: If Claude is not available or API key is missing
        """
        if not ANTHROPIC_AVAILABLE:
            raise AgentConfigurationError(
                "Anthropic package not available. Install with: pip install anthropic"
            )

        super().__init__(model_name)

        # Agent metadata
        self.provider_name = "anthropic"
        self.supports_function_calling = True
        self.max_tokens = 4000

        # Get API key
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise AgentConfigurationError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter."
            )

        # Initialize client
        try:
            self.client = Anthropic(api_key=self.api_key)
        except Exception as e:
            raise AgentConfigurationError(f"Failed to initialize Anthropic client: {str(e)}")

        # Load JSON tool registry
        try:
            self.tool_registry = get_json_tool_registry(tool_registry_path)
            logger.info(f"Loaded JSON tool registry with {len(self.tool_registry.tools)} tools")
        except Exception as e:
            logger.error(f"Failed to load JSON tool registry: {e}")
            # Fall back to decorator-based registry
            from ..tools.base import get_tool_registry
            self.tool_registry = get_tool_registry(use_json=False)
            logger.info("Using fallback decorator-based tool registry")

        # Load and build system prompt
        self.system_prompt = self._build_complete_system_prompt(system_prompt_path)

        # Conversation history for Claude API
        self.conversation_history = []

        logger.info(f"Initialized Claude agent with model: {model_name}")

    def _build_complete_system_prompt(self, custom_path: Optional[str] = None) -> str:
        """
        Build complete system prompt from external file plus registry and schema enhancements.

        Args:
            custom_path: Custom path to system prompt file

        Returns:
            Complete system prompt content
        """
        # Load base system prompt from external file
        base_prompt = self._load_base_system_prompt(custom_path)

        # Generate enhancements from tool registry
        registry_enhancements = generate_system_prompt_enhancement(self.tool_registry)

        # Generate schema enhancements from MediaPlanPy
        schema_enhancements = self._get_schema_enhancements()

        # Combine all components
        prompt_parts = [base_prompt]

        if registry_enhancements:
            prompt_parts.append("## Tool Registry Enhancements")
            prompt_parts.append(registry_enhancements)

        if schema_enhancements:
            prompt_parts.append("## Schema Definitions")
            prompt_parts.append(schema_enhancements)

        complete_prompt = "\n\n".join(prompt_parts)

        # Save system prompt to file in debug mode
        if logger.isEnabledFor(logging.DEBUG):
            try:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # FIXED: Save to debug_output directory instead of root
                debug_dir = Path("debug_output")
                debug_dir.mkdir(exist_ok=True)
                filename = debug_dir / f"{timestamp}_debug_system_prompt.md"

                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"# System Prompt Debug Output\n")
                    f.write(f"Generated at: {datetime.now().isoformat()}\n")
                    f.write(f"Model: {self.model_name}\n")
                    f.write(f"Prompt length: {len(complete_prompt)} characters\n\n")
                    f.write("---\n\n")
                    f.write(complete_prompt)

                logger.debug(f"System prompt saved to debug file: {filename}")
            except Exception as e:
                logger.warning(f"Failed to save debug system prompt: {e}")

        logger.info(f"Built complete system prompt: {len(complete_prompt)} characters")

        return complete_prompt

    def _load_base_system_prompt(self, custom_path: Optional[str] = None) -> str:
        """
        Load base system prompt from external markdown file.

        Args:
            custom_path: Custom path to system prompt file

        Returns:
            Base system prompt content as string
        """
        # Determine prompt file path
        if custom_path:
            prompt_path = Path(custom_path)
        else:
            # Default to system_prompt.md in the same directory as this file
            current_dir = Path(__file__).parent
            prompt_path = current_dir / "system_prompt.md"

        # Try to load external prompt file
        try:
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"Loaded base system prompt from: {prompt_path}")
                return content
            else:
                logger.warning(f"System prompt file not found at: {prompt_path}")
                return self._get_fallback_system_prompt()
        except Exception as e:
            logger.error(f"Failed to load system prompt from {prompt_path}: {e}")
            return self._get_fallback_system_prompt()

    def _get_fallback_system_prompt(self) -> str:
        """Fallback system prompt if external file cannot be loaded."""
        logger.info("Using fallback system prompt")
        return """You are an expert media planning agent designed to help users create, manage, and optimize media plans using the MediaPlanPy SDK.

CRITICAL: When tools return structured data, ALWAYS display the actual details, not summaries.

For list_mediaplans results:
- Show individual media plan IDs (users need these)
- Display exact creation dates and times
- Show precise budget and cost figures
- List each plan separately with specific details
- Include line item counts and allocated costs as returned

Example GOOD format:
📋 Found X media plans:

1. **Campaign Name** (ID: mediaplan_abc123)
   - Budget: $X | Allocated: $Y | Line items: Z
   - Timeline: start to end | Created: exact timestamp
   - Created by: email

[List each plan with its specific details]

Never summarize tool results - show the actual data returned."""

    def chat(self, message: str, use_tools: bool = True) -> str:
        """
        Send message to Claude and get response with tool execution.

        Args:
            message: User message
            use_tools: Whether to enable function calling

        Returns:
            Claude's response

        Raises:
            AgentCommunicationError: If communication with Claude fails
        """
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": message})

        try:
            # Get available tools if requested
            tools = self.get_available_tools() if use_tools else None
            logger.debug(f"Using {len(tools) if tools else 0} tools for this request")

            # Make initial API call
            logger.debug("Making initial API call to Claude")
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=self.conversation_history,
                tools=tools
            )

            logger.debug(f"Received response with {len(response.content)} content blocks")

            response_text = ""
            tool_calls_made = []

            # Process response content with better error handling
            for i, content_block in enumerate(response.content):
                logger.debug(f"Processing content block {i}: type={content_block.type}")

                if content_block.type == "text":
                    response_text += content_block.text
                    logger.debug(f"Added text content: {safe_log_text(content_block.text)}")

                elif content_block.type == "tool_use":
                    logger.debug(f"Executing tool: {content_block.name}")
                    # Execute tool and collect results
                    tool_result = self._execute_tool(content_block)
                    tool_calls_made.append({
                        "tool_name": content_block.name,
                        "result": tool_result,
                        "tool_use_id": content_block.id
                    })
                    logger.debug(f"Tool {content_block.name} executed, success: {tool_result.get('success', 'unknown')}")

            # If tools were called, we need to continue the conversation
            if tool_calls_made:
                logger.debug(f"Processing {len(tool_calls_made)} tool results")

                # Add assistant message with tool calls to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Add tool results to history with custom JSON encoder
                for i, tool_call in enumerate(tool_calls_made):
                    try:
                        # Use custom encoder to handle dates and decimals
                        tool_result_json = json.dumps(tool_call["result"], cls=CustomJSONEncoder)
                        logger.debug(f"Successfully serialized tool result for {tool_call['tool_name']}")
                    except Exception as e:
                        logger.error(f"Failed to serialize tool result for {tool_call['tool_name']}: {e}")
                        # Fallback: create a safe JSON representation
                        tool_result_json = json.dumps({
                            "success": tool_call["result"].get("success", False),
                            "message": str(tool_call["result"].get("message", "Serialization error")),
                            "error": f"JSON serialization failed: {str(e)}"
                        })

                    self.conversation_history.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_call["tool_use_id"],
                            "content": tool_result_json
                        }]
                    })

                # Get follow-up response after tool execution
                logger.debug("Getting follow-up response from Claude")
                follow_up_response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt,
                    messages=self.conversation_history,
                    tools=tools
                )

                logger.debug(f"Follow-up response has {len(follow_up_response.content)} content blocks")

                # Extract text from follow-up response with error handling
                follow_up_text = ""
                for i, content_block in enumerate(follow_up_response.content):
                    logger.debug(f"Processing follow-up content block {i}: type={content_block.type}")
                    if content_block.type == "text":
                        follow_up_text += content_block.text
                        logger.debug(f"Added follow-up text: {safe_log_text(content_block.text)}")

                response_text = follow_up_text

                # Add follow-up to history
                if follow_up_text:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": follow_up_text
                    })
            else:
                # No tools called, add response to history
                if response_text:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response_text
                    })

            # Store conversation in session state
            if response_text:
                self.session_state.add_conversation_turn(message, response_text)

            logger.debug(f"Final response length: {len(response_text)} characters")
            return response_text or "I executed some tools but didn't provide a text response."

        except Exception as e:
            logger.error(f"Claude communication error: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            error_msg = self.handle_error(e, "processing your request")

            # Add error to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": error_msg
            })

            raise AgentCommunicationError(f"Claude communication failed: {str(e)}")

    def _execute_tool(self, tool_call) -> Dict[str, Any]:
        """
        Execute a tool call from Claude using the JSON registry.

        Args:
            tool_call: Claude tool call object

        Returns:
            Tool execution result
        """
        tool_name = tool_call.name
        tool_args = tool_call.input

        logger.debug(f"Executing tool: {tool_name} with args: {tool_args}")

        # Get tool from JSON registry
        tool = self.tool_registry.get_tool(tool_name)

        if not tool:
            error_result = {
                "success": False,
                "error": f"Tool '{tool_name}' not found in JSON registry",
                "available_tools": self.tool_registry.get_tool_names()
            }
            logger.error(f"Tool not found: {tool_name}")
            return error_result

        try:
            # Execute tool with session state
            result = tool.execute(self.session_state, **tool_args)
            logger.debug(f"Tool {tool_name} executed successfully")
            return result

        except Exception as e:
            error_result = {
                "success": False,
                "error": f"Tool execution failed: {str(e)}",
                "tool_name": tool_name,
                "error_type": type(e).__name__
            }
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            import traceback
            logger.error(f"Tool execution traceback: {traceback.format_exc()}")
            return error_result

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get tool schemas formatted for Claude function calling."""
        return self.tool_registry.get_tool_schemas()

    def validate_configuration(self) -> bool:
        """
        Validate Claude agent configuration.

        Returns:
            True if configuration is valid

        Raises:
            AgentConfigurationError: If configuration is invalid
        """
        try:
            # Test API connection with a simple request
            test_response = self.client.messages.create(
                model=self.model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )

            logger.info("Claude configuration validated successfully")
            return True

        except Exception as e:
            logger.error(f"Claude configuration validation failed: {e}")
            raise AgentConfigurationError(f"Claude configuration invalid: {str(e)}")

    def reload_prompts_and_tools(self, system_prompt_path: Optional[str] = None,
                                tool_registry_path: Optional[str] = None) -> str:
        """
        Reload system prompt and tool registry from files (useful for development).

        Args:
            system_prompt_path: Custom path to system prompt file
            tool_registry_path: Custom path to tool registry file

        Returns:
            Status message about what was reloaded
        """
        messages = []

        # Reload tool registry
        try:
            if tool_registry_path:
                self.tool_registry = get_json_tool_registry(tool_registry_path)
            else:
                self.tool_registry.reload_registry()
            messages.append(f"✅ Reloaded tool registry: {len(self.tool_registry.tools)} tools")
        except Exception as e:
            messages.append(f"❌ Failed to reload tool registry: {e}")

        # Reload system prompt
        try:
            old_length = len(self.system_prompt)
            self.system_prompt = self._build_complete_system_prompt(system_prompt_path)
            new_length = len(self.system_prompt)
            messages.append(f"✅ Reloaded system prompt: {old_length} → {new_length} characters")
        except Exception as e:
            messages.append(f"❌ Failed to reload system prompt: {e}")

        return "\n".join(messages)

    def get_model_info(self) -> Dict[str, Any]:
        """Get detailed model information including registry info."""
        base_info = super().get_model_info()
        base_info.update({
            "api_version": "2023-06-01",
            "context_length": 200000 if "claude-3" in self.model_name else 100000,
            "supports_images": "claude-3" in self.model_name,
            "supports_tool_calling": True,
            "system_prompt_length": len(self.system_prompt),
            "tool_registry_type": "json" if hasattr(self.tool_registry, 'registry_data') else "decorator",
            "tool_count": len(self.tool_registry.get_tool_names())
        })
        return base_info

    def _get_schema_enhancements(self) -> str:
        """
        Generate schema definitions section for system prompt.

        Returns:
            Formatted schema definitions as markdown string
        """
        try:
            # Determine schema version to use
            schema_version = self._get_preferred_schema_version()

            # Get schemas from MediaPlanPy
            schemas = self._load_schemas(schema_version)

            if not schemas:
                logger.warning("No schemas loaded for system prompt")
                return ""

            # Format schemas for system prompt
            return self._format_schemas_for_prompt(schemas, schema_version)

        except Exception as e:
            logger.error(f"Failed to generate schema enhancements: {e}")
            return ""

    def _get_preferred_schema_version(self) -> str:
        """
        Get preferred schema version from workspace or use default.

        Returns:
            Schema version string (e.g., 'v2.0')
        """
        try:
            # Check if we have session state with workspace manager
            if (hasattr(self, 'session_state') and
                    self.session_state and
                    hasattr(self.session_state, 'workspace_manager') and
                    self.session_state.workspace_manager):

                config = self.session_state.workspace_manager.get_resolved_config()
                preferred_version = config.get('schema_settings', {}).get('preferred_version')

                if preferred_version:
                    logger.info(f"Using workspace preferred schema version: {preferred_version}")
                    return preferred_version

            default_version = "v2.0"
            logger.info(f"Using default schema version: {default_version}")
            return default_version

        except Exception as e:
            logger.warning(f"Failed to get preferred schema version: {e}, using default")
            return "v2.0"

    def _load_schemas(self, schema_version: str) -> Dict[str, Dict[str, Any]]:
        """
        Load schemas from MediaPlanPy schema system.

        Args:
            schema_version: Version to load (e.g., 'v2.0')

        Returns:
            Dictionary containing schemas by type
        """
        schemas = {}
        schema_types = ['mediaplan', 'campaign', 'lineitem', 'dictionary']

        try:
            # Import MediaPlanPy schema components
            from mediaplanpy.schema import SchemaManager

            # Create schema manager instance
            schema_manager = SchemaManager()

            # Load each schema type
            for schema_type in schema_types:
                try:
                    schema_data = schema_manager.get_schema(schema_type, schema_version)
                    if schema_data:
                        schemas[schema_type] = schema_data
                        logger.debug(f"Loaded {schema_type} schema for {schema_version}")
                    else:
                        logger.warning(f"No {schema_type} schema found for {schema_version}")
                except Exception as e:
                    logger.error(f"Failed to load {schema_type} schema: {e}")
                    continue

            logger.info(f"Successfully loaded {len(schemas)} schemas for {schema_version}")
            return schemas

        except ImportError as e:
            logger.error(f"Failed to import MediaPlanPy schema components: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load schemas: {e}")
            return {}

    def _format_schemas_for_prompt(self, schemas: Dict[str, Dict[str, Any]], version: str) -> str:
        """
        Format schemas as markdown for system prompt inclusion.
        """
        if not schemas:
            return ""

        lines = []
        lines.append(f"# Media Plan Data Structure Schemas ({version})")
        lines.append("")
        lines.append(
            "The following JSON schemas define the data structures for media plans that you can create and manage:")
        lines.append("")

        # FIXED: Updated schema order and descriptions to include dictionary
        schema_info = {
            'mediaplan': {
                'title': 'Media Plan Schema',
                'description': 'Complete media plan structure including metadata, campaign, and line items'
            },
            'campaign': {
                'title': 'Campaign Schema',
                'description': 'Campaign-level information including objectives, budget, audience, and timeline'
            },
            'lineitem': {
                'title': 'Line Item Schema',
                'description': 'Individual media placement or buy within a campaign'
            },
            'dictionary': {
                'title': 'Dictionary Schema',
                'description': 'Standard dictionary values and enumerations used across media plan components'
            }
        }

        # Format each schema (updated order to include dictionary)
        for schema_type in ['mediaplan', 'campaign', 'lineitem', 'dictionary']:
            if schema_type not in schemas:
                continue

            schema_data = schemas[schema_type]
            info = schema_info[schema_type]

            lines.append(f"## {info['title']}")
            lines.append("")
            lines.append(info['description'])
            lines.append("")

            # Add required fields summary
            required_fields = schema_data.get('required', [])
            if required_fields:
                lines.append(f"**Required fields:** {', '.join(required_fields)}")
                lines.append("")

            # Add enum values for key fields if available
            enum_info = self._extract_enum_info(schema_data)
            if enum_info:
                lines.append("**Valid values for constrained fields:**")
                for field, values in enum_info.items():
                    lines.append(f"- `{field}`: {', '.join(values)}")
                lines.append("")

            # Add full schema as code block
            lines.append("**Full JSON Schema:**")
            lines.append("```json")
            lines.append(json.dumps(schema_data, indent=2))
            lines.append("```")
            lines.append("")

        # Add usage guidelines (updated for v2.0.0)
        lines.append("## Schema Usage Guidelines")
        lines.append("")
        lines.append("- All media plans must conform to the mediaplan schema")
        lines.append("- Use the campaign schema for campaign-level fields")
        lines.append("- Each line item must conform to the lineitem schema")
        lines.append("- Use the dictionary schema for standard enumeration values")
        lines.append("- Required fields must always be provided")
        lines.append("- Enum fields must use exact values from the valid options")
        lines.append("- Dates should be in YYYY-MM-DD format")
        lines.append("- Monetary values should be numbers (not strings)")
        lines.append("- For v2.0.0 features, refer to the updated schema specifications")
        lines.append("")

        return "\n".join(lines)

    def _extract_enum_info(self, schema: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Extract enum constraint information from schema.

        Args:
            schema: JSON schema dictionary

        Returns:
            Dictionary mapping field names to their enum values
        """
        enum_info = {}

        def extract_enums_recursive(obj, path=""):
            if isinstance(obj, dict):
                if 'enum' in obj:
                    field_name = path.split('.')[-1] if path else 'root'
                    enum_info[field_name] = obj['enum']

                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    extract_enums_recursive(value, new_path)
            elif isinstance(obj, list):
                for item in obj:
                    extract_enums_recursive(item, path)

        extract_enums_recursive(schema)
        return enum_info

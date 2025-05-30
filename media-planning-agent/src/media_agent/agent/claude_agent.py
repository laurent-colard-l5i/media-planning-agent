"""
Claude agent implementation for the media planning agent.

This module implements the Claude-specific agent using Anthropic's API
with full function calling support for tool execution.
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
from ..tools.base import get_tool_registry

logger = logging.getLogger(__name__)

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles date, datetime, and Decimal objects."""

    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

class ClaudeAgent(BaseAgent):
    """Claude-powered media planning agent with function calling support."""

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None,
                 system_prompt_path: Optional[str] = None):
        """
        Initialize Claude agent.

        Args:
            model_name: Claude model to use
            api_key: Anthropic API key (if not provided, will use environment variable)
            system_prompt_path: Path to system prompt markdown file (optional)

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

        # Load system prompt (external file or fallback to built-in)
        self.system_prompt = self._load_system_prompt(system_prompt_path)

        # Conversation history for Claude API
        self.conversation_history = []

        logger.info(f"Initialized Claude agent with model: {model_name}")

    def _load_system_prompt(self, custom_path: Optional[str] = None) -> str:
        """
        Load system prompt from external markdown file.

        Args:
            custom_path: Custom path to system prompt file

        Returns:
            System prompt content as string
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
                logger.info(f"Loaded system prompt from: {prompt_path}")
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
                    logger.debug(f"Added text content: {content_block.text[:100]}...")

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
                        logger.debug(f"Added follow-up text: {content_block.text[:100]}...")

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
        Execute a tool call from Claude.

        Args:
            tool_call: Claude tool call object

        Returns:
            Tool execution result
        """
        tool_name = tool_call.name
        tool_args = tool_call.input

        logger.debug(f"Executing tool: {tool_name} with args: {tool_args}")

        # Get tool from registry
        tool_registry = get_tool_registry()
        tool = tool_registry.get_tool(tool_name)

        if not tool:
            error_result = {
                "success": False,
                "error": f"Tool '{tool_name}' not found in registry",
                "available_tools": tool_registry.get_tool_names()
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
        tool_registry = get_tool_registry()
        return tool_registry.get_tool_schemas()

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

    def set_system_context(self, context: str) -> None:
        """
        Update the system prompt context.

        Args:
            context: Additional system context to append
        """
        self.system_prompt += f"\n\n## Additional Context\n{context}"
        logger.debug("Updated Claude system context")

    def reload_system_prompt(self, custom_path: Optional[str] = None) -> str:
        """
        Reload system prompt from file (useful for development).

        Args:
            custom_path: Custom path to system prompt file

        Returns:
            New system prompt content
        """
        old_prompt_length = len(self.system_prompt)
        self.system_prompt = self._load_system_prompt(custom_path)
        new_prompt_length = len(self.system_prompt)

        logger.info(f"Reloaded system prompt: {old_prompt_length} → {new_prompt_length} characters")
        return self.system_prompt

    def get_model_info(self) -> Dict[str, Any]:
        """Get detailed model information."""
        base_info = super().get_model_info()
        base_info.update({
            "api_version": "2023-06-01",  # Anthropic API version
            "context_length": 200000 if "claude-3" in self.model_name else 100000,
            "supports_images": "claude-3" in self.model_name,
            "supports_tool_calling": True,
            "system_prompt_length": len(self.system_prompt)
        })
        return base_info

    def reset_conversation(self) -> None:
        """Reset the conversation history while keeping session state."""
        logger.info("Resetting Claude conversation history")
        self.conversation_history = []

    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get statistics about the current conversation."""
        return {
            "total_messages": len(self.conversation_history),
            "user_messages": len([m for m in self.conversation_history if m["role"] == "user"]),
            "assistant_messages": len([m for m in self.conversation_history if m["role"] == "assistant"]),
            "estimated_tokens": sum(len(str(m["content"])) // 4 for m in self.conversation_history)
        }

    def export_conversation(self) -> Dict[str, Any]:
        """
        Export conversation for debugging or analysis.

        Returns:
            Dictionary with conversation data
        """
        return {
            "agent_info": self.get_model_info(),
            "session_info": self.get_session_info(),
            "conversation_history": self.conversation_history,
            "conversation_stats": self.get_conversation_stats(),
            "exported_at": self.session_state.last_activity.isoformat()
        }
"""
Claude agent implementation for the media planning agent.

This module implements the Claude-specific agent using Anthropic's API
with full function calling support for tool execution.
"""

import json
import os
from typing import Dict, Any, List, Optional, Union
import logging

try:
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from .base import BaseAgent, AgentConfigurationError, AgentCommunicationError
from ..tools.base import get_tool_registry

logger = logging.getLogger(__name__)


class ClaudeAgent(BaseAgent):
    """Claude-powered media planning agent with function calling support."""

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None):
        """
        Initialize Claude agent.

        Args:
            model_name: Claude model to use
            api_key: Anthropic API key (if not provided, will use environment variable)

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

        # Build system prompt
        self.system_prompt = self._build_system_prompt()

        # Conversation history for Claude API
        self.conversation_history = []

        logger.info(f"Initialized Claude agent with model: {model_name}")

    def _build_system_prompt(self) -> str:
        """Build the system prompt for Claude."""
        return """You are an expert media planning agent designed to help users create, manage, and optimize media plans using the MediaPlanPy SDK. You have access to various tools for workspace management and media plan operations.

## Your Role and Capabilities

**Core Expertise:**
- Strategic media planning consultation and best practices
- Budget allocation and channel mix recommendations  
- Campaign optimization and tactical media planning
- Media plan data structure and validation

**Available Tools:**
You have access to tools for:
- Workspace management (loading configurations, listing entities)
- Media plan CRUD operations (create, save, validate, delete, load)
- Line item creation and management
- Data analysis and querying

**Communication Style:**
- Be conversational and helpful
- Explain your reasoning for strategic recommendations
- Ask clarifying questions when needed to gather requirements
- Provide actionable advice and clear next steps
- Use emojis appropriately for status updates (✅ ❌ ⚠️ 📋)
- Structure responses clearly with key information highlighted

## Strategic Approach

**When helping users create media plans:**
1. **Understand the Brief**: Ask about business objectives, target audience, budget, timeline
2. **Strategic Consultation**: Recommend channel mix, budget allocation, targeting approach based on industry best practices
3. **Tactical Implementation**: Create the actual media plan with appropriate line items
4. **Validation & Optimization**: Ensure the plan meets requirements and suggest improvements

**Key Principles:**
- Always load a workspace before performing media plan operations
- Validate media plans before saving to ensure compliance
- Recommend realistic budget allocations based on industry knowledge
- Consider audience targeting and channel effectiveness
- Ensure date ranges and budgets are logical and consistent
- Think strategically about channel mix and budget allocation

## Important Workflow Notes
- Always start by loading a workspace using load_workspace
- Strategic context is maintained only during this conversation session
- When loading existing media plans, ask users for context since I won't have the previous strategic reasoning
- Use the available tools - don't make up data or operations
- Validate media plans before saving them
- Provide clear next steps after each major operation

## Budget Allocation Best Practices
When recommending budget allocation across channels:
- Digital channels (Search, Social, Display): 60-80% for most campaigns
- Search advertising: 25-40% for conversion-focused campaigns
- Social media: 20-35% for awareness and engagement
- Display/Video: 15-25% for reach and retargeting
- Traditional media: 20-40% depending on audience and objectives
- Always leave 5-10% buffer for optimization and testing

## Channel Recommendations by Objective
- **Awareness**: Social media, Display, Video, OOH
- **Consideration**: Search, Social, Content marketing
- **Conversion**: Search, Social (retargeting), Email
- **Retention**: Email, Social, Direct mail

Remember: Your goal is to make media planning more efficient and strategic through intelligent assistance and automation. Always use your tools effectively and provide strategic value beyond just technical operations."""

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

            # Make initial API call
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=self.conversation_history,
                tools=tools
            )

            response_text = ""
            tool_calls_made = []

            # Process response content
            for content_block in response.content:
                if content_block.type == "text":
                    response_text += content_block.text
                elif content_block.type == "tool_use":
                    # Execute tool and collect results
                    tool_result = self._execute_tool(content_block)
                    tool_calls_made.append({
                        "tool_name": content_block.name,
                        "result": tool_result
                    })

            # If tools were called, we need to continue the conversation
            if tool_calls_made:
                # Add assistant message with tool calls to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Add tool results to history
                for i, content_block in enumerate(response.content):
                    if content_block.type == "tool_use":
                        self.conversation_history.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps(tool_calls_made[i]["result"])
                            }]
                        })

                # Get follow-up response after tool execution
                follow_up_response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt,
                    messages=self.conversation_history,
                    tools=tools
                )

                # Extract text from follow-up response
                follow_up_text = ""
                for content_block in follow_up_response.content:
                    if content_block.type == "text":
                        follow_up_text += content_block.text

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

            return response_text or "I executed some tools but didn't provide a text response."

        except Exception as e:
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

    def get_model_info(self) -> Dict[str, Any]:
        """Get detailed model information."""
        base_info = super().get_model_info()
        base_info.update({
            "api_version": "2023-06-01",  # Anthropic API version
            "context_length": 200000 if "claude-3" in self.model_name else 100000,
            "supports_images": "claude-3" in self.model_name,
            "supports_tool_calling": True
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
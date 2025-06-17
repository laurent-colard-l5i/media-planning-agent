#!/usr/bin/env python3
"""
Standalone Agent Debugger for Media Planning Agent
Place this file in your project root (same level as src/ directory)

Usage:
1. Set breakpoints in the debug scenario functions below
2. Run: python standalone_agent_debugger.py
3. Choose a scenario and step through with your IDE debugger

This bypasses the CLI Rich console that interferes with IDE debugging.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import codecs
import ctypes


# Add src to Python path so we can import the agent
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

print(f"🔍 Standalone Agent Debugger")
print(f"Project root: {project_root}")
print(f"Source path: {src_path}")

# Verify imports work
try:
    from media_agent.agent import create_agent, SessionState
    from media_agent.tools import get_tool_registry

    print("✅ Successfully imported agent components")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    # Find .env file - it should be in the project root
    project_root = Path(__file__).parent
    env_file = project_root / ".env"

    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Loaded environment variables from: {env_file}")

        # Verify the workspace path was loaded
        workspace_path = os.getenv('MEDIAPLANPY_WORKSPACE_PATH')
        if workspace_path:
            print(f"📍 MEDIAPLANPY_WORKSPACE_PATH: {workspace_path}")
        else:
            print("⚠️ MEDIAPLANPY_WORKSPACE_PATH not found in .env file")
    else:
        print(f"⚠️ .env file not found at: {env_file}")
        print("Environment variables will not be automatically loaded")

except ImportError:
    print("⚠️ python-dotenv not available. Install with: pip install python-dotenv")
except Exception as e:
    print(f"⚠️ Failed to load .env file: {e}")


class SafeConsoleHandler(logging.StreamHandler):
    """Console handler that safely handles Unicode characters on Windows."""

    def emit(self, record):
        """Emit a record, handling Unicode encoding errors gracefully."""
        try:
            super().emit(record)
        except UnicodeEncodeError:
            # If Unicode encoding fails, sanitize the message and try again
            try:
                msg = self.format(record)
                safe_msg = self._sanitize_unicode(msg)
                self.stream.write(safe_msg + self.terminator)
                self.flush()
            except Exception:
                # Last resort: just print a safe error message
                try:
                    self.stream.write("[LOGGING ERROR: Unicode encoding failed]\n")
                    self.flush()
                except:
                    pass  # Give up gracefully

    def _sanitize_unicode(self, text: str) -> str:
        """Replace Unicode characters that can't be encoded safely."""
        # Common emoji replacements for Windows console
        replacements = {
            '✅': '[OK]',
            '❌': '[FAIL]',
            '⚠️': '[WARN]',
            '📋': '[INFO]',
            '🎯': '[TARGET]',
            '💰': '[MONEY]',
            '📊': '[CHART]',
            '🗂️': '[FOLDER]',
            '🔧': '[TOOL]',
            '⏱️': '[TIME]',
            '🤖': '[AGENT]',
            '💬': '[CHAT]',
            '🔍': '[SEARCH]',
            '📝': '[NOTE]',
            '🚀': '[START]',
            '🎉': '[SUCCESS]'
        }

        # Replace known problematic characters
        safe_text = text
        for unicode_char, replacement in replacements.items():
            safe_text = safe_text.replace(unicode_char, replacement)

        # Replace any remaining non-ASCII characters that cause issues
        try:
            safe_text.encode('cp1252')
            return safe_text
        except UnicodeEncodeError:
            return safe_text.encode('cp1252', errors='replace').decode('cp1252')


def configure_windows_console():
    """Configure Windows console for better Unicode support."""
    if sys.platform == "win32":
        try:
            # Try to enable UTF-8 mode in Windows console
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')

            # Set console code page to UTF-8 if possible
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleCP(65001)  # UTF-8 code page
                kernel32.SetConsoleOutputCP(65001)
            except:
                pass  # Not critical if this fails

        except Exception:
            pass  # Not critical if this fails

class StandaloneAgentDebugger:
    """
    Standalone debugger that bypasses CLI for IDE debugging.
    """

    def __init__(self, debug_output_dir: str = "debug_output"):
        self.debug_output_dir = Path(debug_output_dir)
        self.debug_output_dir.mkdir(exist_ok=True)

        self.agent = None
        self.session_id = None
        self.debug_log = []

        # Setup logging to both file and console
        self._setup_debug_logging()

        print(f"📊 Debug output directory: {self.debug_output_dir.absolute()}")

    def _setup_debug_logging(self):
        """Setup detailed logging for debugging with Unicode safety"""

        # Configure Windows console first
        configure_windows_console()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.debug_output_dir / f"{timestamp}_debug_log.log"

        # Create logger
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # File handler with UTF-8 encoding and error handling
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8', errors='replace')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")

        # Safe console handler with Unicode error handling
        console_handler = SafeConsoleHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)  # Less verbose on console
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # Reduce noise from external libraries
        logging.getLogger('anthropic').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)

        print(f"📝 Safe debug logging setup: {log_file}")

    def initialize_agent(self, provider: str = "claude", model: str = None,
                         api_key: str = None, workspace_path: str = None) -> bool:
        """
        Initialize the agent for debugging.

        Args:
            provider: AI provider (default: claude)
            model: Model name (optional, uses default)
            api_key: API key (optional, will use env var)
            workspace_path: Workspace path for auto-loading

        Returns:
            True if initialization successful
        """
        print(f"\n🚀 Initializing agent...")
        print(f"   Provider: {provider}")
        print(f"   Model: {model or 'default'}")
        print(f"   Workspace: {workspace_path or 'none'}")

        # Set API key if provided
        if api_key:
            if provider == "claude":
                os.environ['ANTHROPIC_API_KEY'] = api_key
                print(f"   ✅ API key set from parameter")

        # Check if API key is available
        if provider == "claude" and not os.getenv('ANTHROPIC_API_KEY'):
            print(f"   ⚠️  ANTHROPIC_API_KEY not found in environment")
            print(f"      Set it with: export ANTHROPIC_API_KEY=your_key_here")
            print(f"      Or pass it as api_key parameter")
            return False

        try:
            # Create agent with debugging info
            print(f"   🤖 Creating agent...")
            self.agent = create_agent(provider=provider, model_name=model)

            # Validate configuration
            print(f"   🔧 Validating configuration...")
            self.agent.validate_configuration()

            # Generate session ID
            self.session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_debug"

            print(f"✅ Agent initialized successfully!")
            print(f"   Provider: {self.agent.provider_name}")
            print(f"   Model: {self.agent.model_name}")
            print(f"   Function calling: {self.agent.supports_function_calling}")
            print(f"   Session ID: {self.session_id}")

            # Auto-load workspace if provided
            if workspace_path:
                print(f"\n🗂️  Auto-loading workspace...")
                self.load_workspace(workspace_path)

            return True

        except Exception as e:
            print(f"❌ Failed to initialize agent: {e}")
            logging.error(f"Agent initialization failed: {e}", exc_info=True)
            return False

    def load_workspace(self, workspace_path: str) -> Dict[str, Any]:
        """
        Load workspace with debugging.

        🔴 SET BREAKPOINT HERE to debug workspace loading
        """
        print(f"\n{'=' * 60}")
        print(f"DEBUGGING: load_workspace")
        print(f"{'=' * 60}")
        print(f"Workspace path: {workspace_path}")

        # 🔴 BREAKPOINT: Set breakpoint on the next line to step into tool execution
        result = self._debug_tool_execution("load_workspace", workspace_path=workspace_path)

        print(f"\nWorkspace loading result:")
        print(f"Success: {result.get('success', 'Unknown')}")
        print(f"Message: {result.get('message', 'No message')}")

        if result.get('success'):
            workspace_info = result.get('workspace_info', {})
            print(f"Workspace name: {workspace_info.get('name', 'Unknown')}")
            print(f"Environment: {workspace_info.get('environment', 'Unknown')}")
            print(f"Storage mode: {workspace_info.get('storage_mode', 'Unknown')}")

        return result

    def create_media_plan(self, campaign_name: str, campaign_objective: str,
                          start_date: str, end_date: str, budget_total: float,
                          created_by: str, **kwargs) -> Dict[str, Any]:
        """
        Create media plan with debugging.

        🔴 SET BREAKPOINT HERE to debug media plan creation
        """
        print(f"\n{'=' * 60}")
        print(f"DEBUGGING: create_mediaplan_basic")
        print(f"{'=' * 60}")
        print(f"Campaign: {campaign_name}")
        print(f"Objective: {campaign_objective}")
        print(f"Budget: ${budget_total:,.2f}")
        print(f"Timeline: {start_date} to {end_date}")
        print(f"Created by: {created_by}")

        # 🔴 BREAKPOINT: Set breakpoint on the next line to step into tool execution
        result = self._debug_tool_execution(
            "create_mediaplan_basic",
            campaign_name=campaign_name,
            campaign_objective=campaign_objective,
            start_date=start_date,
            end_date=end_date,
            budget_total=budget_total,
            created_by=created_by,
            **kwargs
        )

        print(f"\nMedia plan creation result:")
        print(f"Success: {result.get('success', 'Unknown')}")
        print(f"Message: {result.get('message', 'No message')}")

        if result.get('success'):
            campaign_info = result.get('campaign_info', {})
            print(f"Media plan ID: {campaign_info.get('media_plan_id', 'Unknown')}")
            print(f"Campaign ID: {campaign_info.get('campaign_id', 'Unknown')}")

        return result

    def create_line_items(self, line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create line items with debugging.

        🔴 SET BREAKPOINT HERE to debug line item creation
        """
        print(f"\n{'=' * 60}")
        print(f"DEBUGGING: create_lineitem")
        print(f"{'=' * 60}")
        print(f"Line items count: {len(line_items)}")

        total_cost = sum(item.get('cost_total', 0) for item in line_items)
        print(f"Total cost: ${total_cost:,.2f}")

        for i, item in enumerate(line_items):
            print(f"  {i + 1}. {item.get('name', 'Unnamed')}: ${item.get('cost_total', 0):,.2f}")
            print(f"     Channel: {item.get('channel', 'Not specified')}")
            print(f"     Vehicle: {item.get('vehicle', 'Not specified')}")

        # 🔴 BREAKPOINT: Set breakpoint on the next line to step into tool execution
        result = self._debug_tool_execution("create_lineitem", line_items=line_items)

        print(f"\nLine item creation result:")
        print(f"Success: {result.get('success', 'Unknown')}")
        print(f"Message: {result.get('message', 'No message')}")

        if result.get('success'):
            created_count = result.get('created_count', 0)
            budget_summary = result.get('budget_summary', {})
            print(f"Created {created_count} line items")
            print(f"Remaining budget: ${budget_summary.get('remaining_budget', 0):,.2f}")

        return result

    def list_media_plans(self, include_stats: bool = True, limit: int = None) -> Dict[str, Any]:
        """
        List media plans with debugging.

        🔴 SET BREAKPOINT HERE to debug media plan listing
        """
        print(f"\n{'=' * 60}")
        print(f"DEBUGGING: list_mediaplans")
        print(f"{'=' * 60}")
        print(f"Include stats: {include_stats}")
        print(f"Limit: {limit}")

        # 🔴 BREAKPOINT: Set breakpoint on the next line to step into tool execution
        result = self._debug_tool_execution(
            "list_mediaplans",
            include_stats=include_stats,
            limit=limit
        )

        print(f"\nMedia plans listing result:")
        print(f"Success: {result.get('success', 'Unknown')}")
        print(f"Count: {result.get('count', 0)}")

        if result.get('success') and result.get('media_plans'):
            for i, plan in enumerate(result['media_plans']):
                print(f"  {i + 1}. {plan.get('name', 'Unnamed')} (ID: {plan.get('id', 'Unknown')})")
                print(f"     Budget: ${plan.get('budget', 0):,.2f}")
                print(f"     Created: {plan.get('created_at', 'Unknown')}")

        return result

    def save_media_plan(self, include_strategic_summary: bool = True) -> Dict[str, Any]:
        """
        Save media plan with debugging.

        🔴 SET BREAKPOINT HERE to debug media plan saving
        """
        print(f"\n{'=' * 60}")
        print(f"DEBUGGING: save_mediaplan")
        print(f"{'=' * 60}")
        print(f"Include strategic summary: {include_strategic_summary}")

        # 🔴 BREAKPOINT: Set breakpoint on the next line to step into tool execution
        result = self._debug_tool_execution(
            "save_mediaplan",
            include_strategic_summary=include_strategic_summary
        )

        print(f"\nMedia plan saving result:")
        print(f"Success: {result.get('success', 'Unknown')}")
        print(f"Message: {result.get('message', 'No message')}")

        if result.get('success'):
            save_info = result.get('save_info', {})
            print(f"Saved to: {save_info.get('saved_path', 'Unknown')}")

        return result

    def chat_with_agent(self, message: str, use_tools: bool = True) -> str:
        """Send message to agent with debugging."""
        self.safe_print(f"\n{'=' * 60}")
        self.safe_print(f"DEBUGGING: Agent Chat")
        self.safe_print(f"{'=' * 60}")
        self.safe_print(f"User message: {message}")
        self.safe_print(f"Use tools: {use_tools}")

        if not self.agent:
            self.safe_print("❌ Agent not initialized")
            return "Agent not initialized"

        try:
            start_time = datetime.now()

            # Log session state before chat
            self.safe_print(f"\n📊 Session state before chat:")
            self._inspect_session_state_brief()

            response = self.agent.chat(message, use_tools=use_tools)

            execution_time = (datetime.now() - start_time).total_seconds()

            # Log session state after chat
            self.safe_print(f"\n📊 Session state after chat:")
            self._inspect_session_state_brief()

            self.safe_print(f"\n⏱️  Execution time: {execution_time:.3f}s")
            # Truncate long responses for console display
            if len(response) > 200:
                display_response = response[:200] + "..."
            else:
                display_response = response
            self.safe_print(f"🤖 Agent response: {display_response}")

            return response

        except Exception as e:
            self.safe_print(f"❌ Chat failed: {e}")
            logging.error(f"Chat failed: {e}", exc_info=True)
            return f"Error: {e}"

    def _debug_tool_execution(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool with detailed debugging.

        This is where the actual tool execution happens.
        You can step into this to see how tools are called.
        """
        if not self.agent:
            return {"success": False, "error": "Agent not initialized"}

        print(f"\n🔧 Executing tool: {tool_name}")
        print(f"📝 Arguments: {json.dumps(kwargs, indent=2, default=str)}")

        try:
            # Log session state before tool execution
            print(f"\n📊 Session state before {tool_name}:")
            self._inspect_session_state_brief()

            # Get tool registry
            if hasattr(self.agent, 'tool_registry'):
                registry = self.agent.tool_registry
            else:
                registry = get_tool_registry()

            # Get tool
            tool = registry.get_tool(tool_name)
            if not tool:
                return {"success": False, "error": f"Tool '{tool_name}' not found"}

            print(f"✅ Found tool: {tool_name}")

            # 🔴 BREAKPOINT: This is where the tool actually executes
            # Step into this line to see the tool implementation
            start_time = datetime.now()
            result = tool.execute(self.agent.session_state, **kwargs)
            execution_time = (datetime.now() - start_time).total_seconds()

            # Log session state after tool execution
            print(f"\n📊 Session state after {tool_name}:")
            self._inspect_session_state_brief()

            print(f"\n⏱️  Tool execution time: {execution_time:.3f}s")
            print(f"✅ Tool success: {result.get('success', 'Unknown')}")

            # Log execution details
            self._log_tool_execution(tool_name, kwargs, result, execution_time)

            return result

        except Exception as e:
            print(f"❌ Tool execution failed: {e}")
            logging.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _inspect_session_state_brief(self):
        """Quick inspection of session state"""
        if not self.agent or not hasattr(self.agent, 'session_state'):
            print("   No session state available")
            return

        session_state = self.agent.session_state
        print(f"   Workspace loaded: {session_state.workspace_manager is not None}")
        print(f"   Media plan loaded: {session_state.current_mediaplan is not None}")
        print(f"   Conversation turns: {len(session_state.conversation_history)}")

        if session_state.current_mediaplan:
            try:
                plan = session_state.current_mediaplan
                budget = float(plan.campaign.budget_total)
                total_cost = sum(float(li.cost_total) for li in plan.lineitems)
                print(f"   Media plan: {plan.campaign.name} (${budget:,.2f} budget, ${total_cost:,.2f} allocated)")
            except:
                print(f"   Media plan: Error getting details")

    def _log_tool_execution(self, tool_name: str, args: Dict[str, Any],
                            result: Dict[str, Any], execution_time: float):
        """Log tool execution details"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'tool_name': tool_name,
            'arguments': args,
            'result': result,
            'execution_time_seconds': execution_time,
            'success': result.get('success', False)
        }

        self.debug_log.append(log_entry)

        # Save to file
        debug_file = self.debug_output_dir / f"{self.session_id}_tool_execution.json"
        with open(debug_file, 'w') as f:
            json.dump(self.debug_log, f, indent=2, default=str)

    def inspect_session_state_detailed(self):
        """Detailed inspection of session state - call this when you need full details"""
        print(f"\n{'=' * 60}")
        print(f"DETAILED SESSION STATE INSPECTION")
        print(f"{'=' * 60}")

        if not self.agent:
            print("❌ Agent not initialized")
            return

        session_state = self.agent.session_state

        print(f"Session ID: {session_state.session_id}")
        print(f"Created at: {session_state.created_at}")
        print(f"Last activity: {session_state.last_activity}")

        # Workspace information
        print(f"\n🗂️  Workspace Details:")
        if session_state.workspace_manager:
            try:
                config = session_state.workspace_manager.get_resolved_config()
                print(f"   Name: {config.get('workspace_name', 'Unknown')}")
                print(f"   Environment: {config.get('environment', 'Unknown')}")
                print(f"   Storage mode: {config.get('storage', {}).get('mode', 'Unknown')}")
                print(f"   Database enabled: {config.get('database', {}).get('enabled', False)}")
            except Exception as e:
                print(f"   Error getting config: {e}")
        else:
            print(f"   ❌ No workspace loaded")

        # Media plan information
        print(f"\n📊 Media Plan Details:")
        if session_state.current_mediaplan:
            try:
                plan = session_state.current_mediaplan
                print(f"   ID: {plan.meta.id}")
                print(f"   Campaign: {plan.campaign.name}")
                print(f"   Objective: {plan.campaign.objective}")
                print(f"   Budget: ${float(plan.campaign.budget_total):,.2f}")
                print(f"   Timeline: {plan.campaign.start_date} to {plan.campaign.end_date}")
                print(f"   Line items: {len(plan.lineitems)}")

                if plan.lineitems:
                    total_cost = sum(float(li.cost_total) for li in plan.lineitems)
                    remaining = float(plan.campaign.budget_total) - total_cost
                    print(f"   Allocated: ${total_cost:,.2f}")
                    print(f"   Remaining: ${remaining:,.2f}")

                    print(f"\n   Line Items:")
                    for i, li in enumerate(plan.lineitems, 1):
                        print(f"     {i}. {li.name}: ${float(li.cost_total):,.2f}")
                        if hasattr(li, 'channel') and li.channel:
                            print(f"        Channel: {li.channel}")
                        if hasattr(li, 'vehicle') and li.vehicle:
                            print(f"        Vehicle: {li.vehicle}")

            except Exception as e:
                print(f"   Error getting plan details: {e}")
        else:
            print(f"   ❌ No media plan loaded")

        # Strategic context
        print(f"\n🎯 Strategic Context:")
        if session_state.strategic_context:
            context = session_state.strategic_context
            if context.business_context:
                print(
                    f"   Business context: {context.business_context[:100]}{'...' if len(context.business_context) > 100 else ''}")
            if context.objectives:
                print(f"   Objectives: {context.objectives}")
            if context.channel_preferences:
                print(f"   Channel preferences: {context.channel_preferences}")
            if context.budget_info:
                print(f"   Budget info: {context.budget_info}")
        else:
            print(f"   ❌ No strategic context")

        # Conversation history
        print(f"\n💬 Conversation History:")
        print(f"   Total turns: {len(session_state.conversation_history)}")
        if session_state.conversation_history:
            latest = session_state.conversation_history[-1]
            print(f"   Latest timestamp: {latest.get('timestamp', 'No timestamp')}")
            print(
                f"   Latest user input: {latest.get('user', 'No input')[:100]}{'...' if len(latest.get('user', '')) > 100 else ''}")

    def safe_print(self, message: str):
        """Safely print messages, handling Unicode encoding issues."""
        try:
            print(message)
        except UnicodeEncodeError:
            # Create a temporary safe handler to sanitize
            safe_handler = SafeConsoleHandler()
            safe_message = safe_handler._sanitize_unicode(message)
            print(safe_message)


def run_debug_scenario_basic_workflow():
    """
    Debug scenario: Basic workspace and media plan creation

    🔴 SET BREAKPOINTS in this function to debug the complete workflow
    """
    print("🧪 DEBUG SCENARIO: Basic Workflow")
    print("=" * 60)

    debugger = StandaloneAgentDebugger()

    # 🔴 BREAKPOINT: Set breakpoint here to debug agent initialization
    print("\n1. Initializing agent...")
    if not debugger.initialize_agent(provider="claude"):
        print("❌ Failed to initialize agent. Check your API key.")
        return

    # 🔴 BREAKPOINT: Set breakpoint here to debug workspace loading
    print("\n2. Loading workspace...")
    workspace_result = debugger.load_workspace("C:\mediaplanpy\workspace_c990700e_settings.json")

    if not workspace_result.get('success'):
        print("⚠️  Workspace loading failed, but continuing...")
        print("   You may need to create a test workspace or adjust the path")

    # 🔴 BREAKPOINT: Set breakpoint here to debug media plan creation
    print("\n3. Creating media plan...")
    mediaplan_result = debugger.create_media_plan(
        campaign_name="Summer Fitness Campaign - Debug Test",
        campaign_objective="awareness",
        start_date="2025-07-01",
        end_date="2025-09-30",
        budget_total=100000.0,
        created_by="debug@example.com"
    )

    if not mediaplan_result.get('success'):
        print("❌ Media plan creation failed. Check the error details above.")
        return

    # 🔴 BREAKPOINT: Set breakpoint here to debug line item creation
    print("\n4. Creating line items...")
    line_items = [
        {
            "name": "Facebook Video Campaign - Debug",
            "start_date": "2025-07-01",
            "end_date": "2025-09-30",
            "cost_total": 40000,
            "channel": "Social",
            "vehicle": "Facebook"
        },
        {
            "name": "Google Search Campaign - Debug",
            "start_date": "2025-07-01",
            "end_date": "2025-09-30",
            "cost_total": 35000,
            "channel": "Search",
            "vehicle": "Google Ads"
        }
    ]

    lineitem_result = debugger.create_line_items(line_items)

    if not lineitem_result.get('success'):
        print("❌ Line item creation failed. Check the error details above.")
        return

    # 🔴 BREAKPOINT: Set breakpoint here to debug media plan saving
    print("\n5. Saving media plan...")
    save_result = debugger.save_media_plan()

    # 🔴 BREAKPOINT: Set breakpoint here to debug media plan listing
    print("\n6. Listing media plans...")
    list_result = debugger.list_media_plans()

    # 🔴 BREAKPOINT: Set breakpoint here to inspect final state
    print("\n7. Final inspection...")
    debugger.inspect_session_state_detailed()

    print("\n✅ Debug scenario completed!")
    print(f"Debug files saved to: {debugger.debug_output_dir}")


def run_debug_scenario_conversation():
    """
    Debug scenario: Agent conversation flow

    🔴 SET BREAKPOINTS in this function to debug conversation handling
    """
    print("🧪 DEBUG SCENARIO: Agent Conversation")
    print("=" * 60)

    debugger = StandaloneAgentDebugger()

    # 🔴 BREAKPOINT: Set breakpoint here to debug agent initialization
    print("\n1. Initializing agent...")
    if not debugger.initialize_agent(provider="claude"):
        print("❌ Failed to initialize agent. Check your API key.")
        return

    # 🔴 BREAKPOINT: Set breakpoint here to debug each conversation turn
    print("\n2. Testing conversation flow...")

    # workspace_tools.load_workspace

    # response1 = debugger.chat_with_agent("Load my workspace from C:\mediaplanpy\workspace_c990700e_settings.json")
    # response1 = debugger.chat_with_agent("load workspace workspace_c990700e")
    response1 = debugger.chat_with_agent("load workspace")
    print(f"\nResponse 1: {response1[:200]}{'...' if len(response1) > 200 else ''}")

    # workspace_tools.list_mediaplans

    # response2 = debugger.chat_with_agent("List all media plans")
    # response2 = debugger.chat_with_agent("List media plans with a budget greater than $100k")
    # print(f"\nResponse 2: {response2[:200]}{'...' if len(response2) > 200 else ''}")

    # workspace_tools.list_campaigns

    # response3 = debugger.chat_with_agent("List my campaigns")
    # response3 = debugger.chat_with_agent("List campaigns starting in Q3 25")
    # print(f"\nResponse 3: {response3[:200]}{'...' if len(response3) > 200 else ''}")

    # workspace_tools.get_workspace_info

    # response4 = debugger.chat_with_agent("How is my workspace configured")
    # print(f"\nResponse 4: {response4[:200]}{'...' if len(response4) > 200 else ''}")

    # mediaplan_tools.load_mediaplan

    # response5 = debugger.chat_with_agent("Load media plan mediaplan_bfde4972")
    # print(f"\nResponse 5: {response5[:200]}{'...' if len(response5) > 200 else ''}")

    # workspace_tools.validate_mediaplan
    # LOGICAL ISSUE: This method requires a media plan to be loaded which itself validates the media plan
    # Either we should deprecate this Tool or make it a media plan-level tool

    # response6 = debugger.chat_with_agent("Validate this media plan")
    # print(f"\nResponse 5: {response6[:200]}{'...' if len(response6) > 200 else ''}")

    # mediaplan_tools.create_mediaplan

    response7 = debugger.chat_with_agent("I am planning a campaign in Q325 which will be targeting car purchasers in the 10 largest States in the US by Population, with a total budget of $250,000, with the objective to drive awareness and consideration. Please assign a name and a description based on this brief. My name is Laurent Colard and my agency name is Level5i")
    print(f"\nResponse 7: {response7[:200]}{'...' if len(response7) > 200 else ''}")

    # mediaplan_tools.create_lineitem

    # response8 = debugger.chat_with_agent("Add line items by channel and by State with your recommended budget allocation, taking State-level population in consideration. Please include an estimated cost breakdown and estimated performance in terms of impressions, clicks and views wherever possible.")
    # print(f"\nResponse 8: {response8[:200]}{'...' if len(response8) > 200 else ''}")

    # mediaplan_tools.save_mediaplan

    response9 = debugger.chat_with_agent("Save this media plan")
    print(f"\nResponse 9: {response9[:200]}{'...' if len(response9) > 200 else ''}")

    # mediaplan_tools.delete_mediaplan

    response10 = debugger.chat_with_agent("Delete media plan mediaplan_61d045ed")
    print(f"\nResponse 10: {response10[:200]}{'...' if len(response10) > 200 else ''}")


    # 🔴 BREAKPOINT: Set breakpoint here to inspect final conversation state
    print("\n3. Final inspection...")
    debugger.inspect_session_state_detailed()

    print("\n✅ Conversation debug scenario completed!")
    print(f"Debug files saved to: {debugger.debug_output_dir}")


def run_debug_scenario_tool_isolation():
    """
    Debug scenario: Test individual tools in isolation

    🔴 SET BREAKPOINTS in this function to debug specific tools
    """
    print("🧪 DEBUG SCENARIO: Tool Isolation Testing")
    print("=" * 60)

    debugger = StandaloneAgentDebugger()

    # 🔴 BREAKPOINT: Set breakpoint here
    print("\n1. Initializing agent...")
    if not debugger.initialize_agent(provider="claude"):
        return

    # Test each tool individually
    tools_to_test = [
        ("load_workspace", {"workspace_path": "C:\mediaplanpy\workspace_c990700e_settings.json"}),
        ("list_mediaplans", {"include_stats": True}),
        ("get_workspace_info", {}),
    ]

    for tool_name, tool_args in tools_to_test:
        print(f"\n🔧 Testing tool: {tool_name}")
        print(f"Arguments: {tool_args}")

        # 🔴 BREAKPOINT: Set breakpoint here to debug each tool individually
        result = debugger._debug_tool_execution(tool_name, **tool_args)

        print(f"Result success: {result.get('success', 'Unknown')}")
        print(f"Result message: {result.get('message', 'No message')[:100]}")

        # Inspect session state after each tool
        debugger._inspect_session_state_brief()

    print("\n✅ Tool isolation testing completed!")


if __name__ == "__main__":
    print("🔍 STANDALONE AGENT DEBUGGER")
    print("=" * 60)
    print("This debugger bypasses the CLI Rich console to enable IDE debugging.")
    print("Set breakpoints in the scenario functions and step through the code.")
    print()
    print("Available scenarios:")
    print("1. Basic workflow (workspace → media plan → line items → save)")
    print("2. Agent conversation flow")
    print("3. Tool isolation testing")
    print("4. Exit")

    while True:
        try:
            choice = input("\nEnter choice (1-4): ").strip()

            if choice == "1":
                print(f"\n🔴 SET BREAKPOINTS in run_debug_scenario_basic_workflow() function")
                print(f"Then press F5 or your IDE's debug button")
                input("Press Enter when ready...")
                run_debug_scenario_basic_workflow()

            elif choice == "2":
                # print(f"\n🔴 SET BREAKPOINTS in run_debug_scenario_conversation() function")
                # print(f"Then press F5 or your IDE's debug button")
                # input("Press Enter when ready...")
                run_debug_scenario_conversation()

            elif choice == "3":
                print(f"\n🔴 SET BREAKPOINTS in run_debug_scenario_tool_isolation() function")
                print(f"Then press F5 or your IDE's debug button")
                input("Press Enter when ready...")
                run_debug_scenario_tool_isolation()

            elif choice == "4":
                print("👋 Goodbye!")
                break

            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            logging.error(f"Main loop error: {e}", exc_info=True)
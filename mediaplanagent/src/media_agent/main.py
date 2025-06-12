"""
Main CLI interface for the media planning agent.

This module provides the command-line interface for interacting with
the media planning agent, supporting different AI providers and models.
"""

import click
import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Confirm
from dotenv import load_dotenv
import logging

from .agent import create_agent, get_available_providers, get_default_models, AgentConfigurationError
from .tools import get_tool_info, list_tools_by_category

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('media_agent.log'),
        logging.StreamHandler()
    ]
)

# Suppress some verbose logs
logging.getLogger('anthropic').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

console = Console()
logger = logging.getLogger(__name__)


def display_welcome_message(provider: str, model: str):
    """Display welcome message with agent information."""
    welcome_text = Text()
    welcome_text.append("🎯 Media Planning Agent - MVP Phase 1\n", style="bold blue")
    welcome_text.append(f"Powered by {provider.title()} ({model})\n\n", style="italic cyan")
    welcome_text.append("I can help you create and manage media plans using the MediaPlanPy SDK.\n\n")
    welcome_text.append("Available capabilities:\n", style="bold")
    welcome_text.append("• Load and manage MediaPlanPy workspaces\n")
    welcome_text.append("• Create media plans with strategic consultation\n")
    welcome_text.append("• Add line items with intelligent recommendations\n")
    welcome_text.append("• Save, validate, and manage media plans\n")
    welcome_text.append("• Query and analyze media plan data\n\n")
    welcome_text.append("💡 ", style="yellow")
    welcome_text.append("Start by saying 'load my workspace' or 'help me create a media plan'\n")
    welcome_text.append("Type 'quit', 'exit', or 'q' to exit.\n", style="italic dim")

    console.print(Panel(welcome_text, title="Welcome", border_style="blue"))


def display_tool_info():
    """Display information about available tools."""
    tool_info = get_tool_info()
    tools_by_category = list_tools_by_category()

    table = Table(title="Available Tools", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Tools", style="green")
    table.add_column("Count", justify="right", style="yellow")

    for category, count in tool_info["categories"].items():
        tools_in_category = tools_by_category["tools_by_category"][category]
        tools_str = ", ".join(tools_in_category)
        table.add_row(category.title(), tools_str, str(count))

    console.print(table)
    console.print(f"\nTotal tools available: {tool_info['total_tools']}\n")


def handle_startup_error(error: Exception, provider: str) -> None:
    """Handle errors during agent startup."""
    console.print(f"❌ Failed to initialize {provider} agent", style="red")

    if "API key" in str(error):
        console.print("\n🔑 API Key Issue:", style="yellow")
        if provider.lower() == "claude":
            console.print("Please set your Anthropic API key:")
            console.print("export ANTHROPIC_API_KEY=your_key_here")
            console.print("Or add it to your .env file")
        else:
            console.print(f"Please set your {provider.upper()} API key in environment variables")
    else:
        console.print(f"\n📋 Error details: {error}", style="red")

    console.print("\n🛠️  Troubleshooting:", style="blue")
    console.print("1. Check your API key is valid and has sufficient credits")
    console.print("2. Verify your internet connection")
    console.print("3. Try a different model if available")


@click.command()
@click.option('--provider', '-p',
              default='claude',
              type=click.Choice(['claude'], case_sensitive=False),  # Only Claude for Phase 1
              help='AI provider to use (currently only Claude is supported)')
@click.option('--model', '-m',
              help='Specific model to use (optional, uses provider default)')
@click.option('--workspace', '-w',
              help='Path to MediaPlanPy workspace configuration file')
@click.option('--info', is_flag=True,
              help='Enable info logging')
@click.option('--debug', is_flag=True,
              help='Enable debug logging')
@click.option('--tools-info', is_flag=True,
              help='Show available tools and exit')
def cli(provider: str, model: str, workspace: str, info: bool, debug: bool, tools_info: bool):
    """Interactive Media Planning Agent - Create and manage media plans with AI assistance."""

    # Set logging levels based on flags
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        console.print("🐛 Debug logging enabled", style="yellow")
    elif info:
        logging.getLogger().setLevel(logging.INFO)
        console.print("ℹ️ Info logging enabled", style="cyan")

    # Show tools info and exit if requested
    if tools_info:
        display_tool_info()
        return

    # Validate provider
    available_providers = get_available_providers()
    if provider.lower() not in available_providers:
        console.print(f"❌ Provider '{provider}' not available", style="red")
        console.print(f"Available providers: {', '.join(available_providers)}")
        return

    # Get default model if not specified
    if not model:
        defaults = get_default_models()
        model = defaults.get(provider.lower(), "unknown")

    # Check for required API keys
    if provider.lower() == "claude":
        api_key_var = 'ANTHROPIC_API_KEY'
    else:
        api_key_var = f'{provider.upper()}_API_KEY'

    if not os.getenv(api_key_var):
        console.print(f"❌ {api_key_var} environment variable not set", style="red")
        console.print(f"Please set your API key: export {api_key_var}=your_key_here")
        console.print("Or add it to your .env file")
        return

    # Initialize agent
    try:
        console.print(f"🤖 Initializing {provider.title()} agent...", style="cyan")
        agent = create_agent(provider=provider, model_name=model)

        # Validate configuration
        agent.validate_configuration()

        console.print(f"✅ Agent initialized successfully!", style="green")
        logger.info(f"Agent initialized: {provider} ({model})")

    except AgentConfigurationError as e:
        handle_startup_error(e, provider)
        return
    except Exception as e:
        logger.error(f"Unexpected startup error: {e}")
        console.print(f"❌ Unexpected error: {e}", style="red")
        return

    # Display welcome message
    display_welcome_message(provider, model)

    # Auto-load workspace if provided
    if workspace:
        console.print(f"🗂️  Auto-loading workspace: {workspace}", style="cyan")
        try:
            response = agent.chat(f"Please load the workspace at {workspace}")
            console.print(f"🤖 {response}", style="cyan")
        except Exception as e:
            console.print(f"⚠️  Failed to auto-load workspace: {e}", style="yellow")

    # Main conversation loop
    console.print("\n" + "=" * 60 + "\n")
    conversation_count = 0

    try:
        while True:
            try:
                # Get user input
                user_input = console.input("\n[bold green]You:[/bold green] ")

                # Handle exit commands
                if user_input.lower().strip() in ['quit', 'exit', 'q', 'bye']:
                    if conversation_count > 0:
                        # Ask for confirmation if they've had a conversation
                        if Confirm.ask("Are you sure you want to exit?"):
                            break
                        else:
                            continue
                    else:
                        break

                # Handle empty input
                if not user_input.strip():
                    console.print("💭 Please enter a message or type 'quit' to exit.", style="dim")
                    continue

                # Handle help commands
                if user_input.lower().strip() in ['help', '?']:
                    console.print("\n📚 Quick Help:", style="blue")
                    console.print("• 'load my workspace' - Load workspace configuration")
                    console.print("• 'create a media plan' - Start creating a new media plan")
                    console.print("• 'list my media plans' - Show existing media plans")
                    console.print("• 'show tools' - Display available tools")
                    console.print("• 'quit' - Exit the application")
                    continue

                # Handle tools info command
                if user_input.lower().strip() in ['show tools', 'tools', 'list tools']:
                    display_tool_info()
                    continue

                # Show thinking indicator
                with console.status("[cyan]🤔 Agent is thinking...", spinner="dots"):
                    # Get agent response
                    response = agent.chat(user_input)

                # Display response
                console.print(f"\n[bold cyan]🤖 Agent:[/bold cyan] {response}")

                conversation_count += 1

            except KeyboardInterrupt:
                console.print("\n\n⚠️  Interrupted by user", style="yellow")
                if Confirm.ask("Do you want to exit?"):
                    break
                else:
                    console.print("Continuing conversation...")
                    continue

            except Exception as e:
                logger.error(f"Conversation error: {e}")
                console.print(f"\n❌ Error: {e}", style="red")
                console.print("The conversation will continue...", style="dim")
                continue

    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
        console.print(f"\n💥 Fatal error: {e}", style="red")

    finally:
        # Display goodbye message
        if conversation_count > 0:
            session_info = agent.get_session_info()
            console.print(f"\n📊 Session Summary:", style="blue")
            console.print(f"Conversation turns: {conversation_count}")
            console.print(f"Tools available: {len(agent.get_available_tools())}")

            if hasattr(agent, 'get_conversation_stats'):
                stats = agent.get_conversation_stats()
                console.print(f"Total messages: {stats['total_messages']}")

        console.print("\n👋 Thanks for using Media Planning Agent!", style="green")
        console.print("Your media plans are saved in your workspace.", style="dim")


def main():
    """Entry point for the CLI application."""
    try:
        cli()
    except Exception as e:
        logger.error(f"Application error: {e}")
        console.print(f"💥 Application error: {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
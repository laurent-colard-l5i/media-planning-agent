# Media Planning Agent

An interactive AI agent for creating and managing media plans using the MediaPlanPy SDK.

## Features

- **Interactive Consultation**: Conduct strategic media planning sessions with AI assistance
- **Intelligent Generation**: Automatically create media plans with budget allocation and line items
- **Multi-LLM Support**: Works with Claude (Anthropic) and OpenAI GPT models
- **Workspace Integration**: Full integration with MediaPlanPy workspace management
- **Schema Compliance**: All generated media plans comply with the open media plan data standard

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd media-planning-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API key
export ANTHROPIC_API_KEY="your_claude_api_key_here"
```

### 3. Set Up MediaPlanPy Workspace

```bash
# Create a test workspace
mkdir test-workspace
cd test-workspace

# Create workspace.json (example configuration)
cat > workspace.json << 'EOF'
{
  "workspace_id": "test-workspace-001",
  "workspace_name": "Test Media Plans",
  "workspace_status": "active",
  "environment": "development",
  "storage": {
    "mode": "local",
    "local": {
      "base_path": "./media-plans"
    }
  },
  "schema_settings": {
    "preferred_version": "v1.0.0",
    "auto_migrate": false
  },
  "database": {
    "enabled": false
  }
}
EOF

cd ..
```

### 4. Run the Agent

```bash
# Start with Claude (default)
media-agent

# Or specify workspace path
media-agent --workspace ./test-workspace/workspace.json

# Use OpenAI instead (requires openai package)
pip install openai
media-agent --provider openai
```

## Usage Examples

### Basic Workflow

```
🤖 Agent: Hello! I'm your media planning assistant. Let's start by loading your workspace.

You: Load my workspace from ./test-workspace/workspace.json

🤖 Agent: ✅ Loaded workspace 'Test Media Plans' successfully!

You: Create a media plan for a new fitness app launch with $100K budget

🤖 Agent: I'd love to help you create a media plan for your fitness app launch. Let me gather some key information:

1. What's the name of your fitness app and what are your main campaign objectives?
2. When do you want the campaign to run (start and end dates)?
3. Who is your target audience?

[Continues with strategic consultation...]
```

## Development

### Phase 1 (Current): MVP Foundation
- [x] Project structure and configuration
- [x] Session state management
- [x] Tool registry system
- [x] Basic workspace operations
- [x] Simple media plan creation
- [x] Claude agent implementation

### Phase 2 (Planned): Strategic Intelligence
- [ ] Strategic consultation flows
- [ ] Intelligent line item generation
- [ ] Budget allocation logic
- [ ] Session-based context management

### Phase 3 (Planned): Advanced Operations
- [ ] OpenAI integration completion
- [ ] SQL query capabilities
- [ ] Multi-plan analysis
- [ ] Export functionality

## Architecture

```
src/media_agent/
├── agent/          # AI agent implementations (Claude, OpenAI)
├── tools/          # Tool functions for agent capabilities
├── conversation/   # Conversation flow management
└── utils/          # Utility functions and helpers
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run tests: `pytest`
5. Format code: `black . && isort .`
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Requirements

- Python 3.8+
- MediaPlanPy SDK
- Claude API key (Anthropic) or OpenAI API key
- Valid MediaPlanPy workspace configuration

## Support

- Check the [MediaPlanPy documentation](https://github.com/your-org/mediaplanpy) for workspace setup
- Review the [schema documentation](https://github.com/laurent-colard-l5i/mediaplanschema) for data structure details
- Open an issue for bugs or feature requests
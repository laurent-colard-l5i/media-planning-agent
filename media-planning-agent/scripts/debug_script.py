#!/usr/bin/env python3
"""
Debug script to check tool schema generation
Run with: python debug_schema.py
"""

import inspect
import sys

print("=" * 60)
print("DEBUGGING TOOL SCHEMA GENERATION")
print("=" * 60)

# Step 1: Check function signature
try:
    from media_agent.tools.workspace_tools import load_workspace

    sig = inspect.signature(load_workspace)
    print(f"✅ Function signature: {sig}")
    print("\nParameters:")

    for param_name, param in sig.parameters.items():
        print(f"  📋 {param_name}:")
        print(f"    - kind: {param.kind}")
        print(f"    - default: {param.default}")
        print(f"    - annotation: {param.annotation}")
        print(f"    - is VAR_KEYWORD: {param.kind == param.VAR_KEYWORD}")
        print(f"    - should skip: {param_name in ['session_state', 'kwargs'] or param.kind == param.VAR_KEYWORD}")
        print()

except Exception as e:
    print(f"❌ Error importing load_workspace: {e}")
    sys.exit(1)

# Step 2: Check tool registry
try:
    from media_agent.tools import tool_registry

    print(f"✅ Tool registry loaded")
    print(f"📋 Available tools: {tool_registry.get_tool_names()}")

    # Get the specific tool
    load_tool = tool_registry.get_tool('load_workspace')
    if load_tool:
        print(f"✅ load_workspace tool found")

        # Generate schema
        try:
            schema = load_tool.get_schema()
            print(f"✅ Schema generated successfully")
            print(f"📋 Schema: {schema}")
            print(f"📋 Properties: {list(schema['input_schema']['properties'].keys())}")
            print(f"📋 Required: {schema['input_schema']['required']}")
        except Exception as e:
            print(f"❌ Schema generation error: {e}")
            import traceback

            traceback.print_exc()
    else:
        print(f"❌ load_workspace tool not found in registry")

except Exception as e:
    print(f"❌ Error with tool registry: {e}")
    import traceback

    traceback.print_exc()

# Step 3: Test direct function call
try:
    from media_agent.agent.session import SessionState

    print(f"\n✅ Testing direct function call...")
    session = SessionState()
    result = load_workspace(session, workspace_path=None)
    print(f"📋 Result success: {result.get('success', 'Unknown')}")
    print(f"📋 Result message: {result.get('message', 'No message')[:100]}...")

except Exception as e:
    print(f"❌ Direct call error: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
print("DEBUG COMPLETE")
print("=" * 60)
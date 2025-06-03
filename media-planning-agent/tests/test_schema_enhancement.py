#!/usr/bin/env python3
"""
Test script to validate schema enhancement functionality.
Run with: python test_schema_enhancement.py
"""

import sys
import os
import logging

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_schema_loading():
    """Test schema loading from MediaPlanPy."""
    print("=" * 60)
    print("TESTING SCHEMA LOADING")
    print("=" * 60)

    try:
        from mediaplanpy.schema import SchemaManager

        schema_manager = SchemaManager()
        print(f"✅ Successfully created SchemaManager")

        # Test loading each schema type
        schema_types = ['mediaplan', 'campaign', 'lineitem']
        version = 'v1.0.0'

        schemas = {}
        for schema_type in schema_types:
            try:
                schema_data = schema_manager.get_schema(schema_type, version)
                schemas[schema_type] = schema_data
                print(f"✅ Loaded {schema_type} schema: {len(str(schema_data))} chars")
            except Exception as e:
                print(f"❌ Failed to load {schema_type} schema: {e}")

        return schemas

    except ImportError as e:
        print(f"❌ Failed to import MediaPlanPy schema components: {e}")
        return {}
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {}


def test_schema_formatting():
    """Test schema formatting for system prompt."""
    print("\n" + "=" * 60)
    print("TESTING SCHEMA FORMATTING")
    print("=" * 60)

    # Mock schemas for testing
    mock_schemas = {
        'campaign': {
            'type': 'object',
            'required': ['id', 'name', 'objective'],
            'properties': {
                'id': {'type': 'string'},
                'name': {'type': 'string'},
                'objective': {
                    'type': 'string',
                    'enum': ['awareness', 'consideration', 'conversion']
                }
            }
        }
    }

    try:
        from media_agent.agent.claude_agent import ClaudeAgent

        # Create a mock agent to test formatting
        agent = ClaudeAgent.__new__(ClaudeAgent)  # Create without calling __init__

        # Test the formatting method
        formatted = agent._format_schemas_for_prompt(mock_schemas, 'v1.0.0')

        print(f"✅ Formatted schema output:")
        print("-" * 40)
        print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
        print("-" * 40)

        return True

    except Exception as e:
        print(f"❌ Schema formatting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test full integration with Claude agent."""
    print("\n" + "=" * 60)
    print("TESTING INTEGRATION")
    print("=" * 60)

    try:
        # Mock environment for testing
        os.environ['ANTHROPIC_API_KEY'] = 'test_key_for_schema_testing'

        from media_agent.agent.claude_agent import ClaudeAgent

        # Create agent instance (will fail on API validation, but that's OK for schema testing)
        try:
            agent = ClaudeAgent()
        except Exception as e:
            print(f"⚠️ Expected API error (testing schemas only): {e}")

            # Create agent without full initialization for schema testing
            agent = ClaudeAgent.__new__(ClaudeAgent)
            agent.session_state = None  # No session state for this test

        # Test schema enhancement generation
        schema_enhancements = agent._get_schema_enhancements()

        if schema_enhancements:
            print(f"✅ Generated schema enhancements: {len(schema_enhancements)} characters")
            print(f"📋 First 200 chars: {schema_enhancements[:200]}...")
        else:
            print("❌ No schema enhancements generated")

        return bool(schema_enhancements)

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_workspace():
    """Test schema enhancement with workspace context."""
    print("\n" + "=" * 60)
    print("TESTING WITH WORKSPACE CONTEXT")
    print("=" * 60)

    try:
        from media_agent.agent.session import SessionState
        from mediaplanpy import WorkspaceManager

        # Create session state with workspace
        session_state = SessionState()

        # Try to load a workspace (may fail if no workspace available)
        try:
            workspace_manager = WorkspaceManager()
            # This will likely fail in test environment, but that's OK
            workspace_manager.load()
            session_state.workspace_manager = workspace_manager
            print("✅ Loaded workspace for testing")
        except Exception as e:
            print(f"⚠️ No workspace available for testing: {e}")
            session_state.workspace_manager = None

        # Create agent with session state
        from media_agent.agent.claude_agent import ClaudeAgent
        agent = ClaudeAgent.__new__(ClaudeAgent)
        agent.session_state = session_state

        # Test schema version detection
        version = agent._get_preferred_schema_version()
        print(f"✅ Detected schema version: {version}")

        # Test schema loading
        schemas = agent._load_schemas(version)
        print(f"✅ Loaded {len(schemas)} schemas")

        return True

    except Exception as e:
        print(f"❌ Workspace test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🧪 Schema Enhancement Testing Suite")

    tests = [
        ("Schema Loading", test_schema_loading),
        ("Schema Formatting", test_schema_formatting),
        ("Integration", test_integration),
        ("Workspace Context", test_with_workspace)
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    passed = 0
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("🎉 All tests passed! Schema enhancement is ready for integration.")
    else:
        print("⚠️ Some tests failed. Please review implementation before proceeding.")
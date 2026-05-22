# tests/orchestration/test_tool.py
"""Unit tests for OrchestrationTool — schema, params, name, scopes."""
import pytest

from nanobot.agent.tools.orchestrate import OrchestrationTool


def test_tool_name():
    """Tool name matches the LLM-visible function name."""
    tool = OrchestrationTool()
    assert tool.name == "orchestrate"


def test_tool_parameters_schema():
    """Parameters is a JSON Schema object with required goal property."""
    tool = OrchestrationTool()
    params = tool.parameters
    assert params["type"] == "object"
    assert "goal" in params["properties"]
    assert "goal" in params["required"]


def test_tool_has_core_scope():
    """Tool is in core scope so ToolLoader with scope="core" discovers it."""
    assert "core" in OrchestrationTool._scopes


def test_tool_is_not_read_only():
    """Orchestration has side-effects (spawns workers, modifies files)."""
    tool = OrchestrationTool()
    assert not tool.read_only


def test_tool_to_schema():
    """to_schema() returns OpenAI function schema."""
    tool = OrchestrationTool()
    schema = tool.to_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "orchestrate"


def test_cast_params():
    """cast_params passes through the goal key unchanged."""
    tool = OrchestrationTool()
    result = tool.cast_params({"goal": "test goal"})
    assert result["goal"] == "test goal"


def test_validate_params_valid():
    """A dict with the required 'goal' key passes validation."""
    tool = OrchestrationTool()
    errors = tool.validate_params({"goal": "add login"})
    assert len(errors) == 0


def test_validate_params_missing_goal():
    """Missing the required 'goal' key produces validation errors."""
    tool = OrchestrationTool()
    errors = tool.validate_params({})
    assert len(errors) > 0

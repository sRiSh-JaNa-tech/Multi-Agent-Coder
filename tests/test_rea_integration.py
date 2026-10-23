"""
Tests for REA (Reverse Engineer Anything) MCP integration.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from multi_agent_coder.tools.custom.rea_tools import (
    _server_parameters,
    rea_call_tool,
    rea_list_tools,
)
from multi_agent_coder.tools.registry import get_default_registry


def test_server_parameters_env_override(monkeypatch):
    monkeypatch.setenv("REA_MCP_COMMAND", "custom-rea")
    monkeypatch.setenv("REA_MCP_ARGS", '["run", "--mode", "mcp"]')
    params = _server_parameters("/test/workspace")
    assert params.command == "custom-rea"
    assert params.args == ["run", "--mode", "mcp"]
    assert "/test/workspace" in params.cwd


def test_server_parameters_invalid_json(monkeypatch):
    monkeypatch.setenv("REA_MCP_ARGS", "not-a-json-list")
    with pytest.raises(ValueError, match="JSON array"):
        _server_parameters(".")


def test_server_parameters_default(monkeypatch):
    monkeypatch.delenv("REA_MCP_COMMAND", raising=False)
    monkeypatch.delenv("REA_MCP_ARGS", raising=False)
    monkeypatch.setenv("REA_MCP_VERSION", "6.7.0")
    params = _server_parameters(".")
    assert "npx" in params.command
    assert params.args == ["-y", "rea-agents@6.7.0", "mcp"]


def test_rea_tools_registered_in_default_registry():
    reg = get_default_registry()
    tool_list = reg.get_tool("rea_list_tools")
    assert tool_list is not None
    assert "reverse-engineering" in tool_list.description

    tool_call = reg.get_tool("rea_call_tool")
    assert tool_call is not None
    assert "Call a tool on the REA" in tool_call.description


def test_rea_call_tool_validation():
    res = rea_call_tool("", {})
    assert "tool_name is required" in res


def test_rea_call_tool_mocked():
    with patch("multi_agent_coder.tools.custom.rea_tools._call_rea_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = "Mock REA Analysis Result: ELF x86-64 binary detected"
        res = rea_call_tool("analyze_binary", {"path": "target.bin"})
        assert "ELF x86-64 binary detected" in res
        mock_call.assert_called_once_with("analyze_binary", {"path": "target.bin"}, None)

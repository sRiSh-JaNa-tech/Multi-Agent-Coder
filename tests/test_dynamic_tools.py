"""
Tests for dynamic tool discovery, the @tool decorator, and ToolRegistry extensibility.
"""

import tempfile
from pathlib import Path
import pytest

from multi_agent_coder.tools.decorator import tool, generate_tool_schema
from multi_agent_coder.tools.registry import ToolRegistry, get_default_registry, load_custom_tools
from multi_agent_coder.security.permissions import AgentCapability, SecurityContext
from multi_agent_coder.orchestrator.agent_worker import AgentWorker


def test_tool_decorator_schema_generation():
    @tool(name="calc_add", description="Add two integers")
    def add(a: int, b: int = 10) -> int:
        """Add two numbers together.
        
        :param a: The first integer
        :param b: The second integer
        """
        return a + b

    schema = add.__tool_schema__
    assert schema["name"] == "calc_add"
    assert schema["description"] == "Add two integers"
    props = schema["parameters"]["properties"]
    assert "a" in props
    assert props["a"]["type"] == "integer"
    assert "The first integer" in props["a"].get("description", "")
    assert "b" in props
    assert props["b"]["default"] == 10
    assert "a" in schema["parameters"]["required"]
    assert "b" not in schema["parameters"]["required"]


def test_registry_executes_decorated_tool():
    reg = ToolRegistry()

    @tool(name="greet_user", description="Greet by name", registry=reg)
    def greet(name: str, shout: bool = False) -> str:
        msg = f"Hello, {name}!"
        return msg.upper() if shout else msg

    res = reg.execute("greet_user", {"name": "Alice"})
    assert res == "Hello, Alice!"

    res_shout = reg.execute("greet_user", {"name": "Bob", "shout": True})
    assert res_shout == "HELLO, BOB!"


def test_load_custom_tools_from_directory(tmp_path):
    # Create a dynamic custom tool file
    tool_file = tmp_path / "crypto_helper.py"
    tool_file.write_text(
        '''
from multi_agent_coder.tools.decorator import tool

@tool(name="xor_cipher", description="XOR string with key")
def xor_cipher(text: str, key: int = 42) -> str:
    return "".join(chr(ord(c) ^ key) for c in text)
''',
        encoding="utf-8",
    )

    reg = ToolRegistry()
    loaded_count = load_custom_tools(tmp_path, reg)
    assert loaded_count >= 1

    tool_def = reg.get_tool("xor_cipher")
    assert tool_def is not None
    assert tool_def.description == "XOR string with key"

    out = reg.execute("xor_cipher", {"text": "ANTIGRAVITY", "key": 13})
    assert isinstance(out, str)
    # Re-apply XOR to verify reversibility
    re_out = reg.execute("xor_cipher", {"text": out, "key": 13})
    assert re_out == "ANTIGRAVITY"


def test_agent_worker_has_custom_tools():
    reg = get_default_registry()
    # Built-in custom tools (e.g. decode_payload, http_request) should be present
    assert reg.get_tool("decode_payload") is not None
    assert reg.get_tool("http_request") is not None

    worker = AgentWorker(
        agent_id="Agent-1",
        role="General Engineer",
        specialty="analysis",
        tool_registry=reg,
    )
    tools = worker._build_worker_tools()
    func_decls = tools[0]["function_declarations"]
    tool_names = [d["name"] for d in func_decls]

    assert "decode_payload" in tool_names
    assert "http_request" in tool_names
    assert "read_file" in tool_names
    assert "run_command" in tool_names

    # Test executing decode_payload through worker
    # "SGVsbG8=" is base64 for "Hello"
    res = worker._execute_tool("decode_payload", {"payload": "SGVsbG8=", "encoding": "base64"})
    assert "Hello" in res

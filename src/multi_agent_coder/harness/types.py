"""
Harness Type Definitions.
Provider-agnostic representations for messages, tool calls, and LLM responses.
"""

from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class ToolCall:
    """Represents a tool/function call requested by the LLM."""
    name: str
    args: dict[str, Any]
    id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")


@dataclass
class ToolResult:
    """Represents the output of executing a ToolCall."""
    name: str
    output: str
    tool_call_id: str | None = None
    is_error: bool = False


@dataclass
class TokenUsage:
    """Tracks token consumption for an LLM interaction."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class Message:
    """Unified chat message structure across any provider."""
    role: str  # "user", "assistant", "system", "tool"
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass
class LLMResponse:
    """Unified response from any attached LLM adapter."""
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw_response: Any = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

"""
Harness Subsystem.
Modular testing and execution harness for quickly attaching any LLM backend
to codebase navigation tools and multi-agent ticket execution.
Decoupled from the main API agent implementation.
"""

from .base import BaseLLMAdapter
from .types import Message, ToolCall, ToolResult, LLMResponse, TokenUsage
from .adapters import (
    MockLLMAdapter,
    CallableAdapter,
    GeminiAdapter,
    OpenAICompatibleAdapter,
)
from .engine import HarnessAgent, AgentRunResult, AgentStep
from .ticket_runner import HarnessTicketWorker

__all__ = [
    "BaseLLMAdapter",
    "Message",
    "ToolCall",
    "ToolResult",
    "LLMResponse",
    "TokenUsage",
    "MockLLMAdapter",
    "CallableAdapter",
    "GeminiAdapter",
    "OpenAICompatibleAdapter",
    "HarnessAgent",
    "AgentRunResult",
    "AgentStep",
    "HarnessTicketWorker",
]

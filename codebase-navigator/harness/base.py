"""
Base LLM Adapter Interface.
Defines the contract that any LLM backend (Gemini, Mock, OpenAI, Ollama, Custom Callable)
must implement to attach to the agentic harness.
"""

from abc import ABC, abstractmethod
from typing import Any
from .types import Message, LLMResponse


class BaseLLMAdapter(ABC):
    """Abstract base class for all LLM backend adapters."""

    def __init__(self, model_name: str = "default", name: str | None = None):
        self.model_name = model_name
        self.name = name or self.__class__.__name__

    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        """
        Generate a model response given message history and available tools.

        Args:
            messages: List of unified Message objects.
            tools: Optional list of tool declaration dictionaries or functions.
            system_instruction: Optional system persona/instruction.

        Returns:
            LLMResponse containing text, tool calls, and token usage.
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.name} model={self.model_name}>"

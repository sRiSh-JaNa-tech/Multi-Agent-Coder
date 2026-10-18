"""
Unified Tool Registry.
Central registry for declaring, validating, capability-checking, and dispatching
tools used across worker agents and the lead brain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import json
import logging
from pathlib import Path
from typing import Any, Callable

from ..security.permissions import AgentCapability, SecurityContext
from ..common.logging_config import setup_logging

logger = setup_logging(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    required_capability: AgentCapability = AgentCapability.READ_ONLY
    mutating: bool = False


class ToolRegistry:
    """Manages tool registration, capability verification, and execution."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any],
        required_capability: AgentCapability = AgentCapability.READ_ONLY,
        mutating: bool = False,
    ) -> None:
        """Register a new tool."""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            required_capability=required_capability,
            mutating=mutating,
        )

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_schemas(self, security_context: SecurityContext | None = None) -> list[dict[str, Any]]:
        """Return tool declarations filtered by capabilities in security_context (if provided)."""
        schemas = []
        for tool in self._tools.values():
            if security_context and not security_context.has_capability(tool.required_capability):
                continue
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            })
        return schemas

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        security_context: SecurityContext | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a registered tool with capability checks and safety boundaries."""
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' is not registered."

        if security_context:
            try:
                security_context.assert_capability(tool.required_capability)
            except PermissionError as e:
                logger.warning("Permission denied executing %s: %s", name, e)
                return f"PermissionError: {e}"

        handler = tool.handler
        sig = inspect.signature(handler)
        call_kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name in arguments:
                call_kwargs[param_name] = arguments[param_name]
            elif param_name == "security_context" and security_context:
                call_kwargs[param_name] = security_context
            elif param_name in kwargs:
                call_kwargs[param_name] = kwargs[param_name]
            elif param_name == "tool_input":
                call_kwargs[param_name] = arguments

        try:
            return handler(**call_kwargs)
        except Exception as exc:
            logger.exception("Error executing tool '%s': %s", name, exc)
            return f"Tool Execution Error ({name}): {exc}"

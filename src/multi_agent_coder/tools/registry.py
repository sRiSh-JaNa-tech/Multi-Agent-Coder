"""
Unified Tool Registry.
Central registry for declaring, validating, capability-checking, and dispatching
tools used across worker agents and the lead brain.
Supports drop-in custom tools and automatic plugin loading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
import inspect
import json
import logging
import os
from pathlib import Path
import sys
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

        # Parameter aliases to tolerate slight LLM key variations
        aliases: dict[str, list[str]] = {
            "filepath": ["path", "file", "filename", "relative_path", "target_file"],
            "path": ["filepath", "file", "filename", "relative_path", "dir_path", "directory"],
            "command": ["cmd"],
            "query": ["pattern", "q"],
            "pattern": ["query", "regex"],
        }

        has_var_keyword = any(param.kind == param.VAR_KEYWORD for param in sig.parameters.values())
        if has_var_keyword:
            call_kwargs.update(arguments)
            call_kwargs["tool_input"] = arguments
            if security_context:
                call_kwargs["security_context"] = security_context
            call_kwargs.update(kwargs)
        else:
            for param_name, param in sig.parameters.items():
                if param_name in arguments:
                    call_kwargs[param_name] = arguments[param_name]
                elif param_name in aliases:
                    for alias in aliases[param_name]:
                        if alias in arguments:
                            call_kwargs[param_name] = arguments[alias]
                            break
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


_DEFAULT_REGISTRY: ToolRegistry | None = None


def get_default_registry() -> ToolRegistry:
    """Get or initialize the global shared tool registry with all built-in and custom tools."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ToolRegistry()
        _register_builtins(_DEFAULT_REGISTRY)

        # Auto-load custom tools from package custom_tools directory
        pkg_custom_dir = Path(__file__).resolve().parent / "custom"
        if pkg_custom_dir.exists():
            load_custom_tools(pkg_custom_dir, _DEFAULT_REGISTRY)

        # Auto-load custom tools from workspace if present
        workspace_custom_dir = Path.cwd() / "custom_tools"
        if workspace_custom_dir.exists():
            load_custom_tools(workspace_custom_dir, _DEFAULT_REGISTRY)

    return _DEFAULT_REGISTRY


def load_custom_tools(directory: Path | str, registry: ToolRegistry | None = None) -> int:
    """
    Dynamically load all Python tool modules from a directory.
    Any function decorated with @tool in those files is automatically added to the registry.
    """
    target_registry = registry or get_default_registry()
    dir_path = Path(directory).resolve()
    if not dir_path.is_dir():
        return 0

    count = 0
    sys_path_added = False
    if str(dir_path) not in sys.path:
        sys.path.insert(0, str(dir_path))
        sys_path_added = True

    try:
        for py_file in dir_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            module_name = f"custom_tools_{py_file.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    # Look for functions with __tool_schema__
                    for attr_name in dir(mod):
                        obj = getattr(mod, attr_name)
                        if callable(obj) and hasattr(obj, "__tool_schema__"):
                            schema = obj.__tool_schema__
                            target_registry.register(
                                name=schema["name"],
                                description=schema["description"],
                                parameters=schema["parameters"],
                                handler=obj,
                                required_capability=getattr(obj, "__required_capability__", AgentCapability.READ_ONLY),
                                mutating=getattr(obj, "__mutating__", False),
                            )
                            count += 1
                            logger.info("Loaded custom tool [%s] from %s", schema["name"], py_file.name)
            except Exception as e:
                logger.error("Failed to load custom tool module %s: %s", py_file, e)
    finally:
        if sys_path_added and str(dir_path) in sys.path:
            sys.path.remove(str(dir_path))

    return count


def _register_builtins(registry: ToolRegistry) -> None:
    """Register all standard built-in tools into a ToolRegistry."""
    from .files import (
        FILE_TOOLS,
        execute_read_file,
        execute_list_directory,
        execute_find_files,
    )
    from .coding import (
        CODING_TOOLS,
        execute_create_file,
        execute_write_file,
        execute_replace_file_content,
        execute_append_file,
    )
    from .execution import (
        EXECUTION_TOOLS,
        execute_run_command,
        execute_check_syntax,
        execute_git_status,
        execute_git_diff,
        execute_git_log,
        execute_git_branch,
        execute_git_add,
        execute_git_commit,
        execute_git_push,
        execute_git_pull,
    )
    from .search import SEARCH_TOOLS, execute_grep, execute_search_code
    from .outline import OUTLINE_TOOLS, execute_get_file_outline
    from .memory import MEMORY_TOOLS, execute_save_memory, execute_recall_memory

    # Map of schemas to their handlers and mutating status
    tool_map: dict[str, tuple[Callable[..., Any], AgentCapability, bool]] = {
        # Execution
        "run_command": (lambda **kw: execute_run_command(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.EXECUTE_TESTS, True),
        "check_syntax": (lambda **kw: execute_check_syntax(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        "git_status": (lambda **kw: execute_git_status(workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        "git_diff": (lambda **kw: execute_git_diff(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        "git_log": (lambda **kw: execute_git_log(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        "git_branch": (lambda **kw: execute_git_branch(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        "git_add": (lambda **kw: execute_git_add(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.GIT_WORKTREE_WRITE, True),
        "git_commit": (lambda **kw: execute_git_commit(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.GIT_WORKTREE_WRITE, True),
        "git_push": (lambda **kw: execute_git_push(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.GIT_WORKTREE_WRITE, True),
        "git_pull": (lambda **kw: execute_git_pull(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.GIT_WORKTREE_WRITE, True),
        # Files
        "read_file": (lambda **kw: execute_read_file(None, kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        "list_directory": (lambda **kw: execute_list_directory(None, kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        "find_files": (lambda **kw: execute_find_files(None, kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        # Coding
        "write_file": (lambda **kw: execute_write_file(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root"), security_context=kw.get("security_context")), AgentCapability.WORKSPACE_WRITE, True),
        "replace_file_content": (lambda **kw: execute_replace_file_content(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root"), security_context=kw.get("security_context")), AgentCapability.WORKSPACE_WRITE, True),
        "create_file": (lambda **kw: execute_create_file(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root"), security_context=kw.get("security_context")), AgentCapability.WORKSPACE_WRITE, True),
        # Search & Outline
        "grep": (lambda **kw: execute_grep(tool_input=kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        "search_code": (lambda **kw: execute_search_code(None, None, kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        "get_file_outline": (lambda **kw: execute_get_file_outline(kw.get("tool_input", kw), workspace_root=kw.get("workspace_root")), AgentCapability.READ_ONLY, False),
        # Memory
        "save_memory": (lambda **kw: execute_save_memory(None, kw.get("tool_input", kw)), AgentCapability.READ_ONLY, True),
        "recall_memory": (lambda **kw: execute_recall_memory(None, kw.get("tool_input", kw)), AgentCapability.READ_ONLY, False),
    }

    all_schemas = EXECUTION_TOOLS + FILE_TOOLS + CODING_TOOLS + SEARCH_TOOLS + OUTLINE_TOOLS + MEMORY_TOOLS
    seen = set()
    for s in all_schemas:
        t_name = s.get("name")
        if not t_name or t_name in seen:
            continue
        seen.add(t_name)
        if t_name in tool_map:
            handler, cap, mutating = tool_map[t_name]
            registry.register(
                name=t_name,
                description=s.get("description", ""),
                parameters=s.get("parameters", {"type": "object", "properties": {}}),
                handler=handler,
                required_capability=cap,
                mutating=mutating,
            )

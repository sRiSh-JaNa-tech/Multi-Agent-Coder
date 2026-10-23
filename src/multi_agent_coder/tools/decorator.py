"""
Decorator and schema generator for creating tools effortlessly.
"""

from __future__ import annotations

import functools
import inspect
from pathlib import Path
from typing import Any, Callable, get_type_hints

from ..security.permissions import AgentCapability


def python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
    """Map a Python type annotation to JSON schema property definition."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {"type": "string"}

    # Handle typing.Optional / Union[T, None]
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    if origin is not None:
        # Union
        if str(origin).endswith("Union"):
            # Check for Optional (Union[T, NoneType])
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                return python_type_to_json_schema(non_none[0])
            return {"type": "string"}
        if origin in (list, list):
            item_schema = python_type_to_json_schema(args[0]) if args else {"type": "string"}
            return {"type": "array", "items": item_schema}
        if origin in (dict, dict):
            return {"type": "object"}

    if annotation in (str, Path):
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation in (list, tuple, set):
        return {"type": "array", "items": {"type": "string"}}
    if annotation in (dict,):
        return {"type": "object"}

    return {"type": "string"}


def generate_tool_schema(
    fn: Callable[..., Any],
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Inspect function signature and docstring to generate a tool schema."""
    tool_name = name or fn.__name__
    raw_doc = inspect.getdoc(fn) or ""
    tool_desc = description or (raw_doc.split("\n\n")[0].strip() if raw_doc else f"Execute {tool_name}")

    sig = inspect.signature(fn)
    hints = {}
    try:
        hints = get_type_hints(fn)
    except Exception:
        pass

    properties: dict[str, Any] = {}
    required: list[str] = []

    # Parameters to ignore (injected automatically by runtime)
    injected_params = {"workspace_root", "security_context", "tool_input", "kwargs"}

    for param_name, param in sig.parameters.items():
        if param_name in injected_params or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue

        ann = hints.get(param_name, param.annotation)
        prop = python_type_to_json_schema(ann)

        # Extract parameter description from docstring if present
        # Format e.g.: :param name: description or Args: name: description
        param_desc = ""
        for line in raw_doc.splitlines():
            line_str = line.strip()
            if line_str.startswith(f":param {param_name}:"):
                param_desc = line_str.split(f":param {param_name}:", 1)[1].strip()
                break
            elif line_str.startswith(f"{param_name}:"):
                param_desc = line_str.split(f"{param_name}:", 1)[1].strip()
                break

        if param_desc:
            prop["description"] = param_desc

        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(param_name)

        properties[param_name] = prop

    return {
        "name": tool_name,
        "description": tool_desc,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def tool(
    name: str | None = None,
    description: str | None = None,
    required_capability: AgentCapability = AgentCapability.READ_ONLY,
    mutating: bool = False,
    registry: Any = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to turn any Python function into an agent tool.
    
    Usage:
        @tool(description="Search the web using DuckDuckGo")
        def web_search(query: str, max_results: int = 5) -> str:
            ...
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        schema = generate_tool_schema(fn, name=name, description=description)
        fn.__tool_schema__ = schema  # type: ignore[attr-defined]
        fn.__tool_name__ = schema["name"]  # type: ignore[attr-defined]
        fn.__required_capability__ = required_capability  # type: ignore[attr-defined]
        fn.__mutating__ = mutating  # type: ignore[attr-defined]

        # Register in provided or default registry
        target_registry = registry
        if target_registry is None:
            try:
                from .registry import get_default_registry
                target_registry = get_default_registry()
            except ImportError:
                pass

        if target_registry is not None:
            target_registry.register(
                name=schema["name"],
                description=schema["description"],
                parameters=schema["parameters"],
                handler=fn,
                required_capability=required_capability,
                mutating=mutating,
            )

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        wrapper.__tool_schema__ = schema  # type: ignore[attr-defined]
        wrapper.__tool_name__ = schema["name"]  # type: ignore[attr-defined]
        return wrapper

    return decorator

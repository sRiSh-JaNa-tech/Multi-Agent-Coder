"""
Code Outline Tools

Extracts high-level architectural outlines (classes, methods, functions) from files
without loading the entire file into context.
"""

import ast
import re
from pathlib import Path
from typing import Any

from .repo import find_repo_path
from ..common.logging_config import setup_logging

logger = setup_logging(__name__)

OUTLINE_TOOLS = [
    {
        "name": "get_file_outline",
        "description": (
            "Extract a high-level outline of classes, methods, and functions with line numbers "
            "from a file without loading the entire file content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository name or path",
                },
                "filepath": {
                    "type": "string",
                    "description": "Relative path to the file (e.g., 'src/flask/app.py')",
                },
            },
            "required": ["repo", "filepath"],
        },
    },
]


def _outline_python(content: str, filepath: str) -> str:
    """Parse Python AST and produce structured symbol hierarchy."""
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        return f"Syntax error while parsing outline for {filepath}: {e}"

    lines = [f"Symbols in {filepath}:"]

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node)
            doc_summary = f" — {doc.splitlines()[0]}" if doc else ""
            lines.append(f"\nclass {node.name} (line {node.lineno}){doc_summary}")
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                    args = [a.arg for a in item.args.args]
                    f_doc = ast.get_docstring(item)
                    f_summary = f" — {f_doc.splitlines()[0]}" if f_doc else ""
                    lines.append(f"    {prefix} {item.name}({', '.join(args)}) (line {item.lineno}){f_summary}")

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            args = [a.arg for a in node.args.args]
            doc = ast.get_docstring(node)
            doc_summary = f" — {doc.splitlines()[0]}" if doc else ""
            lines.append(f"{prefix} {node.name}({', '.join(args)}) (line {node.lineno}){doc_summary}")

    return "\n".join(lines) if len(lines) > 1 else f"No top-level functions or classes found in {filepath}."


def _outline_generic(content: str, filepath: str) -> str:
    """Extract headers or function patterns from other files."""
    lines = content.split("\n")
    matches = []
    pattern = re.compile(r"^\s*(export\s+)?(function|class|interface|type|const|let|struct|enum)\s+([A-Za-z0-9_]+)")

    for idx, line in enumerate(lines, 1):
        m = pattern.match(line)
        if m:
            matches.append(f"  line {idx:4d}: {line.strip()[:100]}")
        elif line.startswith("#") and filepath.endswith((".md", ".markdown")):
            matches.append(f"  line {idx:4d}: {line.strip()}")

    if matches:
        return f"Outline of {filepath}:\n" + "\n".join(matches)
    return f"No major structural definitions detected in {filepath}."


def execute_get_file_outline(tool_input: dict[str, Any]) -> str:
    """Execute get_file_outline tool."""
    repo = tool_input.get("repo", "")
    filepath = (tool_input.get("filepath") or tool_input.get("file") or tool_input.get("path") or "").lstrip("/\\")
    if not repo or not filepath:
        return "Error: 'repo' and 'filepath' parameters are required."

    repo_path = find_repo_path(repo)
    if not repo_path:
        return f"Repository '{repo}' not found."

    target = repo_path / filepath
    if not target.is_file():
        return f"File not found: {filepath} in {repo}"

    try:
        content = target.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"Error reading {filepath}: {e}"

    if target.suffix == ".py":
        return _outline_python(content, filepath)
    return _outline_generic(content, filepath)

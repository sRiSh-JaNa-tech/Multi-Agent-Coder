"""
File Tools

Tools for reading files and exploring directory structure of indexed repositories.
"""

from pathlib import Path
from typing import Any

from ..common.logging_config import setup_logging
from ..security.permissions import AgentCapability, SecurityContext # Import security modules

import os # Import os for path manipulation
import re # Import re for regex matching in security context

logger = setup_logging(__name__)

# Where cloned repos are stored
REPOS_DIR = Path(__file__).parent.parent / "repos"

FILE_TOOLS = [
    {
        "name": "read_file",
        "description": (
            "Read the full content of a file in the target workspace, with line numbers. "
            "Paths are relative to the workspace root."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Ignored when running inside a swarm workspace; pass '.' or omit.",
                },
                "filepath": {
                    "type": "string",
                    "description": "Path to file relative to the workspace root (e.g., 'src/app.js')",
                },
                "start_line": {
                    "type": "integer",
                    "description": "1-based first line to return (default: 1). Use to inspect later sections of large files.",
                    "default": 1,
                },
                "line_count": {
                    "type": "integer",
                    "description": "Maximum lines to return (default: 1000; maximum: 5000).",
                    "default": 1000,
                },
            },
            "required": ["filepath"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories at a path relative to the target workspace root.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Ignored when running inside a swarm workspace; pass '.' or omit.",
                },
                "path": {
                    "type": "string",
                    "description": "Path within the workspace (defaults to root)",
                    "default": "",
                },
            },
            "required": [],
        },
    },
    {
        "name": "find_files",
        "description": "Find files matching a glob pattern (e.g. '**/*.js', '*compress*') relative to the workspace root.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., '**/*.py', '*config*', '*.json'). Default: '**/*'.",
                    "default": "**/*",
                },
                "path": {
                    "type": "string",
                    "description": "Subdirectory to search inside (default: workspace root).",
                    "default": "",
                },
            },
            "required": [],
        },
    },
]


from .repo import find_repo_path


def _find_repo_path(repo: str) -> Path | None:
    """Find the local path for a repository."""
    return find_repo_path(repo)


def _resolve_target(
    tool_input: dict[str, Any], relative: str, workspace_root: Path | None
) -> tuple[Path | None, str | None, str]:
    """
    Resolve ``relative`` to an absolute path.

    Returns (path, error, label). With ``workspace_root`` the path is confined to that
    directory and the ``repo`` argument is ignored, so an agent can never be redirected to a
    different checkout (the original cause of project copies landing in the swarm repo).
    """
    if workspace_root is not None:
        from .coding import resolve_safe_path

        try:
            # Use os.path.commonpath for strict path containment
            abs_filepath = os.path.abspath(Path(workspace_root) / (relative or "."))
            abs_workspace_root = os.path.abspath(workspace_root)
            common = os.path.commonpath([abs_workspace_root, abs_filepath])
            if common != abs_workspace_root:
                raise PermissionError(f"Path traversal blocked: '{relative}' escapes workspace root.")
            return Path(workspace_root) / (relative or "."), None, "workspace"
        except PermissionError as exc:
            return None, f"Error: {exc}", "workspace"

    repo = tool_input.get("repo", "")
    if not repo:
        return None, "Error: 'repo' parameter is required.", ""
    repo_path = _find_repo_path(repo)
    if not repo_path:
        return None, f"Repository '{repo}' not found locally.", repo
    return (repo_path / relative if relative else repo_path), None, repo


def execute_read_file(
    _vector_store: Any, tool_input: dict[str, Any], workspace_root: Path | None = None
) -> str:
    """Read a file (inside ``workspace_root`` when given) with line numbers."""
    filepath = (
        tool_input.get("filepath")
        or tool_input.get("file_path")
        or tool_input.get("file")
        or tool_input.get("path")
        or ""
    ).lstrip("/\\")
    if not filepath:
        return "Error: 'filepath' parameter is required."

    file_path, error, label = _resolve_target(tool_input, filepath, workspace_root)
    if error:
        return error
    repo = label

    if not file_path.is_file():
        return f"File not found: {filepath} in {repo}"

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"Error reading file: {e}"

    # Support paging so agents can inspect large source and challenge artifacts in full.
    lines = content.split("\n")
    start_line = max(1, int(tool_input.get("start_line", 1)))
    line_count = min(5000, max(1, int(tool_input.get("line_count", 1000))))
    start_idx = min(start_line - 1, len(lines))
    end_idx = min(len(lines), start_idx + line_count)
    display_lines = lines[start_idx:end_idx]
    numbered = [f"{i + start_idx + 1:4d} | {line}" for i, line in enumerate(display_lines)]
    result = f"File: {filepath} (lines {start_idx + 1}-{end_idx} of {len(lines)})\n\n" + "\n".join(numbered)
    if end_idx < len(lines):
        result += f"\n\n... {len(lines) - end_idx} lines remain; call read_file with start_line={end_idx + 1}."
    return result


def execute_list_directory(
    _vector_store: Any, tool_input: dict[str, Any], workspace_root: Path | None = None
) -> str:
    """List directory contents (inside ``workspace_root`` when given)."""
    subpath = (
        tool_input.get("path")
        or tool_input.get("subpath")
        or tool_input.get("directory_path")
        or ""
    ).lstrip("/\\")

    target, error, label = _resolve_target(tool_input, subpath, workspace_root)
    if error:
        return error
    repo = label

    if not target.is_dir():
        return f"Directory not found: {subpath or '/'} in {repo}"

    entries = sorted(target.iterdir())
    lines = [f"Directory: {subpath or '/'} in {repo}\n"]

    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            lines.append(f"  [dir] {entry.name}/")
        else:
            size = entry.stat().st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            lines.append(f"  [file] {entry.name} ({size_str})")

    return "\n".join(lines)


def execute_find_files(
    _vector_store: Any, tool_input: dict[str, Any], workspace_root: Path | None = None
) -> str:
    """Find files matching a glob pattern inside workspace_root."""
    pattern = (tool_input.get("pattern") or "**/*").strip()
    subpath = (
        tool_input.get("path")
        or tool_input.get("subpath")
        or tool_input.get("directory_path")
        or ""
    ).lstrip("/\\")

    target, error, label = _resolve_target(tool_input, subpath, workspace_root)
    if error:
        return error
    if not target.is_dir():
        return f"Directory not found: {subpath or '/'} in {label}"

    glob_pattern = pattern if ("*" in pattern or "?" in pattern) else f"*{pattern}*"
    matches: list[str] = []
    count = 0
    max_matches = 100

    try:
        for p in target.rglob(glob_pattern):
            rel = p.relative_to(target)
            if any(part.startswith(".") or part in ("node_modules", "__pycache__", ".venv") for part in rel.parts):
                continue
            display_path = (Path(subpath) / rel).as_posix() if subpath else rel.as_posix()
            matches.append(display_path + ("/" if p.is_dir() else ""))
            count += 1
            if count >= max_matches:
                matches.append(f"... [truncated at {max_matches} results]")
                break
    except Exception as exc:
        return f"Error finding files with pattern '{pattern}': {exc}"

    if not matches:
        return f"No files found matching '{pattern}' in {subpath or '.'}"
    return f"Found {len(matches)} matches for '{pattern}':\n" + "\n".join(f"  {m}" for m in matches)


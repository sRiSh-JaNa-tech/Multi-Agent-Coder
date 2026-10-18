"""
Coding Tools
Tools for precision file creation, atomic search-and-replace patching, and code editing.
Includes syntax validation gate and path traversal protection.
"""

import ast
import os
import tempfile
from pathlib import Path
from typing import Any

from ..common.logging_config import setup_logging
from ..security.permissions import AgentCapability, SecurityContext # Import security modules

logger = setup_logging(__name__)


class PatchError(Exception):
    """Raised when atomic search/replace patch fails validation."""
    pass


def resolve_safe_path(workspace_root: Path, relative_path: str) -> Path:
    """
    Resolve and validate a relative path against workspace root.
    Guards against path traversal attacks (e.g., ../../etc/passwd).
    """
    root = workspace_root.resolve()
    target = (root / relative_path).resolve()
    abs_filepath = os.path.abspath(target)
    abs_workspace_root = os.path.abspath(root)
    
    # Use os.path.commonpath to ensure it's a subpath
    common = os.path.commonpath([abs_workspace_root, abs_filepath])
    
    # If the common path is the workspace root, then the filepath is within the workspace
    if common != abs_workspace_root:
        raise PermissionError(f"Path traversal blocked: '{relative_path}' escapes workspace root.")
    return target


def apply_search_replace(
    workspace_root: Path,
    relative_path: str,
    search_block: str,
    replace_block: str,
) -> str:
    """
    Surgically replace a unique search block with replacement content.
    Enforces path sandboxing, unique match constraint, in-memory Python AST
    syntax verification, and atomic file replacement via tempfile + os.replace.
    """
    target = resolve_safe_path(workspace_root, relative_path)
    if not target.exists():
        raise FileNotFoundError(f"Target file does not exist: {relative_path}")

    original_content = target.read_text(encoding="utf-8")
    occurrences = original_content.count(search_block)

    if occurrences == 0:
        raise PatchError(f"SEARCH block not found in {relative_path}. Ensure exact whitespace match.")
    if occurrences > 1:
        raise PatchError(
            f"Ambiguous SEARCH block: found {occurrences} matches in {relative_path}. Include more surrounding context."
        )

    updated_content = original_content.replace(search_block, replace_block, 1)

    # Syntax gate for Python files before touching disk
    if target.suffix == ".py":
        try:
            ast.parse(updated_content, filename=relative_path)
        except SyntaxError as exc:
            raise PatchError(f"Rejected edit: introduces SyntaxError at line {exc.lineno}: {exc.msg}") from exc

    # Atomic write via temporary file in the same directory
    fd, tmp_path = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(updated_content)
        os.replace(tmp_path, target)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise

    return f"Successfully patched {relative_path}"


def _get_target_root(tool_input: dict[str, Any], workspace_root: Path | None = None) -> Path:
    if workspace_root:
        return workspace_root
    repo = tool_input.get("repo")
    if repo:
        p = Path(repo).expanduser()
        if p.is_dir():
            return p
        try:
            from .repo import find_repo_path
            found = find_repo_path(repo)
            if found:
                return found
        except Exception:
            pass
    return Path.cwd()


CODING_TOOLS = [
    {
        "name": "create_file",
        "description": "Create a new file in the repository with the specified content. Fails if file exists.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Relative file path."},
                "content": {"type": "string", "description": "Full file content."},
            },
            "required": ["filepath", "content"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or overwrite a file in the repository with the specified content.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Relative file path."},
                "content": {"type": "string", "description": "Full file content."},
            },
            "required": ["filepath", "content"],
        },
    },
    {
        "name": "replace_file_content",
        "description": "Surgically replace an exact block of code in a file with new code.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Relative file path."},
                "target_content": {"type": "string", "description": "The exact block of code to find and replace."},
                "replacement_content": {"type": "string", "description": "The new replacement content."},
            },
            "required": ["filepath", "target_content", "replacement_content"],
        },
    },
]


def _normalize_file_content(content: str) -> str:
    """
    Normalize file content, unescaping accidental raw literal newlines/tabs from LLM responses
    and stripping surrounding markdown code fences if erroneously included.
    """
    if not content:
        return content

    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            content = "\n".join(lines[1:-1])

    if "\\n" in content and "\n" not in content:
        try:
            content = content.encode("utf-8").decode("unicode_escape")
        except Exception:
            content = content.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    elif "\\r\\n" in content and "\r\n" not in content and "\n" not in content:
        try:
            content = content.encode("utf-8").decode("unicode_escape")
        except Exception:
            content = content.replace("\\r\\n", "\n").replace("\\n", "\n")

    return content


def execute_create_file(tool_input: dict[str, Any], workspace_root: Path | None = None, security_context: SecurityContext | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    filepath = (tool_input.get("filepath") or tool_input.get("file_path") or "").lstrip("/\\")
    raw_content = tool_input.get("content", "")
    if not filepath:
        return "Error: 'filepath' parameter is required."

    content = _normalize_file_content(raw_content)

    if security_context:
        security_context.assert_capability(AgentCapability.WORKSPACE_WRITE)
        security_context.assert_path_within_workspace(os.path.join(root, filepath))

    try:
        target = resolve_safe_path(root, filepath)
    except PermissionError as e:
        return f"Error: {e}"

    if target.exists():
        return f"Error: File already exists at {filepath}. Use replace_file_content or write_file."

    if target.suffix == ".py":
        try:
            ast.parse(content, filename=filepath)
        except SyntaxError as syn_err:
            return (
                f"Rejected create_file: Content introduces SyntaxError at line {syn_err.lineno}: {syn_err.msg}. "
                f"Ensure valid Python code is provided without literal escape artifacts."
            )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Successfully created {filepath} ({len(content.splitlines())} lines)"


def execute_write_file(tool_input: dict[str, Any], workspace_root: Path | None = None, security_context: SecurityContext | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    filepath = (tool_input.get("filepath") or tool_input.get("file_path") or "").lstrip("/\\")
    raw_content = tool_input.get("content", "")
    if not filepath:
        return "Error: 'filepath' parameter is required."

    content = _normalize_file_content(raw_content)

    if security_context:
        security_context.assert_capability(AgentCapability.WORKSPACE_WRITE)
        security_context.assert_path_within_workspace(os.path.join(root, filepath))

    try:
        target = resolve_safe_path(root, filepath)
    except PermissionError as e:
        return f"Error: {e}"

    # Anti-collapse protection for existing files
    if target.exists():
        try:
            existing_lines = len(target.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            existing_lines = 0
        new_lines = len(content.splitlines())
        if existing_lines > 30 and new_lines <= 2:
            return (
                f"Rejected full-file overwrite: Target '{filepath}' has {existing_lines} lines, "
                f"but provided content has only {new_lines} line(s) (likely due to newline escaping or truncated output). "
                f"Use replace_file_content to surgically edit specific blocks without replacing the entire file."
            )

    if target.suffix == ".py":
        try:
            ast.parse(content, filename=filepath)
        except SyntaxError as syn_err:
            return (
                f"Rejected write_file: Content introduces SyntaxError at line {syn_err.lineno}: {syn_err.msg}. "
                f"Fix the syntax error or use replace_file_content for surgical edits."
            )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Successfully updated {filepath} ({len(content.splitlines())} lines)"


def execute_replace_file_content(tool_input: dict[str, Any], workspace_root: Path | None = None, security_context: SecurityContext | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    filepath = (tool_input.get("filepath") or tool_input.get("file_path") or "").lstrip("/\\")
    target_content = tool_input.get("target_content") or tool_input.get("search_block") or ""
    replacement_content = tool_input.get("replacement_content") or tool_input.get("replace_block") or ""

    if not filepath:
        return "Error: 'filepath' parameter is required."
    if not target_content:
        return "Error: 'target_content' parameter is required."

    if security_context:
        security_context.assert_capability(AgentCapability.WORKSPACE_WRITE)
        security_context.assert_path_within_workspace(os.path.join(root, filepath))

    try:
        apply_search_replace(root, filepath, target_content, replacement_content)
        return f"Successfully updated {filepath}"
    except (PatchError, PermissionError, FileNotFoundError) as e:
        return f"Error: {e}"

"""
Execution & Validation Tools

Tools for running tests, linter commands, git inspections, and syntax checks.
Used by the Reviewer and Orchestrator agents.
"""

import ast
import json
import subprocess
from pathlib import Path
from typing import Any

from tools.repo import find_repo_path
from common.logging_config import setup_logging

logger = setup_logging(__name__)

EXECUTION_TOOLS = [
    {
        "name": "run_command",
        "description": (
            "Execute a shell command (such as running tests, linters, or build scripts) "
            "inside the repository directory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run (e.g., 'pytest tests/test_app.py', 'ruff check .')",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name or path where the command should execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 60)",
                    "default": 60,
                },
            },
            "required": ["command", "repo"],
        },
    },
    {
        "name": "git_diff",
        "description": "View git diff of modified, staged, or unstaged files in the repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository name or path",
                },
                "filepath": {
                    "type": "string",
                    "description": "Optional specific file to limit the diff to",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "git_status",
        "description": "View short git status of untracked and modified files in the repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository name or path",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "check_syntax",
        "description": "Validate syntax of a Python or JSON file without executing it.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository name or path",
                },
                "filepath": {
                    "type": "string",
                    "description": "Relative path to the file to check",
                },
            },
            "required": ["repo", "filepath"],
        },
    },
]


def execute_run_command(tool_input: dict[str, Any]) -> str:
    """Run a shell command inside the repository directory."""
    command = tool_input["command"]
    repo = tool_input["repo"]
    timeout = min(int(tool_input.get("timeout", 60)), 300)

    repo_path = find_repo_path(repo)
    if not repo_path:
        return f"Repository '{repo}' not found."

    logger.info("Executing in %s: %s", repo_path, command)
    try:
        proc = subprocess.run(
            command,
            cwd=str(repo_path),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output_parts = [f"Exit code: {proc.returncode}"]
        if proc.stdout:
            stdout_text = proc.stdout.strip()
            if len(stdout_text) > 4000:
                stdout_text = stdout_text[:3900] + "\n... [truncated]"
            output_parts.append(f"STDOUT:\n{stdout_text}")
        if proc.stderr:
            stderr_text = proc.stderr.strip()
            if len(stderr_text) > 4000:
                stderr_text = stderr_text[:3900] + "\n... [truncated]"
            output_parts.append(f"STDERR:\n{stderr_text}")

        if not proc.stdout and not proc.stderr:
            output_parts.append("(Command produced no output)")

        return "\n\n".join(output_parts)
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing command: {e}"


def execute_git_diff(tool_input: dict[str, Any]) -> str:
    """Inspect git diff in the repository."""
    repo = tool_input["repo"]
    filepath = tool_input.get("filepath")

    repo_path = find_repo_path(repo)
    if not repo_path:
        return f"Repository '{repo}' not found."

    cmd = ["git", "diff"]
    if filepath:
        cmd.append(filepath)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        diff = proc.stdout.strip()
        if not diff:
            return "No git diff detected (working tree is clean)."
        if len(diff) > 5000:
            diff = diff[:4900] + "\n... [truncated]"
        return diff
    except Exception as e:
        return f"Error running git diff: {e}"


def execute_git_status(tool_input: dict[str, Any]) -> str:
    """Inspect git status in the repository."""
    repo = tool_input["repo"]
    repo_path = find_repo_path(repo)
    if not repo_path:
        return f"Repository '{repo}' not found."

    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        status = proc.stdout.strip()
        return status if status else "Working tree clean (nothing to commit)."
    except Exception as e:
        return f"Error running git status: {e}"


def execute_check_syntax(tool_input: dict[str, Any]) -> str:
    """Check syntax of code/config files without running them."""
    repo = tool_input.get("repo", "")
    filepath = (tool_input.get("filepath") or tool_input.get("file") or tool_input.get("path") or "").lstrip("/\\")
    if not repo or not filepath:
        return "Error: 'repo' and 'filepath' parameters are required."

    repo_path = find_repo_path(repo)
    if not repo_path:
        return f"Repository '{repo}' not found."

    target = repo_path / filepath
    if not target.is_file():
        return f"File not found: {filepath}"

    suffix = target.suffix.lower()
    try:
        content = target.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"

    if suffix == ".py":
        try:
            ast.parse(content, filename=filepath)
            return f"Syntax valid for Python file: {filepath}"
        except SyntaxError as e:
            return f"Python SyntaxError in {filepath}:{e.lineno}: {e.msg}\n  {e.text or ''}"

    if suffix == ".json":
        try:
            json.loads(content)
            return f"Syntax valid for JSON file: {filepath}"
        except json.JSONDecodeError as e:
            return f"JSONDecodeError in {filepath}:{e.lineno}: {e.msg}"

    return f"Syntax check not supported for '{suffix}' files."

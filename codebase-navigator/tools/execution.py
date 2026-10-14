"""
Execution Tools
Tools for running sandboxed commands, validating syntax, and inspecting git status/diff.
Includes process-group isolation, secret stripping, timeout enforcement, and output truncation.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import Any

from common.logging_config import setup_logging

logger = setup_logging(__name__)


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def truncate_output(text: str, max_chars: int = 4000) -> str:
    """Truncate long terminal output to head + tail to prevent context explosion."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    omitted = len(text) - max_chars
    return f"{text[:half]}\n... [TRUNCATED {omitted} CHARS] ...\n{text[-half:]}"


def run_sandboxed_command(
    cmd: list[str],
    cwd: Path,
    timeout_seconds: float = 30.0,
    max_output_chars: int = 4000,
) -> CommandResult:
    """
    Run a subprocess with stdin closed, secrets stripped from environment,
    process-group sandboxing, hard timeout enforcement, and output truncation.
    """
    # Strip sensitive API keys and secrets from child environment
    safe_env = {
        k: v for k, v in os.environ.items()
        if not any(secret in k.upper() for secret in ("API_KEY", "SECRET", "TOKEN", "PASSWORD"))
    }
    safe_env["PYTHONUNBUFFERED"] = "1"

    # Start child in dedicated process group where supported
    popen_kwargs: dict[str, Any] = {
        "cwd": str(cwd.resolve()),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "env": safe_env,
    }

    if hasattr(os, "setsid") or sys.platform != "win32":
        popen_kwargs["start_new_session"] = True
    else:
        # On Windows, start_new_session=True creates a new process group in py3.11+
        try:
            popen_kwargs["start_new_session"] = True
        except Exception:
            pass

    proc = subprocess.Popen(cmd, **popen_kwargs)

    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        return CommandResult(
            exit_code=proc.returncode,
            stdout=truncate_output(stdout or "", max_output_chars),
            stderr=truncate_output(stderr or "", max_output_chars),
            timed_out=False,
        )
    except subprocess.TimeoutExpired:
        # Terminate entire process group so children don't become zombies
        if hasattr(os, "killpg") and hasattr(signal, "SIGKILL"):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        else:
            try:
                proc.kill()
            except Exception:
                pass

        try:
            stdout, stderr = proc.communicate(timeout=2.0)
        except Exception:
            stdout, stderr = "", ""

        err_msg = (stderr or "") + f"\nProcess killed after {timeout_seconds}s timeout."
        return CommandResult(
            exit_code=-1,
            stdout=truncate_output(stdout or "", max_output_chars),
            stderr=truncate_output(err_msg, max_output_chars),
            timed_out=True,
        )


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


EXECUTION_TOOLS = [
    {
        "name": "run_command",
        "description": "Run a non-interactive shell command in the repository with a timeout.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run."},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30).", "default": 30},
            },
            "required": ["command"],
        },
    },
    {
        "name": "check_syntax",
        "description": "Check Python syntax of a file using python -m py_compile.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "File to check."},
            },
            "required": ["filepath"],
        },
    },
    {
        "name": "git_diff",
        "description": "Show git diff of modified files in the repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Optional file path to diff."},
            },
        },
    },
    {
        "name": "git_status",
        "description": "Show git status of the repository.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def execute_run_command(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    cmd_str = tool_input.get("command", "")
    timeout = float(tool_input.get("timeout", 30))

    if not cmd_str:
        return "Error: 'command' parameter is required."

    if sys.platform == "win32":
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd_str]
    else:
        cmd = ["/bin/sh", "-c", cmd_str]

    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=timeout)
    out = []
    if res.stdout:
        out.append(f"STDOUT:\n{res.stdout}")
    if res.stderr:
        out.append(f"STDERR:\n{res.stderr}")
    out.append(f"Exit code: {res.exit_code}")
    out.append(f"Exit Code: {res.exit_code}")
    if res.timed_out:
        out.append("Status: Timed out and killed")
    return "\n".join(out)


def execute_check_syntax(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    filepath = (tool_input.get("filepath") or tool_input.get("file_path") or "").lstrip("/\\")
    if not filepath:
        return "Error: 'filepath' parameter is required."

    target = root / filepath
    if not target.exists():
        return f"Error: File not found: {filepath}"

    cmd = [sys.executable, "-m", "py_compile", str(target)]
    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=10)
    if res.exit_code == 0:
        return f"Syntax valid: {filepath}"
    return f"SyntaxError in {filepath}:\n{res.stderr or res.stdout}"


def execute_git_diff(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    filepath = tool_input.get("filepath")
    cmd = ["git", "diff"]
    if filepath:
        cmd.append(filepath.lstrip("/\\"))
    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=15)
    return res.stdout if res.stdout else "No changes detected (clean working tree)."


def execute_git_status(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    cmd = ["git", "status", "--short"]
    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=10)
    return res.stdout if res.stdout else "Clean working tree (no changes)."

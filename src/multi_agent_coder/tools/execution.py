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

from ..common.logging_config import setup_logging

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



GIT_TOOLS = [
    {
        "name": "git_pull",
        "description": "Pull latest changes from a remote Git repository into the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "remote": {"type": "string", "description": "Remote name (default: origin).", "default": "origin"},
                "branch": {"type": "string", "description": "Optional branch name to pull."},
            },
        },
    },
    {
        "name": "git_push",
        "description": "Push committed changes to a remote Git repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "remote": {"type": "string", "description": "Remote name (default: origin).", "default": "origin"},
                "branch": {"type": "string", "description": "Optional branch name to push."},
                "set_upstream": {"type": "boolean", "description": "Whether to pass -u / --set-upstream.", "default": False},
            },
        },
    },
    {
        "name": "git_commit",
        "description": "Commit staged or modified changes to the Git repository with a message.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message."},
                "stage_all": {"type": "boolean", "description": "Automatically stage all modified and new files (default: True).", "default": True},
                "files": {"type": "array", "items": {"type": "string"}, "description": "Optional specific list of files to commit."},
            },
            "required": ["message"],
        },
    },
    {
        "name": "git_add",
        "description": "Stage files in the Git index for committing.",
        "parameters": {
            "type": "object",
            "properties": {
                "files": {"type": "string", "description": "Files to stage (default: '.' for all).", "default": "."},
            },
        },
    },
    {
        "name": "git_branch",
        "description": "List, create, or switch Git branches.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "create", "checkout"], "description": "Action: list, create, or checkout.", "default": "list"},
                "branch_name": {"type": "string", "description": "Branch name (required for create and checkout)."},
            },
        },
    },
    {
        "name": "git_log",
        "description": "Show recent Git commit history.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of commits to show (default: 10).", "default": 10},
            },
        },
    },
]

EXECUTION_TOOLS = [
    *GIT_TOOLS,

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

    ext = target.suffix.lower()
    if ext in (".js", ".mjs", ".cjs"):
        cmd = ["node", "--check", str(target)]
    elif ext in (".py", ".pyw"):
        cmd = [sys.executable, "-m", "py_compile", str(target)]
    elif ext in (".json",):
        cmd = [sys.executable, "-m", "json.tool", str(target)]
    else:
        return f"Syntax valid (skipped non-script file): {filepath}"

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


def execute_git_pull(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    remote = tool_input.get("remote", "origin")
    branch = tool_input.get("branch")
    cmd = ["git", "pull", remote]
    if branch:
        cmd.append(branch)
    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=45)
    out = res.stdout or res.stderr or "Pull completed."
    return f"Git Pull (Exit {res.exit_code}):\n{out.strip()}"


def execute_git_push(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    remote = tool_input.get("remote", "origin")
    branch = tool_input.get("branch")
    cmd = ["git", "push"]
    if tool_input.get("set_upstream"):
        cmd.append("-u")
    if remote:
        cmd.append(remote)
    if branch:
        cmd.append(branch)
    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=45)
    out = res.stdout or res.stderr or "Push completed."
    return f"Git Push (Exit {res.exit_code}):\n{out.strip()}"


def execute_git_commit(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    message = tool_input.get("message", "").strip()
    if not message:
        return "Error: 'message' parameter is required for git_commit."

    files = tool_input.get("files")
    stage_all = tool_input.get("stage_all", True)
    if files:
        file_list = [str(f) for f in files] if isinstance(files, list) else [str(files)]
        run_sandboxed_command(["git", "add"] + file_list, cwd=root, timeout_seconds=15)
    elif stage_all:
        run_sandboxed_command(["git", "add", "-A"], cwd=root, timeout_seconds=15)

    cmd = ["git", "commit", "-m", message]
    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=20)
    out = res.stdout or res.stderr or "Commit finished."
    return f"Git Commit (Exit {res.exit_code}):\n{out.strip()}"


def execute_git_add(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    files = tool_input.get("files", ".")
    file_list = [str(f) for f in files] if isinstance(files, list) else [str(files)]
    cmd = ["git", "add"] + file_list
    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=15)
    if res.exit_code == 0:
        return f"Staged {', '.join(file_list)} successfully."
    return f"Git Add (Exit {res.exit_code}):\n{res.stderr or res.stdout}"


def execute_git_branch(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    action = tool_input.get("action", "list").lower()
    branch_name = tool_input.get("branch_name", "").strip()
    if action == "list":
        cmd = ["git", "branch", "-a"]
    elif action == "create":
        if not branch_name:
            return "Error: 'branch_name' parameter is required when action='create'."
        cmd = ["git", "checkout", "-b", branch_name]
    elif action == "checkout":
        if not branch_name:
            return "Error: 'branch_name' parameter is required when action='checkout'."
        cmd = ["git", "checkout", branch_name]
    else:
        return f"Error: Unknown action '{action}'. Must be 'list', 'create', or 'checkout'."

    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=15)
    out = res.stdout or res.stderr or "Branch operation completed."
    return out.strip()


def execute_git_log(tool_input: dict[str, Any], workspace_root: Path | None = None) -> str:
    root = _get_target_root(tool_input, workspace_root)
    limit = int(tool_input.get("limit", 10))
    cmd = ["git", "log", "-n", str(limit), "--oneline"]
    res = run_sandboxed_command(cmd, cwd=root, timeout_seconds=15)
    return res.stdout if res.stdout else (res.stderr or "No git commit history found.")

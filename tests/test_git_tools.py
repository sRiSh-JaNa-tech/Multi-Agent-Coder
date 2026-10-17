"""
Unit tests for Git tools, directory resolution, and Sub-Agent command-line capabilities.
"""

from pathlib import Path
import subprocess
import pytest

from multi_agent_coder.tools.execution import (
    execute_git_status,
    execute_git_diff,
    execute_git_add,
    execute_git_commit,
    execute_git_branch,
    execute_git_log,
    execute_run_command,
    GIT_TOOLS,
    EXECUTION_TOOLS,
)
from multi_agent_coder.tools.repo import resolve_repo_path
from multi_agent_coder.orchestrator.agent_worker import AgentWorker
from multi_agent_coder.orchestrator.ticket import Ticket


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """Create a temporary initialized git repository."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True, capture_output=True)
    
    file1 = repo_dir / "README.md"
    file1.write_text("# Initial Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)
    return repo_dir


def test_git_tools_exported_and_declared():
    """Verify Git tools are present in both GIT_TOOLS and EXECUTION_TOOLS."""
    git_names = {t["name"] for t in GIT_TOOLS}
    exec_names = {t["name"] for t in EXECUTION_TOOLS}
    expected = {"git_pull", "git_push", "git_commit", "git_add", "git_branch", "git_log"}
    assert expected.issubset(git_names)
    assert expected.issubset(exec_names)
    assert "run_command" in exec_names
    assert "git_status" in exec_names
    assert "git_diff" in exec_names


def test_git_status_and_diff(temp_git_repo: Path):
    """Test git_status and git_diff on clean and dirty trees."""
    # Clean state
    status_out = execute_git_status({}, workspace_root=temp_git_repo)
    assert "Clean working tree" in status_out or status_out.strip() == ""

    # Modify file
    readme = temp_git_repo / "README.md"
    readme.write_text("# Initial Repo\nExtra line\n", encoding="utf-8")

    status_out = execute_git_status({}, workspace_root=temp_git_repo)
    assert "README.md" in status_out

    diff_out = execute_git_diff({}, workspace_root=temp_git_repo)
    assert "+Extra line" in diff_out


def test_git_add_commit_and_log(temp_git_repo: Path):
    """Test staging, committing, and inspecting git commit log."""
    new_file = temp_git_repo / "feature.py"
    new_file.write_text("print('hello')\n", encoding="utf-8")

    add_res = execute_git_add({"files": "feature.py"}, workspace_root=temp_git_repo)
    assert "Staged feature.py" in add_res

    commit_res = execute_git_commit({"message": "Add feature.py", "stage_all": False}, workspace_root=temp_git_repo)
    assert "Exit 0" in commit_res or "Add feature.py" in commit_res

    log_res = execute_git_log({"limit": 5}, workspace_root=temp_git_repo)
    assert "Add feature.py" in log_res
    assert "Initial commit" in log_res


def test_git_branch_operations(temp_git_repo: Path):
    """Test listing, creating, and checking out git branches."""
    # Create branch
    create_res = execute_git_branch({"action": "create", "branch_name": "feature-branch"}, workspace_root=temp_git_repo)
    assert "Switched to a new branch" in create_res or "feature-branch" in create_res

    # List branches
    list_res = execute_git_branch({"action": "list"}, workspace_root=temp_git_repo)
    assert "feature-branch" in list_res


def test_directory_resolution():
    """Verify resolve_repo_path resolves local directories like '.' without cloning."""
    cwd = Path.cwd().resolve()
    resolved_path, collection_name, needs_clone = resolve_repo_path(".")
    assert resolved_path == cwd
    assert needs_clone is False
    assert collection_name.startswith("local-")


def test_subagent_cmd_and_git_access(temp_git_repo: Path):
    """Verify AgentWorker has command line access (cmd/run_command) and git tools."""
    worker = AgentWorker(
        agent_id="test_worker_1",
        role="Backend Engineer",
        specialty="Python & CLI",
        workspace_root=temp_git_repo,
        api_key="dummy_key",
    )

    # Check worker tool declarations
    worker_tools = worker._build_worker_tools()
    func_decls = worker_tools[0]["function_declarations"]
    tool_names = {t["name"] for t in func_decls}
    assert "run_command" in tool_names
    assert "git_status" in tool_names
    assert "git_commit" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names

    # Test executing run_command through the worker
    cmd_res = worker._execute_tool("run_command", {"command": "echo SubAgentCmdOnline"})
    assert "SubAgentCmdOnline" in cmd_res

    # Test executing git_status through the worker
    git_res = worker._execute_tool("git_status", {})
    assert "Clean working tree" in git_res or git_res.strip() == ""

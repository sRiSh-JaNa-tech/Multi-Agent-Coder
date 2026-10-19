import subprocess
from pathlib import Path
from multi_agent_coder.tools.repo import create_worktree, remove_worktree, merge_worktree

def test_worktree_lifecycle_and_isolation(tmp_path: Path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Initialize a git repo with an initial commit
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    (repo_dir / "init.txt").write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.PIPE)

    ticket_id = "T101"
    worktree_path = create_worktree(repo_dir, ticket_id)

    assert worktree_path.exists()
    assert (worktree_path / "init.txt").exists()

    # Make isolated edit in worktree
    (worktree_path / "feature.txt").write_text("feature content", encoding="utf-8")

    # Verify main repo does NOT yet have feature.txt
    assert not (repo_dir / "feature.txt").exists()

    # Merge worktree back to main
    merge_worktree(repo_dir, ticket_id, target_branch="main")

    # Verify main repo now HAS feature.txt
    assert (repo_dir / "feature.txt").exists()
    assert (repo_dir / "feature.txt").read_text(encoding="utf-8") == "feature content"

    # Remove worktree
    remove_worktree(repo_dir, ticket_id)
    assert not worktree_path.exists()


def test_agent_worktree_isolation_until_ticket_runner_merge(tmp_path: Path):
    """
    Proves that an agent modifying a file in its isolated worktree does NOT
    affect the file in the main repository until ticket_runner.py explicitly merges it.
    """
    repo_dir = tmp_path / "main_repo"
    repo_dir.mkdir()

    # Initialize main git repo with initial commit
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.name", "Swarm Lead"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "lead@example.com"], cwd=str(repo_dir), check=True)
    initial_text = "original main repo content\n"
    (repo_dir / "app.py").write_text(initial_text, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit on main"], cwd=str(repo_dir), check=True, stdout=subprocess.PIPE)

    from multi_agent_coder.orchestrator.worktree_manager import WorktreeManager
    from multi_agent_coder.orchestrator.ticket_runner import FileIOWorker
    from multi_agent_coder.orchestrator.agent_worker import AgentWorker

    wt_manager = WorktreeManager(repo_dir)
    runner = FileIOWorker(repo_dir)
    agent = AgentWorker("Agent-Worktree-Tester", role="Implementer", workspace_root=repo_dir, api_key="dummy")

    ticket_id = "TICK-ISO-01"

    # 1. Bind agent execution context to isolated ephemeral worktree
    agent_wt_path = wt_manager.bind_agent_to_worktree(agent, ticket_id)
    assert agent.workspace_root == agent_wt_path
    assert agent_wt_path.exists()
    assert (agent_wt_path / "app.py").exists()

    # 2. Agent modifies app.py inside its isolated worktree
    isolated_text = "modified content exclusively inside agent worktree\n"
    (agent.workspace_root / "app.py").write_text(isolated_text, encoding="utf-8")

    # 3. Prove main repository file remains 100% untouched and unaffected!
    main_file_content_before_merge = (repo_dir / "app.py").read_text(encoding="utf-8")
    assert main_file_content_before_merge == initial_text, (
        "Isolation breach: main repository was modified before ticket_runner explicit merge!"
    )

    # 4. Explicitly merge via ticket_runner single-threaded queue
    merge_ticket = wt_manager.merge_via_ticket_runner(ticket_id, runner, target_branch="main")
    assert merge_ticket.status == "APPLIED", f"Ticket runner merge failed: {merge_ticket.error}"

    # 5. Prove main repository file now contains the merged changes
    main_file_content_after_merge = (repo_dir / "app.py").read_text(encoding="utf-8")
    assert main_file_content_after_merge == isolated_text, (
        f"Expected merged content, got: {main_file_content_after_merge!r}"
    )

    runner.stop()
    wt_manager.cleanup_all()


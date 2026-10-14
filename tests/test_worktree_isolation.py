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

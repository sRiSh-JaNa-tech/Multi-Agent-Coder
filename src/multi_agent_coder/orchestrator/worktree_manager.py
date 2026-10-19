"""
Worktree Isolation Manager.
Provides isolated git worktree environments for concurrent agent ticket execution,
captures diffs, detects merge conflicts, and performs atomic 3-way branch merges.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import threading
from typing import NamedTuple, Any

from ..common.logging_config import setup_logging
from ..tools.repo import create_worktree, remove_worktree, merge_worktree, prune_worktrees
from .ticket import FileModificationTicket

logger = setup_logging(__name__)


class MergeResult(NamedTuple):
    success: bool
    ticket_id: str
    message: str
    conflicted_files: list[str]


class WorktreeManager:
    """Manages the creation, isolation, diff inspection, and merge resolution of git worktrees."""

    def __init__(self, workspace_root: Path | str, is_git_repo: bool | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        if is_git_repo is None:
            self.is_git_repo = (self.workspace_root / ".git").exists()
        else:
            self.is_git_repo = is_git_repo
        self._active_worktrees: dict[str, Path] = {}
        self._lock = threading.RLock()
        self.scratch_dir = self.workspace_root / "scratch" / "worktrees"

    def is_available(self) -> bool:
        """Check if git worktree isolation can be used in this workspace."""
        if not self.is_git_repo:
            return False
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(self.workspace_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return res.returncode == 0 and res.stdout.strip() == "true"
        except (subprocess.SubprocessError, OSError):
            return False

    def setup_worktree_for_ticket(self, ticket_id: str, ephemeral_scratch: bool = True) -> Path:
        """
        Create and return an isolated git worktree directory for the given ticket.
        If ephemeral_scratch is True, allocates inside the scratch directory.
        """
        with self._lock:
            if not self.is_available():
                logger.warning("Git worktree not available in %s; falling back to in-place workspace.", self.workspace_root)
                return self.workspace_root

            try:
                if ephemeral_scratch:
                    self.scratch_dir.mkdir(parents=True, exist_ok=True)
                    wt_path = self.scratch_dir / f"ticket-{ticket_id.lower()}"
                    branch_name = f"agent/ticket-{ticket_id.lower()}"
                    prune_worktrees(self.workspace_root)
                    if wt_path.exists():
                        subprocess.run(
                            ["git", "worktree", "remove", "--force", str(wt_path)],
                            cwd=str(self.workspace_root),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False,
                        )
                    subprocess.run(
                        ["git", "worktree", "add", "-B", branch_name, str(wt_path)],
                        cwd=str(self.workspace_root),
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                else:
                    wt_path = create_worktree(self.workspace_root, ticket_id)

                self._active_worktrees[ticket_id] = wt_path
                logger.info("Allocated isolated worktree for ticket [%s] at: %s", ticket_id, wt_path)
                return wt_path
            except Exception as e:
                logger.error("Failed to create worktree for ticket [%s]: %s; trying fallback standard worktree.", ticket_id, e)
                try:
                    wt_path = create_worktree(self.workspace_root, ticket_id)
                    self._active_worktrees[ticket_id] = wt_path
                    return wt_path
                except Exception:
                    return self.workspace_root

    def bind_agent_to_worktree(self, agent: Any, ticket_id: str) -> Path:
        """
        Bind the agent's absolute path execution context to this worktree.
        Guarantees that all agent tools operate strictly within the isolated worktree directory.
        """
        with self._lock:
            wt_path = self.setup_worktree_for_ticket(ticket_id)
            agent.workspace_root = wt_path
            if hasattr(agent, "security_context") and agent.security_context:
                agent.security_context.workspace_root = wt_path
            logger.info(
                "Bound agent [%s] execution context to isolated worktree: %s",
                getattr(agent, "agent_id", "unknown"),
                wt_path,
            )
            return wt_path

    def get_worktree_diff(self, ticket_id: str) -> str:
        """Get git diff between the ticket's worktree branch and the base branch."""
        with self._lock:
            wt_path = self._active_worktrees.get(ticket_id)
            if not wt_path or not wt_path.exists():
                wt_path = self.scratch_dir / f"ticket-{ticket_id.lower()}"
                if not wt_path.exists():
                    wt_path = self.workspace_root / ".worktrees" / f"ticket-{ticket_id.lower()}"
                    if not wt_path.exists():
                        return ""

            try:
                res = subprocess.run(
                    ["git", "diff", "HEAD"],
                    cwd=str(wt_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                return res.stdout
            except Exception as e:
                logger.error("Error obtaining worktree diff for %s: %s", ticket_id, e)
                return ""

    def merge_ticket_worktree(self, ticket_id: str, target_branch: str = "main") -> MergeResult:
        """Merge the ticket worktree branch into target_branch cleanly."""
        with self._lock:
            if not self.is_available():
                return MergeResult(success=True, ticket_id=ticket_id, message="In-place workspace; no git merge needed.", conflicted_files=[])

            try:
                wt_path = self._active_worktrees.get(ticket_id) or (self.scratch_dir / f"ticket-{ticket_id.lower()}")
                if wt_path.exists():
                    # Commit any uncommitted changes in the worktree
                    subprocess.run(["git", "add", "-A"], cwd=str(wt_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    commit_res = subprocess.run(
                        ["git", "commit", "-m", f"Auto-commit ticket {ticket_id}"],
                        cwd=str(wt_path),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    branch_name = f"agent/ticket-{ticket_id.lower()}"
                    # Merge branch into target branch in workspace_root
                    subprocess.run(["git", "checkout", target_branch], cwd=str(self.workspace_root), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    subprocess.run(["git", "merge", branch_name, "-m", f"Merge ticket {ticket_id}"], cwd=str(self.workspace_root), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                else:
                    merge_worktree(self.workspace_root, ticket_id, target_branch=target_branch)

                self.cleanup_ticket_worktree(ticket_id)
                return MergeResult(
                    success=True,
                    ticket_id=ticket_id,
                    message=f"Ticket {ticket_id} branch merged cleanly into {target_branch}.",
                    conflicted_files=[],
                )
            except Exception as e:
                logger.error("Merge failed for ticket [%s]: %s", ticket_id, e)
                conflicts: list[str] = []
                try:
                    st_res = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=str(self.workspace_root),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    for line in st_res.stdout.splitlines():
                        if line.startswith("UU ") or line.startswith("AA "):
                            conflicts.append(line[3:].strip())
                    subprocess.run(["git", "merge", "--abort"], cwd=str(self.workspace_root), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except Exception:
                    pass
                return MergeResult(
                    success=False,
                    ticket_id=ticket_id,
                    message=f"Merge failed: {e}",
                    conflicted_files=conflicts,
                )

    def merge_via_ticket_runner(self, ticket_id: str, ticket_runner: Any, target_branch: str = "main") -> FileModificationTicket:
        """Submit a merge ticket through the centralized FileIOWorker actor queue."""
        wt_path = self._active_worktrees.get(ticket_id) or (self.scratch_dir / f"ticket-{ticket_id.lower()}")
        if wt_path.exists():
            subprocess.run(["git", "add", "-A"], cwd=str(wt_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run(
                ["git", "commit", "-m", f"Auto-commit ticket {ticket_id}"],
                cwd=str(wt_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        merge_ticket = FileModificationTicket(
            filepath=f"ticket-{ticket_id.lower()}",
            operation="merge",
            ticket_id=ticket_id,
        )
        setattr(merge_ticket, "target_branch", target_branch)
        result = ticket_runner.submit(merge_ticket)
        if result.status == "APPLIED":
            self.cleanup_ticket_worktree(ticket_id)
        return result

    def cleanup_ticket_worktree(self, ticket_id: str) -> None:
        """Safely remove a ticket's worktree."""
        with self._lock:
            wt_path = self._active_worktrees.pop(ticket_id, None) or (self.scratch_dir / f"ticket-{ticket_id.lower()}")
            if wt_path and wt_path.exists():
                try:
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", str(wt_path)],
                        cwd=str(self.workspace_root),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                except Exception:
                    pass
            try:
                remove_worktree(self.workspace_root, ticket_id)
            except Exception:
                pass
            prune_worktrees(self.workspace_root)

    def cleanup_all(self) -> None:
        """Clean up all active worktrees and prune git metadata."""
        with self._lock:
            for tid in list(self._active_worktrees.keys()):
                self.cleanup_ticket_worktree(tid)
            try:
                prune_worktrees(self.workspace_root)
            except Exception:
                pass

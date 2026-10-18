"""
Unified Run Controller.
Top-level coordinator binding discovery, planning, security contexts,
worktree isolation, swarm parallel dispatch, verification, and SQLite persistence.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from .main_orchestrator import MainOrchestrator, AutonomousRunState
from .worktree_manager import WorktreeManager
from .protocols import AgentReport
from ..security.permissions import SecurityContext
from ..store.run_store import RunStateStore
from ..common.config import resolve_workspace
from ..common.logging_config import setup_logging

logger = setup_logging(__name__)


class UnifiedRunController:
    """Controls end-to-end execution lifecycle of the multi-agent swarm."""

    def __init__(
        self,
        workspace_root: Path | str | None = None,
        max_agents: int = 8,
        parallel: bool = True,
        auto_qa: bool = True,
        model: str | None = None,
        api_key: str | None = None,
        use_worktrees: bool = True,
        db_path: Path | str | None = None,
    ) -> None:
        self.workspace_root = resolve_workspace(workspace_root)
        self.max_agents = max_agents
        self.parallel = parallel
        self.auto_qa = auto_qa
        self.use_worktrees = use_worktrees

        self.store = RunStateStore(db_path=db_path)
        self.worktree_manager = WorktreeManager(self.workspace_root)

        self.orchestrator = MainOrchestrator(
            max_agents=self.max_agents,
            workspace_root=self.workspace_root,
            parallel=self.parallel,
            auto_qa=self.auto_qa,
            model=model,
            api_key=api_key,
        )
        self.run_id = self.orchestrator.run_id

    def execute_dag(
        self,
        tickets: list[dict[str, Any]],
        objective: str = "Swarm DAG Execution",
        on_step_callback: Callable[[Any], None] | None = None,
    ) -> dict[str, Any]:
        """Execute a predefined DAG manifest across the agent fleet."""
        self.store.record_run_start(
            run_id=self.run_id,
            objective=objective,
            workspace_root=str(self.workspace_root),
            max_agents=self.max_agents,
        )

        loaded_tickets = self.orchestrator.load_manifest({"objective": objective, "tickets": tickets})
        for t in loaded_tickets:
            self.store.save_ticket_checkpoint(self.run_id, t)

        results = self.orchestrator.process_all_tickets(on_step_callback=on_step_callback)
        for t in self.orchestrator.all_tickets:
            self.store.save_ticket_checkpoint(self.run_id, t)

        summary = self.orchestrator.get_summary()
        summary["run_id"] = self.run_id
        summary["objective"] = objective

        final_status = "COMPLETED" if summary.get("failed", 0) == 0 and summary.get("blocked", 0) == 0 else "PARTIAL"
        self.store.record_run_finish(self.run_id, final_status, summary)
        return summary

    def execute_autonomous(
        self,
        objective: str,
        on_step_callback: Callable[[Any], None] | None = None,
    ) -> dict[str, Any]:
        """Execute full autonomous loop: discovery -> plan -> parallel execution -> verification."""
        self.store.record_run_start(
            run_id=self.run_id,
            objective=objective,
            workspace_root=str(self.workspace_root),
            max_agents=self.max_agents,
        )

        summary = self.orchestrator.run_autonomous_loop(
            objective=objective,
            mode="autonomous",
            on_step_callback=on_step_callback,
        )

        # Record findings and tickets into SQLite
        for f in self.orchestrator.findings_registry.list_all():
            self.store.record_finding(self.run_id, f)

        for t in self.orchestrator.all_tickets:
            self.store.save_ticket_checkpoint(self.run_id, t)

        self.store.record_run_finish(self.run_id, summary.get("final_status", "COMPLETED"), summary)
        return summary

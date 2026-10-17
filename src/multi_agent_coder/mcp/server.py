"""
Model Context Protocol (MCP) Server for Multi-Agent Coder.
Exposes tools for Antigravity (The Brain) to orchestrate local worker agents:
- Submit DAG tickets
- Dispatch high-level objectives
- Query agent and worktree status
- Review isolated worktree diffs
- Merge approved ticket worktrees
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv
from mcp.server.mcpserver import MCPServer

from ..common.logging_config import setup_logging
from ..orchestrator.main_orchestrator import MainOrchestrator
from ..tools.repo import merge_worktree, prune_worktrees

load_dotenv(find_dotenv())
logger = setup_logging(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def create_mcp_server() -> MCPServer:
    """Build and configure the Multi-Agent Coder MCP server."""
    server = MCPServer(
        name="MultiAgentCoderSwarm",
        instructions=(
            "You are connected to the Multi-Agent Coder worker swarm. "
            "You act as the Lead Cognitive Architect (The Brain). "
            "Use these tools to dispatch tasks, monitor worker queues, review worktree git diffs, "
            "and merge verified solutions."
        ),
    )

    @server.tool(
        name="swarm_submit_dag",
        description=(
            "Submit an explicit Directed Acyclic Graph (DAG) of tickets directly to the worker swarm. "
            "Bypasses heuristic LLM decomposition and uses your exact architecture plan. "
            "Each ticket dictionary should include: 'id' (optional), 'title', 'description', "
            "'category' ('analysis', 'coding', 'testing', 'refactor', 'docs'), and 'depends_on' (list of prerequisite ticket IDs)."
        ),
    )
    def swarm_submit_dag(
        tickets: list[dict[str, Any]],
        objective: str = "Architectural Ticket DAG",
        max_agents: int | None = None,
        queue_limit: int | None = None,
    ) -> str:
        try:
            api_key = os.getenv("GEMINI_API_KEY", "")
            orchestrator = MainOrchestrator(
                api_key=api_key,
                queue_limit_per_agent=queue_limit,
                max_agents=max_agents,
                workspace_root=REPO_ROOT,
            )
            orchestrator.load_manifest({"objective": objective, "tickets": tickets})
            orchestrator.dispatch_all_pending()
            orchestrator.process_all_tickets_synchronously()

            summary = orchestrator.get_summary()
            summary["objective"] = objective
            return json.dumps(summary, indent=2)
        except Exception as e:
            logger.exception("Error in swarm_submit_dag")
            return json.dumps({"error": str(e), "status": "FAILED"}, indent=2)

    @server.tool(
        name="swarm_dispatch_objective",
        description=(
            "Submit a high-level problem statement. The internal orchestrator will automatically "
            "decompose the problem into 2-6 tickets and dispatch them across the agent fleet."
        ),
    )
    def swarm_dispatch_objective(
        objective: str,
        max_agents: int | None = None,
        queue_limit: int | None = None,
    ) -> str:
        try:
            api_key = os.getenv("GEMINI_API_KEY", "")
            orchestrator = MainOrchestrator(
                api_key=api_key,
                queue_limit_per_agent=queue_limit,
                max_agents=max_agents,
                workspace_root=REPO_ROOT,
            )
            orchestrator.identify_problems_and_create_tickets(objective)
            orchestrator.dispatch_all_pending()
            orchestrator.process_all_tickets_synchronously()

            summary = orchestrator.get_summary()
            summary["objective"] = objective
            return json.dumps(summary, indent=2)
        except Exception as e:
            logger.exception("Error in swarm_dispatch_objective")
            return json.dumps({"error": str(e), "status": "FAILED"}, indent=2)

    @server.tool(
        name="swarm_status",
        description="Query the operational status of the swarm, repository root, active Git worktrees, and .env configuration limits.",
    )
    def swarm_status() -> str:
        try:
            worktrees_dir = REPO_ROOT / ".worktrees"
            active_worktrees = []
            if worktrees_dir.exists():
                active_worktrees = [p.name for p in worktrees_dir.iterdir() if p.is_dir()]

            # Query git branches
            branches_proc = subprocess.run(
                ["git", "branch", "--list", "agent/*"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=5,
            )
            agent_branches = [
                b.strip().lstrip("* ")
                for b in branches_proc.stdout.splitlines()
                if b.strip()
            ]

            status = {
                "workspace_root": str(REPO_ROOT),
                "active_worktrees": active_worktrees,
                "agent_branches": agent_branches,
                "configured_max_agents": int(os.getenv("MAX_AGENTS", "3")),
                "configured_queue_limit": int(
                    os.getenv(
                        "QUEUE_LIMIT_PER_AGENT",
                        os.getenv("AGENT_QUEUE_LIMIT", os.getenv("MAX_QUEUE_SIZE", "3"))
                    )
                ),
                "api_key_configured": bool(os.getenv("GEMINI_API_KEY")),
            }
            return json.dumps(status, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @server.tool(
        name="swarm_get_worktree_diff",
        description=(
            "Review the isolated Git diff patch generated by a worker agent for a specific ticket. "
            "Use this to review code before approving a merge to main."
        ),
    )
    def swarm_get_worktree_diff(ticket_id: str) -> str:
        clean_id = ticket_id.lower().replace("tick-", "")
        # Target worktree path
        wt_name = f"ticket-tick-{clean_id}"
        worktree_path = REPO_ROOT / ".worktrees" / wt_name
        if not worktree_path.exists():
            # Check alternative naming
            wt_name = f"ticket-{clean_id}"
            worktree_path = REPO_ROOT / ".worktrees" / wt_name

        if not worktree_path.exists():
            return json.dumps({
                "error": f"Worktree directory not found for ticket '{ticket_id}'.",
                "searched_paths": [str(worktree_path)],
            }, indent=2)

        try:
            # First git status in worktree
            status_res = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Git diff against main
            diff_res = subprocess.run(
                ["git", "diff", "main"],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=15,
            )

            return json.dumps({
                "ticket_id": ticket_id,
                "worktree_path": str(worktree_path),
                "uncommitted_files": status_res.stdout.splitlines(),
                "diff": diff_res.stdout or "(No diff from main)",
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @server.tool(
        name="swarm_merge_worktree",
        description=(
            "Approve and merge a completed ticket's worktree branch into main (or specified branch) "
            "and prune the isolated worktree."
        ),
    )
    def swarm_merge_worktree(ticket_id: str, target_branch: str = "main") -> str:
        clean_id = ticket_id.lower().replace("tick-", "")
        formatted_id = f"TICK-{clean_id.upper()}"
        try:
            merge_worktree(REPO_ROOT, formatted_id, target_branch=target_branch)
            prune_worktrees(REPO_ROOT)
            return json.dumps({
                "status": "MERGED",
                "ticket_id": formatted_id,
                "target_branch": target_branch,
                "message": f"Successfully merged ticket {formatted_id} into {target_branch}.",
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "FAILED",
                "ticket_id": formatted_id,
                "error": str(e),
            }, indent=2)

    return server


def main() -> None:
    """Run the MCP server over standard stdio."""
    server = create_mcp_server()
    server.run()


if __name__ == "__main__":
    main()

"""
Main Orchestrator for Multi-Agent Ticket System.
Identifies problems from user objectives, generates discrete tickets,
and dispatches them to agents with a strict per-agent queue limit of 3.
Agents process tasks synchronously one by one.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Callable, Any
from dotenv import find_dotenv, load_dotenv
from google import genai
from google.genai import types

from .ticket import Ticket, TicketStatus, TicketDAG
from .agent_worker import AgentWorker, QueueFullError
from .run_logger import SwarmRunLogger
from ..common.config import SwarmConfig, resolve_workspace, parse_token_limit
from ..common.token_budget import TokenBudget, TokenBudgetExceeded, usage_from_response
from ..common.logging_config import setup_logging

load_dotenv(find_dotenv())
logger = setup_logging(__name__)

_UNSET: Any = object()


class MainOrchestrator:
    """
    Coordinates work distribution across worker agents:
    - Launches worker agents (up to MAX_AGENTS from .env, default 3).
    - Analyzes high-level problems and creates discrete tickets.
    - Dispatches tickets into agent queues (strict limit of 3 per agent).
    - Orchestrates synchronous execution so agents work one ticket at a time.
    """

    def __init__(
        self,
        max_agents: int | None = None,
        queue_limit_per_agent: int | None = None,
        model: str | None = None,
        api_key: str | None = None,
        workspace_root: Path | str | None = None,
        token_limit: Any = _UNSET,
        objective: str = "",
    ) -> None:
        self.config = SwarmConfig.from_env()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        # Workspace: explicit argument > TARGET_WORKSPACE > cwd. Agents edit it IN PLACE.
        self.workspace_root = resolve_workspace(workspace_root)
        self.model = model or self.config.model_name
        self.token_limit: int | None = (
            self.config.token_usage_limit if token_limit is _UNSET else parse_token_limit(token_limit)
        )
        self.token_budget = TokenBudget(self.token_limit)
        
        # Read max_agents from argument or .env (MAX_AGENTS / MAX_ACTIVE_AGENTS, default: 3)
        if max_agents is None:
            raw_val = os.getenv("MAX_AGENTS", os.getenv("MAX_ACTIVE_AGENTS", "3")).strip()
            try:
                self.max_agents = max(1, int(raw_val))
            except ValueError:
                self.max_agents = 3
        else:
            self.max_agents = max(1, max_agents)

        # Read queue_limit_per_agent from argument or .env (QUEUE_LIMIT_PER_AGENT / AGENT_QUEUE_LIMIT / MAX_QUEUE_SIZE, default: 3)
        if queue_limit_per_agent is None:
            raw_queue = os.getenv(
                "QUEUE_LIMIT_PER_AGENT",
                os.getenv("AGENT_QUEUE_LIMIT", os.getenv("MAX_QUEUE_SIZE", "3"))
            ).strip()
            try:
                self.queue_limit_per_agent = max(1, int(raw_queue))
            except ValueError:
                self.queue_limit_per_agent = 3
        else:
            self.queue_limit_per_agent = max(1, queue_limit_per_agent)

        # Pending backlog when all agents' queues are at capacity
        self.pending_backlog: list[Ticket] = []
        self.all_tickets: list[Ticket] = []

        # Client for problem decomposition
        self._client: genai.Client | None = None

        self.run_logger = SwarmRunLogger(
            self.config.log_dir,
            objective=objective,
            workspace_root=self.workspace_root,
            model=self.model,
            token_limit=self.token_limit,
            max_agents=self.max_agents,
            queue_limit=self.queue_limit_per_agent,
        )
        self.run_id = self.run_logger.run_id
        logger.info("Swarm run %s | workspace=%s | model=%s | token_limit=%s",
                    self.run_id, self.workspace_root, self.model,
                    "unlimited" if self.token_limit is None else self.token_limit)

        # Start and initialize all worker agents
        self.agents: list[AgentWorker] = []
        self._init_agents()

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not self.api_key:
                self.api_key = os.getenv("GEMINI_API_KEY", "")
            self._client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        return self._client

    def _init_agents(self) -> None:
        """Start all worker agents up to max_agents."""
        roles = [
            ("Agent-1", "Code Navigator & System Analyst", "analysis"),
            ("Agent-2", "Core Implementation & Coding Engineer", "coding"),
            ("Agent-3", "Test Automation & Validation Engineer", "testing"),
            ("Agent-4", "Refactoring & Performance Engineer", "refactor"),
            ("Agent-5", "Documentation & Architecture Specialist", "docs"),
        ]

        logger.info("Main Orchestrator launching %d agents (queue limit: %d each)...",
                    self.max_agents, self.queue_limit_per_agent)

        names = self.config.agent_names
        for i in range(self.max_agents):
            role_meta = roles[i % len(roles)]
            agent_id = names[i] if i < len(names) else f"Agent-{i+1}"
            worker = AgentWorker(
                agent_id=agent_id,
                role=role_meta[1],
                specialty=role_meta[2],
                queue_limit=self.queue_limit_per_agent,
                model=self.model,
                api_key=self.api_key,
                workspace_root=self.workspace_root,
                token_budget=self.token_budget,
                run_logger=self.run_logger,
            )
            self.agents.append(worker)

    def _note_objective(self, objective: str) -> None:
        if objective and not getattr(self.run_logger, "objective", ""):
            self.run_logger.objective = objective

    def identify_problems_and_create_tickets(self, objective: str) -> list[Ticket]:
        """
        Main orchestrator analyzes the high-level objective, decomposes it into
        distinct technical problems, and raises tickets.
        """
        logger.info("Main Orchestrator decomposing objective: %s", objective)
        self._note_objective(objective)

        prompt = f"""You are the Main Orchestrator of an autonomous multi-agent coding team.
Analyze the following objective and break it down into 2 to 6 concrete, independent problem tickets.

OBJECTIVE:
{objective}

Categories should be one of: "analysis", "coding", "testing", "refactor", "docs".

Respond ONLY with a JSON array of ticket objects:
[
  {{
    "title": "Short descriptive title",
    "description": "Specific problem statement and requirements",
    "category": "analysis" | "coding" | "testing" | "refactor" | "docs"
  }}
]"""

        tickets: list[Ticket] = []
        try:
            if self.api_key and not self.api_key.startswith("dummy"):
                self.token_budget.check()
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction="You are a Chief Software Architect and Orchestrator. Output valid JSON array only."
                    )
                )
                p, c, tot = usage_from_response(response)
                self.token_budget.record(tot)
                self.run_logger.llm_usage("orchestrator", None, p, c, tot, self.token_budget.used)
                text = (response.text or "").strip()
                match = re.search(r"\[.*\]", text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    for item in parsed:
                        ticket = Ticket.create(
                            title=item.get("title", "Untitled Ticket"),
                            description=item.get("description", ""),
                            category=item.get("category", "coding"),
                        )
                        tickets.append(ticket)
        except Exception as e:
            logger.warning("LLM ticket decomposition error: %s (falling back to heuristic decomposition)", e)

        # Fallback heuristic decomposition if LLM did not produce tickets
        if not tickets:
            tickets = self._heuristic_problem_decomposition(objective)

        for t in tickets:
            self.all_tickets.append(t)
            self.pending_backlog.append(t)
            self.run_logger.ticket_created(t)

        logger.info("Main Orchestrator identified and raised %d tickets.", len(tickets))
        return tickets

    def _heuristic_problem_decomposition(self, objective: str) -> list[Ticket]:
        """Rule-based breakdown when LLM is unavailable or in offline test mode."""
        lines = [line.strip().lstrip("-*123456789. ") for line in objective.splitlines() if line.strip()]
        if len(lines) > 1:
            tickets = []
            for i, line in enumerate(lines[:5]):
                cat = "analysis" if i == 0 else ("testing" if "test" in line.lower() else "coding")
                tickets.append(Ticket.create(title=line[:50], description=line, category=cat))
            return tickets

        # Default standard 3-phase decomposition for single-line objective
        return [
            Ticket.create(
                title=f"Analyze requirements for: {objective[:40]}",
                description=f"Inspect system architecture, dependencies, and requirements for: {objective}",
                category="analysis",
            ),
            Ticket.create(
                title=f"Implement changes for: {objective[:40]}",
                description=f"Implement code logic, functions, or fixes needed for: {objective}",
                category="coding",
            ),
            Ticket.create(
                title=f"Validate and test: {objective[:40]}",
                description=f"Write tests, verify syntax, and confirm solution for: {objective}",
                category="testing",
            ),
        ]

    def dispatch_ticket(self, ticket: Ticket) -> AgentWorker | None:
        """
        Dispatch a single ticket to the most suitable agent that has queue capacity (< 3).
        Priority:
        1. Agent matching ticket category/specialty with queue < 3.
        2. Any agent with the shortest queue (< 3).
        3. If all agents are full (each has 3 queued), remains in pending_backlog.
        """
        # Candidate agents with capacity
        available_agents = [a for a in self.agents if a.can_accept_ticket()]
        if not available_agents:
            logger.info("All agent queues are full (limit %d). Ticket %s held in backlog.",
                        self.queue_limit_per_agent, ticket.id)
            return None

        # 1. Match by specialty
        specialty_match = [a for a in available_agents if a.specialty == ticket.category]
        if specialty_match:
            chosen_agent = min(specialty_match, key=lambda a: a.queue_size)
        else:
            # 2. Pick agent with fewest queued items
            chosen_agent = min(available_agents, key=lambda a: a.queue_size)

        chosen_agent.enqueue_ticket(ticket)
        if ticket in self.pending_backlog:
            self.pending_backlog.remove(ticket)

        return chosen_agent

    def dispatch_all_pending(self) -> int:
        """Attempt to dispatch all pending backlog tickets to agents with capacity."""
        dispatched_count = 0
        self._propagate_blocked()
        backlog_copy = list(self.pending_backlog)
        for ticket in backlog_copy:
            if not self._deps_satisfied(ticket):
                continue
            agent = self.dispatch_ticket(ticket)
            if agent:
                dispatched_count += 1
        return dispatched_count

    # ------------------------------------------------------------ dependencies
    def _ticket_by_id(self) -> dict[str, Ticket]:
        return {t.id: t for t in self.all_tickets}

    def _deps_satisfied(self, ticket: Ticket) -> bool:
        by_id = self._ticket_by_id()
        return all(
            (d in by_id and by_id[d].status == TicketStatus.RESOLVED) for d in ticket.depends_on
        )

    def _block(self, ticket: Ticket, reason: str, code: str) -> None:
        ticket.mark_blocked(reason, code)
        if ticket in self.pending_backlog:
            self.pending_backlog.remove(ticket)
        for agent in self.agents:
            if ticket in agent.queue:
                agent.queue.remove(ticket)
        logger.warning("Ticket [%s] BLOCKED (%s): %s", ticket.id, code, reason)
        self.run_logger.ticket_blocked(ticket, reason, code)

    def _propagate_blocked(self) -> None:
        """Block backlog tickets whose dependency failed, was blocked, or does not exist."""
        changed = True
        while changed:
            changed = False
            by_id = self._ticket_by_id()
            for t in list(self.pending_backlog):
                for d in t.depends_on:
                    dep = by_id.get(d)
                    if dep is None:
                        self._block(t, f"Unknown dependency '{d}'", "DEPENDENCY_FAILED")
                    elif dep.status in (TicketStatus.FAILED, TicketStatus.BLOCKED):
                        self._block(t, f"Dependency '{d}' is {dep.status.value}", "DEPENDENCY_FAILED")
                    else:
                        continue
                    changed = True
                    break

    def _abort_for_budget(self) -> None:
        reason = "Token budget exhausted before this ticket could run"
        for t in list(self.pending_backlog):
            self._block(t, reason, "TOKEN_BUDGET_EXHAUSTED")
        for agent in self.agents:
            for t in list(agent.queue):
                self._block(t, reason, "TOKEN_BUDGET_EXHAUSTED")

    def process_all_tickets_synchronously(
        self,
        on_step_callback: Callable[[Ticket], None] | None = None
    ) -> list[Ticket]:
        """
        Executes tickets strictly one by one (synchronously per agent).
        Round-robin steps across agents to process their current front ticket,
        re-fills opened queue slots from backlog, and continues until all tickets are RESOLVED.
        """
        resolved_tickets: list[Ticket] = []

        # Initial dispatch into available queues (only tickets whose dependencies are done)
        self.dispatch_all_pending()

        # Synchronous execution loop:
        # Loop until all tickets in all queues and pending backlog are processed
        while any(a.queue_size > 0 for a in self.agents) or self.pending_backlog:
            work_done_in_round = False

            for agent in self.agents:
                if self.token_budget.exhausted:
                    self._abort_for_budget()
                    break
                if agent.queue_size > 0:
                    # Agent processes its next ticket strictly synchronously
                    completed = agent.process_next_ticket(callback=on_step_callback)
                    if completed:
                        resolved_tickets.append(completed)
                        work_done_in_round = True

                    # Fill freed slots / unlock dependents / block failed chains
                    self.dispatch_all_pending()

            if self.token_budget.exhausted:
                self._abort_for_budget()
                break

            if not work_done_in_round and self.pending_backlog:
                # Deadlock guard: backlog can never be dispatched (e.g. dependency cycle)
                for t in list(self.pending_backlog):
                    self._block(t, "Dependencies can never be satisfied", "DEPENDENCY_FAILED")
                break

        self.run_logger.finalize(self.get_summary())
        return resolved_tickets

    def load_manifest(self, manifest_data: list[dict[str, Any]] | dict[str, Any]) -> list[Ticket]:
        """
        Load an explicit DAG of tickets from a manifest (e.g. prepared by Antigravity or JSON file).
        Validates dependencies using Kahn's algorithm before queueing.
        """
        raw_tickets = manifest_data.get("tickets", []) if isinstance(manifest_data, dict) else manifest_data
        loaded: list[Ticket] = []

        for item in raw_tickets:
            t_id = item.get("id")
            title = item.get("title", "Untitled Ticket")
            desc = item.get("description", "")
            cat = item.get("category", "coding")
            deps = item.get("depends_on", [])

            if t_id:
                t = Ticket(
                    id=t_id,
                    title=title,
                    description=desc,
                    category=cat,
                    depends_on=list(deps),
                )
            else:
                t = Ticket.create(
                    title=title,
                    description=desc,
                    category=cat,
                    depends_on=list(deps),
                )
            loaded.append(t)

        # Validate DAG dependencies across the loaded tickets
        if loaded:
            TicketDAG(loaded)

        for t in loaded:
            self.all_tickets.append(t)
            self.pending_backlog.append(t)
            self.run_logger.ticket_created(t)

        logger.info("Main Orchestrator loaded and validated %d manifest tickets.", len(loaded))
        return loaded

    def get_summary(self) -> dict[str, Any]:
        """Return a structured summary of the ticket system state."""
        total = len(self.all_tickets)
        resolved = sum(1 for t in self.all_tickets if t.status == TicketStatus.RESOLVED)
        failed = sum(1 for t in self.all_tickets if t.status == TicketStatus.FAILED)
        blocked = sum(1 for t in self.all_tickets if t.status == TicketStatus.BLOCKED)
        in_progress = sum(1 for t in self.all_tickets if t.status == TicketStatus.IN_PROGRESS)
        queued = sum(a.queue_size for a in self.agents)
        backlog = len(self.pending_backlog)

        return {
            "run_id": self.run_id,
            "model": self.model,
            "workspace_root": str(self.workspace_root),
            "token_usage": self.token_budget.snapshot(),
            "log_dir": str(self.run_logger.run_dir),
            "total_tickets": total,
            "resolved": resolved,
            "failed": failed,
            "blocked": blocked,
            "in_progress": in_progress,
            "queued": queued,
            "backlog": backlog,
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "role": a.role,
                    "specialty": a.specialty,
                    "queue_size": a.queue_size,
                    "queue_limit": a.queue_limit,
                    "current_ticket": a.current_ticket.id if a.current_ticket else None,
                    "tickets_assigned": sum(1 for t in self.all_tickets if t.assigned_agent_id == a.agent_id),
                    "completed_count": sum(1 for t in a.history if t.status == TicketStatus.RESOLVED),
                    "failed_count": sum(1 for t in a.history if t.status == TicketStatus.FAILED),
                    "tokens_used": a.tokens_used,
                }
                for a in self.agents
            ],
            "tickets": [
                {
                    "id": t.id,
                    "title": t.title,
                    "category": t.category,
                    "status": t.status.value,
                    "depends_on": t.depends_on,
                    "assigned_agent_id": t.assigned_agent_id,
                    "duration_seconds": t.duration_seconds,
                    "tokens_used": t.tokens_used,
                    "tool_calls": t.tool_calls,
                    "failure_code": t.failure_code,
                    "result": t.result,
                    "error": t.error,
                }
                for t in self.all_tickets
            ],
        }


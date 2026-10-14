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
from typing import Callable, Any
from google import genai
from google.genai import types

from .ticket import Ticket, TicketStatus
from .agent_worker import AgentWorker, QueueFullError
from ..common.logging_config import setup_logging

logger = setup_logging(__name__)


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
        queue_limit_per_agent: int = 3,
        model: str = "gemini-2.5-flash-lite",
        api_key: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model
        self.queue_limit_per_agent = queue_limit_per_agent
        
        # Read limit from .env or argument
        if max_agents is None:
            raw_val = os.getenv("MAX_AGENTS", os.getenv("MAX_ACTIVE_AGENTS", "3")).strip()
            try:
                self.max_agents = max(1, int(raw_val))
            except ValueError:
                self.max_agents = 3
        else:
            self.max_agents = max(1, max_agents)

        # Pending backlog when all agents' queues are at capacity (limit 3)
        self.pending_backlog: list[Ticket] = []
        self.all_tickets: list[Ticket] = []

        # Client for problem decomposition
        self._client: genai.Client | None = None

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

        for i in range(self.max_agents):
            role_meta = roles[i % len(roles)]
            agent_id = f"Agent-{i+1}"
            worker = AgentWorker(
                agent_id=agent_id,
                role=role_meta[1],
                specialty=role_meta[2],
                queue_limit=self.queue_limit_per_agent,
                model=self.model,
                api_key=self.api_key,
            )
            self.agents.append(worker)

    def identify_problems_and_create_tickets(self, objective: str) -> list[Ticket]:
        """
        Main orchestrator analyzes the high-level objective, decomposes it into
        distinct technical problems, and raises tickets.
        """
        logger.info("Main Orchestrator decomposing objective: %s", objective)

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
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction="You are a Chief Software Architect and Orchestrator. Output valid JSON array only."
                    )
                )
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
        backlog_copy = list(self.pending_backlog)
        for ticket in backlog_copy:
            agent = self.dispatch_ticket(ticket)
            if agent:
                dispatched_count += 1
        return dispatched_count

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

        # Initial dispatch into available queues (up to 3 per agent)
        self.dispatch_all_pending()

        # Synchronous execution loop:
        # Loop until all tickets in all queues and pending backlog are processed
        while any(a.queue_size > 0 for a in self.agents) or self.pending_backlog:
            work_done_in_round = False

            for agent in self.agents:
                if agent.queue_size > 0:
                    # Agent processes its next ticket strictly synchronously
                    completed = agent.process_next_ticket(callback=on_step_callback)
                    if completed:
                        resolved_tickets.append(completed)
                        work_done_in_round = True

                    # After an agent finishes a ticket, its queue has a free slot!
                    # Fill it from pending backlog if any are waiting
                    self.dispatch_all_pending()

            if not work_done_in_round and self.pending_backlog:
                # If backlog cannot be dispatched and no queue has items (should not happen)
                break

        return resolved_tickets

    def get_summary(self) -> dict[str, Any]:
        """Return a structured summary of the ticket system state."""
        total = len(self.all_tickets)
        resolved = sum(1 for t in self.all_tickets if t.status == TicketStatus.RESOLVED)
        failed = sum(1 for t in self.all_tickets if t.status == TicketStatus.FAILED)
        in_progress = sum(1 for t in self.all_tickets if t.status == TicketStatus.IN_PROGRESS)
        queued = sum(a.queue_size for a in self.agents)
        backlog = len(self.pending_backlog)

        return {
            "total_tickets": total,
            "resolved": resolved,
            "failed": failed,
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
                    "completed_count": len(a.history),
                }
                for a in self.agents
            ]
        }

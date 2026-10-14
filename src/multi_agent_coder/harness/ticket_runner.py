"""
Harness Ticket Runner.
Enables running the multi-agent ticket system with any LLM adapter attached via the harness,
completely separate and independent of the main API agent.
"""

import time
from typing import Any

from ..orchestrator.ticket import Ticket, TicketStatus
from ..common.logging_config import setup_logging
from .base import BaseLLMAdapter
from .engine import HarnessAgent, AgentRunResult

logger = setup_logging(__name__)

QUEUE_LIMIT_DEFAULT = 3


class HarnessTicketWorker:
    """
    Ticket Worker powered by any harness-attached LLM adapter.
    Enforces the 3-ticket queue limit and synchronous FIFO ticket resolution.
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        adapter: BaseLLMAdapter,
        specialty: str = "general",
        queue_limit: int = QUEUE_LIMIT_DEFAULT,
        harness_agent: HarnessAgent | None = None,
        console: Any | None = None,
    ):
        self.agent_id = agent_id
        self.role = role
        self.adapter = adapter
        self.specialty = specialty
        self.queue_limit = queue_limit
        self.console = console

        self.queue: list[Ticket] = []
        self.current_ticket: Ticket | None = None
        self.history: list[Ticket] = []
        self.run_results: dict[str, AgentRunResult] = {}

        if harness_agent:
            self.harness_agent = harness_agent
        else:
            self.harness_agent = HarnessAgent.with_codebase_tools(
                adapter=self.adapter,
                console=self.console,
            )

    @property
    def queue_size(self) -> int:
        return len(self.queue)

    @property
    def is_full(self) -> bool:
        return len(self.queue) >= self.queue_limit

    def can_accept_ticket(self) -> bool:
        """Check if this agent worker has capacity (queue limit: 3)."""
        return len(self.queue) < self.queue_limit

    def enqueue_ticket(self, ticket: Ticket) -> bool:
        """
        Add a ticket to this worker's queue.
        Raises ValueError if queue is at capacity.
        """
        if len(self.queue) >= self.queue_limit:
            raise ValueError(
                f"Agent '{self.agent_id}' queue full ({len(self.queue)}/{self.queue_limit})."
            )

        ticket.mark_queued(self.agent_id)
        self.queue.append(ticket)
        logger.info(
            "HarnessWorker [%s] queued ticket [%s]: %s (Queue: %d/%d)",
            self.agent_id, ticket.id, ticket.title, len(self.queue), self.queue_limit,
        )
        return True

    def process_next_ticket(self) -> Ticket | None:
        """
        Pop the next ticket from the queue and execute it synchronously using the attached LLM.
        """
        if not self.queue:
            return None

        ticket = self.queue.pop(0)
        self.current_ticket = ticket
        ticket.mark_in_progress()

        logger.info(
            "HarnessWorker [%s] STARTED ticket [%s]: %s",
            self.agent_id, ticket.id, ticket.title,
        )

        prompt = (
            f"You are {self.agent_id} ({self.role}, specialty: {self.specialty}).\n"
            f"Solve the following ticket:\n"
            f"Ticket ID: {ticket.id}\n"
            f"Title: {ticket.title}\n"
            f"Description: {ticket.description}\n"
            f"Category: {ticket.category}\n"
        )

        start_time = time.perf_counter()
        run_res = self.harness_agent.run(prompt)
        elapsed = time.perf_counter() - start_time

        self.run_results[ticket.id] = run_res

        if run_res.success:
            resolution = run_res.final_answer or f"Resolved by {self.agent_id} ({len(run_res.tools_invoked)} tool calls)"
            ticket.mark_resolved(resolution)
            logger.info(
                "HarnessWorker [%s] RESOLVED ticket [%s] in %.2fs",
                self.agent_id, ticket.id, elapsed,
            )
        else:
            ticket.mark_failed(run_res.error or "Unknown failure during execution")
            logger.error(
                "HarnessWorker [%s] FAILED ticket [%s]: %s",
                self.agent_id, ticket.id, run_res.error,
            )

        self.history.append(ticket)
        self.current_ticket = None
        return ticket

    def run_all_tickets_sync(self) -> list[Ticket]:
        """Process all queued tickets synchronously in FIFO order."""
        processed = []
        while self.queue:
            t = self.process_next_ticket()
            if t:
                processed.append(t)
        return processed

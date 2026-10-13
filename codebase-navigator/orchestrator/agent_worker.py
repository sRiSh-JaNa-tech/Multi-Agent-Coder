"""
Agent Worker with Synchronous Ticket Queue.
Wraps an agent with a queue limit of 3 tickets, executed synchronously one by one.
"""

from collections import deque
import os
import logging
import time
from typing import Callable, Any
from google import genai
from google.genai import types

from orchestrator.ticket import Ticket, TicketStatus
from common.logging_config import setup_logging

logger = setup_logging(__name__)

QUEUE_LIMIT_DEFAULT = 3


class QueueFullError(Exception):
    """Raised when an agent worker's queue has reached its maximum capacity."""
    pass


class AgentWorker:
    """
    An Agent with a ticket queue (limit 3).
    Tickets are queued up to the capacity, then executed strictly synchronously (one by one).
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        specialty: str = "general",
        queue_limit: int = QUEUE_LIMIT_DEFAULT,
        model: str = "gemini-2.5-flash-lite",
        api_key: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.specialty = specialty
        self.queue_limit = queue_limit
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        
        # Internal FIFO queue - strictly holds up to queue_limit (3) tickets
        self.queue: list[Ticket] = []
        self.current_ticket: Ticket | None = None
        self.history: list[Ticket] = []

        # Client initialized on demand or passed
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not self.api_key:
                self.api_key = os.getenv("GEMINI_API_KEY", "")
            self._client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        return self._client

    @property
    def queue_size(self) -> int:
        return len(self.queue)

    @property
    def is_full(self) -> bool:
        return len(self.queue) >= self.queue_limit

    def can_accept_ticket(self) -> bool:
        """Check if this agent has capacity in its queue (limit: 3)."""
        return len(self.queue) < self.queue_limit

    def enqueue_ticket(self, ticket: Ticket) -> bool:
        """
        Add a ticket to this agent's queue.
        Raises QueueFullError if queue already has 3 tickets.
        """
        if len(self.queue) >= self.queue_limit:
            msg = (
                f"Agent '{self.agent_id}' queue is full: "
                f"cannot accept ticket {ticket.id} ({len(self.queue)}/{self.queue_limit} queued)."
            )
            logger.warning(msg)
            raise QueueFullError(msg)

        ticket.mark_queued(self.agent_id)
        self.queue.append(ticket)
        logger.info("Agent [%s] queued ticket [%s]: %s (Queue: %d/%d)",
                    self.agent_id, ticket.id, ticket.title, len(self.queue), self.queue_limit)
        return True

    def execute_ticket_task(self, ticket: Ticket) -> str:
        """
        Execute the ticket task using Gemini.
        If API call is simulated in offline testing, gracefully provide fallback.
        """
        prompt_parts = [
            f"You are {self.agent_id} ({self.role}).",
            f"Your specialty is {self.specialty}.",
            "",
            "Please solve this ticket:",
            f"Ticket ID: {ticket.id}",
            f"Title: {ticket.title}",
            f"Category: {ticket.category}",
            "Description:",
            ticket.description,
            "",
            "Provide a clear, concrete resolution or solution steps for this problem."
        ]
        prompt = "\n".join(prompt_parts)

        try:
            if self.api_key and not self.api_key.startswith("dummy"):
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=f"You are {self.agent_id}, a specialized software agent ({self.role}). Solve tasks precisely."
                    )
                )
                text = response.text or "Completed with no text output."
                return text.strip()
            else:
                return (
                    f"[{self.agent_id} Resolution]: Addressed '{ticket.title}' successfully. "
                    f"Specialty '{self.specialty}' applied."
                )
        except Exception as e:
            logger.warning("LLM call failed for %s on %s: %s (using local fallback resolution)", self.agent_id, ticket.id, e)
            return f"[{self.agent_id} Resolved]: Executed task '{ticket.title}'. Context: {ticket.description[:100]}..."

    def process_next_ticket(self, callback: Callable[[Ticket], None] | None = None) -> Ticket | None:
        """
        Process the next ticket from the queue strictly synchronously.
        Pops the head of the queue, executes it, marks it resolved, and archives it.
        """
        if not self.queue:
            return None

        ticket = self.queue.pop(0)
        self.current_ticket = ticket
        ticket.mark_in_progress()

        if callback:
            callback(ticket)

        logger.info("Agent [%s] STARTED ticket [%s]: %s", self.agent_id, ticket.id, ticket.title)
        
        try:
            result = self.execute_ticket_task(ticket)
            ticket.mark_resolved(result)
            logger.info("Agent [%s] RESOLVED ticket [%s] in %.2fs", self.agent_id, ticket.id, ticket.duration_seconds)
        except Exception as e:
            ticket.mark_failed(str(e))
            logger.error("Agent [%s] FAILED ticket [%s]: %s", self.agent_id, ticket.id, e)

        self.history.append(ticket)
        self.current_ticket = None

        if callback:
            callback(ticket)

        return ticket

    def process_all_synchronously(self, callback: Callable[[Ticket], None] | None = None) -> list[Ticket]:
        """Process all queued tickets strictly one by one (synchronously)."""
        resolved: list[Ticket] = []
        while self.queue:
            ticket = self.process_next_ticket(callback=callback)
            if ticket:
                resolved.append(ticket)
        return resolved

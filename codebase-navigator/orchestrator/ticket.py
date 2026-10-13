"""
Ticket Model and Lifecycle Status.
Defines work items raised by the Main Orchestrator and queued for Agents.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
import uuid


class TicketStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


@dataclass
class Ticket:
    """Represents a discrete work item identified by the Main Orchestrator."""
    id: str
    title: str
    description: str
    category: str = "general"          # e.g., "explore", "coding", "testing", "refactor"
    status: TicketStatus = TicketStatus.PENDING
    assigned_agent_id: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: str | None = None
    error: str | None = None

    @classmethod
    def create(cls, title: str, description: str, category: str = "general") -> "Ticket":
        ticket_id = f"TICK-{uuid.uuid4().hex[:6].upper()}"
        return cls(id=ticket_id, title=title, description=description, category=category)

    def mark_queued(self, agent_id: str) -> None:
        self.assigned_agent_id = agent_id
        self.status = TicketStatus.QUEUED

    def mark_in_progress(self) -> None:
        self.status = TicketStatus.IN_PROGRESS
        self.started_at = time.time()

    def mark_resolved(self, result: str) -> None:
        self.status = TicketStatus.RESOLVED
        self.result = result
        self.completed_at = time.time()

    def mark_failed(self, error: str) -> None:
        self.status = TicketStatus.FAILED
        self.error = error
        self.completed_at = time.time()

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return round(self.completed_at - self.started_at, 2)
        return 0.0

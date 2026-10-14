"""
Ticket Model and DAG Dependency State Machine.
Defines work items raised by the Main Orchestrator, manages DAG dependencies,
detects circular dependencies with Kahn's algorithm, and propagates BLOCKED status.
"""

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import time
import uuid


class TicketStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    RESOLVED = "COMPLETED"  # Backward compatibility alias
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    QUEUED = "IN_PROGRESS"  # Backward compatibility alias


@dataclass
class Ticket:
    """Represents a discrete work item managed by the Main Orchestrator."""
    id: str
    title: str
    description: str
    category: str = "general"          # e.g., "explore", "coding", "testing", "refactor"
    depends_on: list[str] = field(default_factory=list)
    status: TicketStatus = TicketStatus.PENDING
    assigned_agent_id: str | None = None
    retries: int = 0
    max_retries: int = 2
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: str | None = None
    error: str | None = None
    error_log: str | None = None

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        category: str = "general",
        depends_on: list[str] | None = None,
    ) -> "Ticket":
        ticket_id = f"TICK-{uuid.uuid4().hex[:6].upper()}"
        return cls(
            id=ticket_id,
            title=title,
            description=description,
            category=category,
            depends_on=list(depends_on or []),
        )

    def mark_queued(self, agent_id: str) -> None:
        self.assigned_agent_id = agent_id
        if self.status in (TicketStatus.PENDING, TicketStatus.READY):
            self.status = TicketStatus.IN_PROGRESS

    def mark_in_progress(self) -> None:
        self.status = TicketStatus.IN_PROGRESS
        self.started_at = time.time()

    def mark_resolved(self, result: str) -> None:
        self.status = TicketStatus.COMPLETED
        self.result = result
        self.completed_at = time.time()

    def mark_failed(self, error: str) -> None:
        self.status = TicketStatus.FAILED
        self.error = error
        self.error_log = error
        self.completed_at = time.time()

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return round(self.completed_at - self.started_at, 2)
        if self.started_at:
            return round(time.time() - self.started_at, 2)
        return 0.0


class TicketDAG:
    """
    Direct Acyclic Graph (DAG) state machine for ticket scheduling.
    Validates ticket dependencies, rejects circular references via Kahn's algorithm,
    and identifies tickets ready for execution while propagating BLOCKED status.
    """

    def __init__(self, tickets: list[Ticket]):
        self.tickets: dict[str, Ticket] = {t.id: t for t in tickets}
        self._validate_dag()

    def _validate_dag(self) -> None:
        # Check for missing dependency IDs
        for t in self.tickets.values():
            for dep in t.depends_on:
                if dep not in self.tickets:
                    raise ValueError(f"Ticket '{t.id}' depends on unknown ticket '{dep}'")

        # Kahn's algorithm for cycle detection
        in_degree = {t_id: len(t.depends_on) for t_id, t in self.tickets.items()}
        queue = deque([t_id for t_id, deg in in_degree.items() if deg == 0])
        visited = 0

        while queue:
            curr = queue.popleft()
            visited += 1
            for t in self.tickets.values():
                if curr in t.depends_on:
                    in_degree[t.id] -= 1
                    if in_degree[t.id] == 0:
                        queue.append(t.id)

        if visited != len(self.tickets):
            raise ValueError("Cycle detected in ticket dependency graph")

    def get_ready_tickets(self) -> list[Ticket]:
        """Return all tickets whose upstream dependencies are completed."""
        ready = []
        for t in self.tickets.values():
            if t.status == TicketStatus.PENDING:
                deps_statuses = [self.tickets[d].status for d in t.depends_on]
                if any(s in (TicketStatus.FAILED, TicketStatus.BLOCKED) for s in deps_statuses):
                    t.status = TicketStatus.BLOCKED
                elif all(s == TicketStatus.COMPLETED for s in deps_statuses):
                    t.status = TicketStatus.READY
            if t.status == TicketStatus.READY:
                ready.append(t)
        return ready

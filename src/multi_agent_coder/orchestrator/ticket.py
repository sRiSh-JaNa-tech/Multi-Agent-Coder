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
    failure_code: str | None = None    # e.g. ITERATION_LIMIT, TOKEN_BUDGET_EXHAUSTED, LLM_ERROR
    tokens_used: int = 0
    tool_calls: int = 0
    actions: list[dict] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    target_files: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    risk_level: str = "medium"         # "low", "medium", "high", "critical"
    priority: int = 2                  # 1 (highest) to 5
    expected_deliverables: list[str] = field(default_factory=list)
    follow_up_findings: list[dict] = field(default_factory=list)
    actual_files_modified: list[str] = field(default_factory=list)
    verified: bool = False
    verification_summary: str = ""

    def record_action(
        self,
        tool: str,
        detail: str | None = None,
        status: str = "success",
    ) -> dict:
        """Record a discrete tool action taken during execution."""
        act = {
            "timestamp": time.time(),
            "tool": tool,
            "detail": detail,
            "status": status,
        }
        self.actions.append(act)
        return act

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        category: str = "general",
        depends_on: list[str] | None = None,
        finding_ids: list[str] | None = None,
        target_files: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        verification_commands: list[str] | None = None,
        risk_level: str = "medium",
        priority: int = 2,
        expected_deliverables: list[str] | None = None,
        custom_id: str | None = None,
    ) -> "Ticket":
        ticket_id = custom_id or f"TICK-{uuid.uuid4().hex[:6].upper()}"
        return cls(
            id=ticket_id,
            title=title,
            description=description,
            category=category,
            depends_on=list(depends_on or []),
            finding_ids=list(finding_ids or []),
            target_files=list(target_files or []),
            acceptance_criteria=list(acceptance_criteria or []),
            verification_commands=list(verification_commands or []),
            risk_level=risk_level,
            priority=priority,
            expected_deliverables=list(expected_deliverables or []),
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

    def mark_failed(self, error: str, code: str = "AGENT_ERROR") -> None:
        self.status = TicketStatus.FAILED
        self.error = error
        self.error_log = error
        self.failure_code = code
        self.completed_at = time.time()

    def mark_blocked(self, reason: str, code: str = "DEPENDENCY_FAILED") -> None:
        """The ticket will never run (failed upstream dependency or exhausted budget)."""
        self.status = TicketStatus.BLOCKED
        self.error = reason
        self.error_log = reason
        self.failure_code = code
        self.completed_at = time.time()

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return round(self.completed_at - self.started_at, 2)
        if self.started_at:
            return round(time.time() - self.started_at, 2)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "assigned_agent_id": self.assigned_agent_id,
            "finding_ids": self.finding_ids,
            "target_files": self.target_files,
            "acceptance_criteria": self.acceptance_criteria,
            "verification_commands": self.verification_commands,
            "risk_level": self.risk_level,
            "priority": self.priority,
            "expected_deliverables": self.expected_deliverables,
            "result": self.result,
            "error": self.error,
            "failure_code": self.failure_code,
            "tokens_used": self.tokens_used,
            "tool_calls": self.tool_calls,
            "actions": self.actions,
            "duration_seconds": self.duration_seconds,
            "follow_up_findings": self.follow_up_findings,
            "actual_files_modified": self.actual_files_modified,
            "verified": self.verified,
        }


class TicketDAG:
    """
    Direct Acyclic Graph (DAG) state machine for ticket scheduling.
    Validates ticket dependencies, rejects circular references via Kahn's algorithm,
    and identifies tickets ready for execution while propagating BLOCKED status.
    """

    def __init__(self, tickets: list[Ticket]):
        if len(tickets) != len({t.id for t in tickets}):
            raise ValueError("Duplicate ticket IDs are not allowed")
        self.tickets: dict[str, Ticket] = {t.id: t for t in tickets}
        self._validate_dag()

    def _validate_dag(self) -> None:
        # Check for missing dependency IDs
        for t in self.tickets.values():
            if len(t.depends_on) != len(set(t.depends_on)):
                raise ValueError(f"Ticket '{t.id}' contains duplicate dependencies")
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

    def add_ticket(self, ticket: Ticket) -> None:
        """Safely add a ticket to the active DAG, revalidating graph integrity."""
        if ticket.id in self.tickets:
            raise ValueError(f"Ticket '{ticket.id}' already exists in DAG")
        self.tickets[ticket.id] = ticket
        self._validate_dag()

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

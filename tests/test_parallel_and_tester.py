"""
Tests for Multi-Agent Swarm Parallel Execution and Nth-Agent Tester Architecture:
1. Nth agent designation as dedicated QA & Test Verification Engineer (e.g. Agent-5 when MAX_AGENTS=5).
2. Proper ticket routing: work tickets to workers (Agents 1..N-1), testing tickets to Nth agent.
3. Automated QA verification ticket creation for the Nth agent when coding tickets resolve.
4. Parallel execution using ThreadPoolExecutor verifying concurrent execution across agents.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from multi_agent_coder.orchestrator.ticket import Ticket, TicketStatus
from multi_agent_coder.orchestrator.agent_worker import AgentWorker
from multi_agent_coder.orchestrator.main_orchestrator import MainOrchestrator


def test_nth_agent_tester_roster_designation(tmp_path: Path):
    """With 5 agents, Agents 1-4 are workers and Agent 5 is the dedicated QA Tester."""
    orch = MainOrchestrator(max_agents=5, queue_limit_per_agent=3, workspace_root=tmp_path, api_key="dummy")
    assert len(orch.agents) == 5

    # First 4 agents are worker agents
    for i in range(4):
        agent = orch.agents[i]
        assert not agent.is_tester, f"{agent.agent_id} should not be tester"
        assert agent.specialty in ("analysis", "coding", "refactor", "docs")

    assert len(orch.worker_agents) == 4

    # The 5th agent (Nth agent) is the dedicated QA Tester
    tester = orch.tester_agent
    assert tester is not None
    assert tester.agent_id == "Agent-5"
    assert tester.is_tester is True
    assert tester.specialty == "testing"
    assert "QA" in tester.role or "Test" in tester.role


def test_nth_agent_tester_with_3_agents(tmp_path: Path):
    """With 3 agents, Agents 1-2 are workers and Agent 3 is the dedicated QA Tester."""
    orch = MainOrchestrator(max_agents=3, queue_limit_per_agent=3, workspace_root=tmp_path, api_key="dummy")
    assert len(orch.agents) == 3
    assert len(orch.worker_agents) == 2
    assert orch.tester_agent is not None
    assert orch.tester_agent.agent_id == "Agent-3"
    assert orch.tester_agent.is_tester is True


def test_ticket_routing_to_worker_vs_tester(tmp_path: Path):
    """Work tickets route to workers; testing tickets route strictly to the Nth tester agent."""
    orch = MainOrchestrator(max_agents=5, queue_limit_per_agent=3, workspace_root=tmp_path, api_key="dummy")

    t_code = Ticket.create(title="Implement Feature", description="Code feature", category="coding")
    t_test = Ticket.create(title="Verify Test Suite", description="Run tests", category="testing")

    orch.all_tickets = [t_code, t_test]
    orch.pending_backlog = [t_code, t_test]

    orch.dispatch_all_pending()

    # t_code should be on one of the worker agents (Agent-1 to Agent-4)
    assigned_code_agent = next(a for a in orch.agents if t_code in a.queue)
    assert not assigned_code_agent.is_tester
    assert assigned_code_agent.agent_id in ("Agent-1", "Agent-2", "Agent-3", "Agent-4")

    # t_test should be strictly on Agent-5 (the tester agent)
    assigned_test_agent = next(a for a in orch.agents if t_test in a.queue)
    assert assigned_test_agent.is_tester
    assert assigned_test_agent.agent_id == "Agent-5"


def test_auto_qa_verification_ticket_generation(tmp_path: Path):
    """When a worker completes a coding ticket without an existing test, QA ticket is raised for Tester."""
    orch = MainOrchestrator(max_agents=3, queue_limit_per_agent=3, workspace_root=tmp_path, api_key="dummy", auto_qa=True)

    t_code = Ticket.create(title="Implement DB Cache", description="Write cache", category="coding")
    orch.all_tickets = [t_code]
    orch.pending_backlog = [t_code]

    resolved = orch.process_all_tickets_synchronously()
    assert len(resolved) == 2  # The coding ticket + the automated QA verification ticket
    assert t_code.status == TicketStatus.RESOLVED

    qa_ticket = next(t for t in resolved if t.id == f"TICK-QA-{t_code.id}")
    assert qa_ticket.status == TicketStatus.RESOLVED
    assert qa_ticket.assigned_agent_id == "Agent-3"  # Executed by the Tester agent


def test_parallel_ticket_execution_concurrency(tmp_path: Path):
    """Verify that multiple independent tickets execute concurrently in parallel across agents."""
    orch = MainOrchestrator(max_agents=3, queue_limit_per_agent=3, workspace_root=tmp_path, api_key="dummy", auto_qa=False)

    # Mock execute_ticket_task with a 0.2s sleep to measure concurrency
    execution_times = {}

    def slow_execute(ticket):
        t_start = time.time()
        time.sleep(0.2)
        t_end = time.time()
        execution_times[ticket.id] = (t_start, t_end)
        return f"Resolved {ticket.title}"

    for a in orch.agents:
        a.execute_ticket_task = slow_execute

    t1 = Ticket.create(title="Task A", description="Parallel task A", category="coding")
    t2 = Ticket.create(title="Task B", description="Parallel task B", category="coding")

    orch.all_tickets = [t1, t2]
    orch.pending_backlog = [t1, t2]

    start_total = time.time()
    resolved = orch.process_all_tickets_parallel()
    total_duration = time.time() - start_total

    assert len(resolved) == 2
    assert t1.status == TicketStatus.RESOLVED
    assert t2.status == TicketStatus.RESOLVED

    # Verify execution times overlapped concurrently (both threads ran at the same time)
    t1_start, t1_end = execution_times[t1.id]
    t2_start, t2_end = execution_times[t2.id]
    assert t2_start < t1_end and t1_start < t2_end, "Execution times did not overlap; tasks did not run in parallel!"

    overlap = min(t1_end, t2_end) - max(t1_start, t2_start)
    assert overlap > 0.05, f"Expected significant concurrency overlap, got {overlap:.3f}s"

"""
Comprehensive Unit & Integration Tests for Multi-Agent Ticket Orchestration System.
Tests:
- Ticket model & status transitions
- Queue limit of 3 per agent & QueueFullError
- Synchronous one-by-one ticket execution
- Main Orchestrator problem decomposition and distribution
- Backlog handling under high ticket volume
"""

import os
import sys
import unittest
from pathlib import Path

# Ensure import resolution
_NAV_DIR = Path(__file__).resolve().parent
if str(_NAV_DIR) not in sys.path:
    sys.path.insert(0, str(_NAV_DIR))

from multi_agent_coder.orchestrator.ticket import Ticket, TicketStatus
from multi_agent_coder.orchestrator.agent_worker import AgentWorker, QueueFullError
from multi_agent_coder.orchestrator.main_orchestrator import MainOrchestrator


class TestTicketSystem(unittest.TestCase):
    """Test suite for Ticket System and Worker Agents."""

    def test_ticket_lifecycle(self):
        """Verify ticket state transitions from creation to resolution."""
        t = Ticket.create(title="Fix memory leak", description="Profile cache usage", category="coding")
        self.assertEqual(t.status, TicketStatus.PENDING)
        self.assertIsNone(t.assigned_agent_id)

        t.mark_queued("Agent-1")
        self.assertEqual(t.status, TicketStatus.QUEUED)
        self.assertEqual(t.assigned_agent_id, "Agent-1")

        t.mark_in_progress()
        self.assertEqual(t.status, TicketStatus.IN_PROGRESS)
        self.assertIsNotNone(t.started_at)

        t.mark_resolved("Fixed by adding weakref")
        self.assertEqual(t.status, TicketStatus.RESOLVED)
        self.assertEqual(t.result, "Fixed by adding weakref")
        self.assertIsNotNone(t.completed_at)
        self.assertGreaterEqual(t.duration_seconds, 0.0)

    def test_agent_queue_limit_enforcement(self):
        """Verify that an agent strictly accepts at most 3 tickets in its queue."""
        worker = AgentWorker(agent_id="Agent-Test", role="Tester", queue_limit=3, api_key="dummy")

        self.assertTrue(worker.can_accept_ticket())
        self.assertEqual(worker.queue_size, 0)

        # Enqueue 3 tickets
        t1 = Ticket.create("Task 1", "Desc 1")
        t2 = Ticket.create("Task 2", "Desc 2")
        t3 = Ticket.create("Task 3", "Desc 3")

        self.assertTrue(worker.enqueue_ticket(t1))
        self.assertTrue(worker.enqueue_ticket(t2))
        self.assertTrue(worker.enqueue_ticket(t3))

        self.assertEqual(worker.queue_size, 3)
        self.assertFalse(worker.can_accept_ticket())
        self.assertTrue(worker.is_full)

        # Enqueueing a 4th ticket must raise QueueFullError
        t4 = Ticket.create("Task 4", "Desc 4")
        with self.assertRaises(QueueFullError):
            worker.enqueue_ticket(t4)

    def test_synchronous_one_by_one_execution(self):
        """Verify that tickets are executed strictly one by one in FIFO order."""
        worker = AgentWorker(agent_id="Agent-Sync", role="Coder", queue_limit=3, api_key="dummy")

        t1 = Ticket.create("Task A", "First")
        t2 = Ticket.create("Task B", "Second")
        t3 = Ticket.create("Task C", "Third")

        worker.enqueue_ticket(t1)
        worker.enqueue_ticket(t2)
        worker.enqueue_ticket(t3)

        # First execution -> must be Task A
        done1 = worker.process_next_ticket()
        self.assertEqual(done1.id, t1.id)
        self.assertEqual(done1.status, TicketStatus.RESOLVED)
        self.assertEqual(worker.queue_size, 2)
        self.assertTrue(worker.can_accept_ticket())  # Slot freed!

        # Second execution -> must be Task B
        done2 = worker.process_next_ticket()
        self.assertEqual(done2.id, t2.id)
        self.assertEqual(done2.status, TicketStatus.RESOLVED)
        self.assertEqual(worker.queue_size, 1)

        # Third execution -> must be Task C
        done3 = worker.process_next_ticket()
        self.assertEqual(done3.id, t3.id)
        self.assertEqual(done3.status, TicketStatus.RESOLVED)
        self.assertEqual(worker.queue_size, 0)

        # Queue is empty now
        self.assertIsNone(worker.process_next_ticket())
        self.assertEqual(len(worker.history), 3)

    def test_main_orchestrator_initialization_and_limits(self):
        """Verify Main Orchestrator starts 3 agents and respects queue limits."""
        orchestrator = MainOrchestrator(max_agents=3, queue_limit_per_agent=3, api_key="dummy")
        self.assertEqual(len(orchestrator.agents), 3)
        for a in orchestrator.agents:
            self.assertEqual(a.queue_limit, 3)
            self.assertEqual(a.queue_size, 0)

    def test_orchestrator_dispatch_and_backlog(self):
        """Verify dispatch across agents and backlog when all queues (3x3=9) are full."""
        orchestrator = MainOrchestrator(max_agents=3, queue_limit_per_agent=3, api_key="dummy")

        # Create 11 tickets (capacity is 3 agents * 3 = 9)
        test_tickets = [Ticket.create(f"Problem {i+1}", f"Description {i+1}") for i in range(11)]
        for t in test_tickets:
            orchestrator.all_tickets.append(t)
            orchestrator.pending_backlog.append(t)

        dispatched = orchestrator.dispatch_all_pending()
        self.assertEqual(dispatched, 9)  # Exactly 9 fill the queues (3 per agent)
        self.assertEqual(len(orchestrator.pending_backlog), 2)  # 2 remain in backlog

        # All agents must be full
        for a in orchestrator.agents:
            self.assertEqual(a.queue_size, 3)
            self.assertFalse(a.can_accept_ticket())

        # Process one ticket from Agent-1
        orchestrator.agents[0].process_next_ticket()
        self.assertEqual(orchestrator.agents[0].queue_size, 2)

        # Now dispatch_all_pending should move 1 ticket from backlog into Agent-1
        dispatched_more = orchestrator.dispatch_all_pending()
        self.assertEqual(dispatched_more, 1)
        self.assertEqual(len(orchestrator.pending_backlog), 1)
        self.assertEqual(orchestrator.agents[0].queue_size, 3)

    def test_full_synchronous_orchestration_cycle(self):
        """Verify end-to-end problem decomposition, dispatch, and synchronous completion."""
        orchestrator = MainOrchestrator(max_agents=3, queue_limit_per_agent=3, api_key="dummy")

        objective = (
            "1. Analyze memory footprint\n"
            "2. Optimize vector cache\n"
            "3. Add unit tests for cache\n"
            "4. Refactor clean architecture"
        )

        tickets = orchestrator.identify_problems_and_create_tickets(objective)
        self.assertGreaterEqual(len(tickets), 3)

        # Process all tickets synchronously
        resolved = orchestrator.process_all_tickets_synchronously()
        self.assertEqual(len(resolved), len(tickets))

        summary = orchestrator.get_summary()
        self.assertEqual(summary["resolved"], len(tickets))
        self.assertEqual(summary["queued"], 0)
        self.assertEqual(summary["backlog"], 0)


if __name__ == "__main__":
    unittest.main()

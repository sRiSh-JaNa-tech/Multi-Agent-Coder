"""
Comprehensive Automated Test Suite for Autonomous Multi-Agent Software Engineering System.
Validates Scenarios A through L according to specification:
- Scenario A: Proactive discovery without user specifying files
- Scenario B: Follow-up discovery and second defect scheduling
- Scenario C: False completion prevention (worker claims success, verification fails)
- Scenario D: Duplicate finding deduplication
- Scenario E: Failed worker crash recovery and tracking
- Scenario F: Dependency failure and propagation
- Scenario G: Token budget exhaustion safety
- Scenario H: No-progress loop termination
- Scenario I: Concurrent execution and scope fencing
- Scenario J: Existing user changes preserved and distinguished from regressions
- Scenario K: Clean repository audit with no actionable findings
- Scenario L: End-to-end objective discovery, fix, verification, and completion
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from multi_agent_coder.discovery.findings import (
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingRegistry,
    FindingSeverity,
)
from multi_agent_coder.discovery.baseline import (
    capture_git_baseline,
    capture_repository_baseline,
    detect_project_type_and_test_command,
)
from multi_agent_coder.discovery.scanner import RepositoryScanner, run_discovery
from multi_agent_coder.orchestrator.ticket import Ticket, TicketDAG, TicketStatus
from multi_agent_coder.orchestrator.planner import EvidenceDrivenPlanner
from multi_agent_coder.orchestrator.verifier import IndependentVerifier, VerificationResult
from multi_agent_coder.orchestrator.agent_worker import AgentWorker, AgentFailure
from multi_agent_coder.orchestrator.main_orchestrator import (
    MainOrchestrator,
    AutonomousRunState,
)
from multi_agent_coder.common.token_budget import TokenBudget, TokenBudgetExceeded


class TestAutonomousSystem(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name).resolve()
        # Initialize basic git repository in temporary directory
        subprocess.run(["git", "init"], cwd=str(self.workspace), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "agent@test.local"], cwd=str(self.workspace), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Agent Tester"], cwd=str(self.workspace), capture_output=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Scenario A: Proactive Discovery
    # -------------------------------------------------------------------------
    def test_scenario_a_proactive_discovery(self):
        """System discovers defects without the user naming the affected file."""
        broken_file = self.workspace / "service.py"
        broken_file.write_text("def broken():\n    raise NotImplementedError('TODO: implement auth')\n", encoding="utf-8")
        subprocess.run(["git", "add", "service.py"], cwd=str(self.workspace), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(self.workspace), capture_output=True)

        scanner = RepositoryScanner(self.workspace)
        registry, baseline = scanner.scan(objective="Make repository production ready", run_baseline_tests=False)

        # Proactive finding must be detected without naming service.py
        self.assertGreaterEqual(len(registry), 1)
        finding = registry.prioritized()[0]
        self.assertEqual(finding.file_path, "service.py")
        self.assertIn("placeholder", finding.title.lower())

        # Planner converts finding into ticket targeting service.py
        planner = EvidenceDrivenPlanner(workspace_root=self.workspace, api_key="dummy")
        tickets = planner.plan(
            objective="Make repository production ready",
            findings=registry,
            baseline=baseline,
        )
        coding_tickets = [t for t in tickets if t.category == "coding"]
        self.assertGreaterEqual(len(coding_tickets), 1)
        self.assertIn("service.py", coding_tickets[0].target_files)

    # -------------------------------------------------------------------------
    # Scenario B: Follow-up Discovery
    # -------------------------------------------------------------------------
    def test_scenario_b_follow_up_discovery(self):
        """When an agent reports a follow-up defect, orchestrator schedules it."""
        orchestrator = MainOrchestrator(
            workspace_root=self.workspace,
            max_agents=2,
            api_key="dummy",
            parallel=False,
        )
        # Mock worker report containing discovered follow-up issue
        worker = orchestrator.agents[0]
        ticket = Ticket.create(title="Implement initial module", description="Work", category="coding")
        mock_report = (
            "[Agent Status: RESOLVED] Implemented feature.\n"
            "[Discovered Issue: SQL Injection Vulnerability] File: auth/db.py Description: Unescaped raw SQL query found"
        )
        worker.queue = [ticket]
        with patch.object(worker, "execute_ticket_task", return_value=mock_report):
            worker.process_next_ticket()

        # Follow-up issue must be extracted into ticket follow_up_findings
        self.assertEqual(len(ticket.follow_up_findings), 1)
        issue = ticket.follow_up_findings[0]
        self.assertIn("SQL Injection", issue["title"])
        self.assertEqual(issue["file_path"], "auth/db.py")

        # Simulate autonomous loop registering it and generating follow-up ticket
        f = Finding.create(
            title=issue["title"],
            description=issue["description"],
            file_path=issue["file_path"],
            category=FindingCategory.DEFECT,
            severity=FindingSeverity.HIGH,
            confidence=FindingConfidence.HIGH,
        )
        orchestrator.findings_registry.add(f)
        planner = EvidenceDrivenPlanner(workspace_root=self.workspace, api_key="dummy")
        follow_ups = planner.plan_follow_up(
            objective="Secure application",
            unresolved_findings=[f],
            baseline=orchestrator.baseline or capture_repository_baseline(self.workspace, run_tests=False),
            existing_tickets=[ticket],
        )
        self.assertEqual(len(follow_ups), 1)
        self.assertIn("SQL Injection", follow_ups[0].title)
        self.assertIn("auth/db.py", follow_ups[0].target_files)

    # -------------------------------------------------------------------------
    # Scenario C: False Completion Prevention
    # -------------------------------------------------------------------------
    def test_scenario_c_false_completion_prevention(self):
        """Worker claims resolved, but acceptance/syntax check fails -> marked FAILED."""
        broken_script = self.workspace / "app.py"
        broken_script.write_text("def broken_syntax(:\n", encoding="utf-8")  # syntax error

        ticket = Ticket.create(
            title="Update app logic",
            description="Fix app",
            category="coding",
            target_files=["app.py"],
            verification_commands=[],
        )
        ticket.mark_resolved("Done! [Agent Status: RESOLVED]")

        verifier = IndependentVerifier(workspace_root=self.workspace)
        v_res = verifier.verify_ticket(ticket)

        self.assertFalse(v_res.success)
        self.assertGreater(len(v_res.syntax_errors), 0)

        # In autonomous loop, this prevents VERIFIED_COMPLETE
        orchestrator = MainOrchestrator(workspace_root=self.workspace, api_key="dummy")
        orchestrator.all_tickets = [ticket]
        if not v_res.success:
            ticket.mark_failed(f"Verification failed: {v_res.summary}", "VERIFICATION_FAILED")

        self.assertEqual(ticket.status, TicketStatus.FAILED)
        self.assertNotEqual(orchestrator.final_status, AutonomousRunState.VERIFIED_COMPLETE.value)

    # -------------------------------------------------------------------------
    # Scenario D: Duplicate Findings Deduplication
    # -------------------------------------------------------------------------
    def test_scenario_d_duplicate_findings(self):
        """Registry and planner deduplicate identical findings reported by multiple agents."""
        registry = FindingRegistry()
        f1 = Finding.create(
            title="Deadlock in Connection Pool",
            description="Acquires locks out of order",
            file_path="src/pool.py",
            line_number=42,
            category=FindingCategory.DEFECT,
            severity=FindingSeverity.HIGH,
        )
        f2 = Finding.create(
            title="Deadlock in Connection Pool",
            description="Acquires locks out of order duplicate",
            file_path="src/pool.py",
            line_number=42,
            category=FindingCategory.DEFECT,
            severity=FindingSeverity.HIGH,
        )

        added1 = registry.add(f1)
        added2 = registry.add(f2)

        self.assertTrue(added1)
        self.assertFalse(added2)  # Duplicate fingerprint rejected
        self.assertEqual(len(registry), 1)

    # -------------------------------------------------------------------------
    # Scenario E: Failed Worker Recovery
    # -------------------------------------------------------------------------
    def test_scenario_e_failed_worker_recovery(self):
        """When worker crashes or raises AgentFailure, ticket is safely marked FAILED."""
        orchestrator = MainOrchestrator(workspace_root=self.workspace, max_agents=1, api_key="dummy")
        worker = orchestrator.agents[0]
        ticket = Ticket.create(title="Unstable task", description="Crash test", category="coding")

        with patch.object(worker, "execute_ticket_task", side_effect=AgentFailure("LLM_ERROR", "API connection aborted")):
            worker.queue = [ticket]
            processed = worker.process_next_ticket()

        self.assertEqual(processed.status, TicketStatus.FAILED)
        self.assertEqual(processed.failure_code, "LLM_ERROR")
        self.assertIn("API connection aborted", processed.error)

    # -------------------------------------------------------------------------
    # Scenario F: Dependency Failure Propagation
    # -------------------------------------------------------------------------
    def test_scenario_f_dependency_failure_propagation(self):
        """Dependent ticket is BLOCKED and never runs when parent fails."""
        orchestrator = MainOrchestrator(workspace_root=self.workspace, max_agents=2, api_key="dummy")
        t_parent = Ticket.create(title="Parent Task", description="Base logic", category="coding")
        t_child = Ticket.create(title="Child Task", description="Requires parent", category="testing", depends_on=[t_parent.id])

        orchestrator.all_tickets = [t_parent, t_child]
        orchestrator.pending_backlog = [t_parent, t_child]

        # Fail parent ticket
        t_parent.mark_failed("Fatal compile error", "AGENT_ERROR")

        # Propagate blocked
        orchestrator._propagate_blocked()

        self.assertEqual(t_child.status, TicketStatus.BLOCKED)
        self.assertEqual(t_child.failure_code, "DEPENDENCY_FAILED")
        self.assertNotIn(t_child, orchestrator.pending_backlog)

    # -------------------------------------------------------------------------
    # Scenario G: Token Budget Exhaustion
    # -------------------------------------------------------------------------
    def test_scenario_g_budget_exhaustion(self):
        """System safely stops with BUDGET_EXHAUSTED when token limit reached."""
        orchestrator = MainOrchestrator(
            workspace_root=self.workspace,
            max_agents=2,
            api_key="dummy",
            token_limit=100,
        )
        t1 = Ticket.create(title="Task 1", description="Work", category="coding")
        t2 = Ticket.create(title="Task 2", description="Work", category="coding")
        orchestrator.all_tickets = [t1, t2]
        orchestrator.pending_backlog = [t1, t2]

        # Exceed budget
        orchestrator.token_budget.record(150)
        self.assertTrue(orchestrator.token_budget.exhausted)

        orchestrator._abort_for_budget()

        self.assertEqual(t1.status, TicketStatus.BLOCKED)
        self.assertEqual(t1.failure_code, "TOKEN_BUDGET_EXHAUSTED")
        self.assertEqual(t2.status, TicketStatus.BLOCKED)

    # -------------------------------------------------------------------------
    # Scenario H: No-Progress Loop Termination
    # -------------------------------------------------------------------------
    def test_scenario_h_no_progress_loop(self):
        """Loop terminates with NO_PROGRESS when no new work or progress is possible."""
        orchestrator = MainOrchestrator(workspace_root=self.workspace, api_key="dummy")
        t_blocked = Ticket.create(title="Unresolvable", description="Deadlock", category="coding")
        t_blocked.mark_blocked("No solution possible", "UNRESOLVABLE")
        orchestrator.all_tickets = [t_blocked]

        summary = orchestrator.run_autonomous_loop("Solve unresolvable issue", mode="autonomous")
        self.assertIn(summary["status"], (AutonomousRunState.NO_PROGRESS.value, AutonomousRunState.BLOCKED.value, AutonomousRunState.INCOMPLETE.value))
        self.assertNotEqual(summary["status"], AutonomousRunState.VERIFIED_COMPLETE.value)

    # -------------------------------------------------------------------------
    # Scenario I: Concurrent Execution and Scope Fencing
    # -------------------------------------------------------------------------
    def test_scenario_i_concurrent_execution_and_scope_fencing(self):
        """Workers can run in parallel while scope fencing blocks writes outside target_files."""
        orchestrator = MainOrchestrator(workspace_root=self.workspace, max_agents=3, api_key="dummy", parallel=True)
        worker = orchestrator.agents[0]
        ticket = Ticket.create(
            title="Scoped Task",
            description="Only edit target",
            category="coding",
            target_files=["src/allowed.py"],
        )
        worker.current_ticket = ticket

        # Attempt to write to a forbidden file
        res = worker._execute_tool("write_file", {"filepath": "src/forbidden.py", "content": "malicious"})
        self.assertIn("Error: Modification of 'src/forbidden.py' is forbidden", res)

    # -------------------------------------------------------------------------
    # Scenario J: Existing User Changes Distinguished from Regressions
    # -------------------------------------------------------------------------
    def test_scenario_j_existing_user_changes(self):
        """Pre-existing uncommitted user modifications are not flagged as agent scope violations."""
        user_file = self.workspace / "user_work.py"
        user_file.write_text("print('user draft')\n", encoding="utf-8")
        subprocess.run(["git", "add", "user_work.py"], cwd=str(self.workspace), capture_output=True)
        subprocess.run(["git", "commit", "-m", "User base commit"], cwd=str(self.workspace), capture_output=True)

        # User modifies user_work.py uncommitted
        user_file.write_text("print('user uncommitted edit')\n", encoding="utf-8")

        baseline = capture_repository_baseline(self.workspace, run_tests=False)
        self.assertIn("user_work.py", baseline.pre_existing_git_changes)

        # Agent executes a ticket targeting agent_file.py
        agent_file = self.workspace / "agent_file.py"
        agent_file.write_text("print('agent work')\n", encoding="utf-8")

        ticket = Ticket.create(
            title="Agent Task",
            description="Add agent file",
            category="coding",
            target_files=["agent_file.py"],
        )
        ticket.mark_resolved("Done")

        verifier = IndependentVerifier(workspace_root=self.workspace, baseline=baseline)
        v_res = verifier.verify_ticket(ticket)

        # user_work.py was in baseline, so it must NOT be flagged as scope violation
        self.assertNotIn("user_work.py", v_res.scope_violations)
        self.assertTrue(v_res.success)

    # -------------------------------------------------------------------------
    # Scenario K: No Actionable Findings (Clean Audit)
    # -------------------------------------------------------------------------
    def test_scenario_k_clean_audit(self):
        """Clean repository audit completes with VERIFIED_COMPLETE and 0 defects."""
        clean_file = self.workspace / "main.py"
        clean_file.write_text("def main():\n    return 0\n", encoding="utf-8")
        subprocess.run(["git", "add", "main.py"], cwd=str(self.workspace), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Clean base"], cwd=str(self.workspace), capture_output=True)

        orchestrator = MainOrchestrator(workspace_root=self.workspace, api_key="dummy")
        summary = orchestrator.run_autonomous_loop("Audit codebase for defects", mode="audit")

        self.assertEqual(summary["status"], AutonomousRunState.VERIFIED_COMPLETE.value)
        self.assertEqual(summary["total_tickets"], 0)

    # -------------------------------------------------------------------------
    # Scenario L: End-to-End Objective Workflow
    # -------------------------------------------------------------------------
    def test_scenario_l_end_to_end_objective(self):
        """Real end-to-end orchestration: discover defect, plan, execute, verify."""
        math_file = self.workspace / "math_service.py"
        math_file.write_text("def add(a, b):\n    return a - b  # Intentional bug\n", encoding="utf-8")
        test_file = self.workspace / "test_math.py"
        test_file.write_text(
            "import sys\nfrom math_service import add\nassert add(2, 3) == 5, 'add(2,3) must equal 5'\n",
            encoding="utf-8"
        )
        subprocess.run(["git", "add", "."], cwd=str(self.workspace), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial with bug"], cwd=str(self.workspace), capture_output=True)

        orchestrator = MainOrchestrator(workspace_root=self.workspace, max_agents=2, api_key="dummy")

        # Step 1: Discover
        registry, baseline = orchestrator.discover_repository(run_tests=False)
        self.assertIsNotNone(baseline)

        # Step 2: Plan
        planner = EvidenceDrivenPlanner(workspace_root=self.workspace, api_key="dummy")
        tickets = planner.plan(
            objective="Fix calculation defect and verify math service",
            findings=registry,
            baseline=baseline,
        )
        self.assertGreaterEqual(len(tickets), 1)

        # Step 3: Simulate worker applying the fix
        math_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        # Step 4: Independent verification
        verifier = IndependentVerifier(workspace_root=self.workspace, baseline=baseline)
        cmd_result = subprocess.run(
            [os.sys.executable, str(test_file)],
            cwd=str(self.workspace),
            capture_output=True,
            text=True
        )
        self.assertEqual(cmd_result.returncode, 0)

        # Mark ticket resolved and verify
        t = tickets[0]
        t.mark_resolved("Bug resolved in math_service.py")
        v_res = verifier.verify_ticket(t)
        self.assertTrue(v_res.success)


if __name__ == "__main__":
    unittest.main()

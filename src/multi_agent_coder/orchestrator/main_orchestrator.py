"""
Main Orchestrator for Multi-Agent Ticket System.
Identifies problems from user objectives, generates discrete tickets,
and dispatches them to agents with a strict per-agent queue limit of 3.
Agents process tasks synchronously one by one.
"""

import concurrent.futures
import json
import logging
import os
import re
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Callable, Any
from dotenv import find_dotenv, load_dotenv
from google import genai
from google.genai import types

from .ticket import Ticket, TicketStatus, TicketDAG
from .agent_worker import AgentWorker, QueueFullError
from .run_logger import SwarmRunLogger
from .planner import EvidenceDrivenPlanner
from .verifier import IndependentVerifier, VerificationResult
from ..discovery.findings import (
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingRegistry,
    FindingSeverity,
)
from ..discovery.baseline import RepositoryBaseline
from ..discovery.scanner import RepositoryScanner
from ..common.config import SwarmConfig, resolve_workspace, parse_token_limit
from ..common.token_budget import TokenBudget, TokenBudgetExceeded, usage_from_response
from ..common.logging_config import setup_logging

load_dotenv(find_dotenv())
logger = setup_logging(__name__)

_UNSET: Any = object()


class AutonomousRunState(str, Enum):
    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    NO_PROGRESS = "NO_PROGRESS"
    CANCELLED = "CANCELLED"
    PLANNED = "PLANNED"
    AUDIT_COMPLETE = "AUDIT_COMPLETE"


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
        parallel: bool | None = None,
        auto_qa: bool | None = None,
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
        self.parallel: bool = self.config.parallel if parallel is None else bool(parallel)
        self.auto_qa: bool = self.config.auto_qa if auto_qa is None else bool(auto_qa)
        self._lock = threading.Lock()
        
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
        logger.info("Swarm run %s | workspace=%s | model=%s | parallel=%s | auto_qa=%s | token_limit=%s",
                    self.run_id, self.workspace_root, self.model, self.parallel, self.auto_qa,
                    "unlimited" if self.token_limit is None else self.token_limit)

        # Autonomous discovery, baseline snapshot, and independent verification
        self.findings_registry: FindingRegistry = FindingRegistry()
        self.baseline: RepositoryBaseline | None = None
        self.verifier: IndependentVerifier | None = None

        raw_rounds = os.getenv("MAX_PLANNING_ROUNDS", "3").strip()
        self.max_planning_rounds: int = max(1, int(raw_rounds)) if raw_rounds.isdigit() else 3
        raw_tot = os.getenv("MAX_TOTAL_TICKETS", "20").strip()
        self.max_total_tickets: int = max(1, int(raw_tot)) if raw_tot.isdigit() else 20
        raw_secs = os.getenv("MAX_WALL_CLOCK_SECONDS", "600").strip()
        self.max_wall_clock_seconds: float = float(raw_secs) if raw_secs.replace(".", "").isdigit() else 600.0
        self.final_status: str = AutonomousRunState.INCOMPLETE.value

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

    @property
    def tester_agent(self) -> AgentWorker | None:
        """The dedicated Nth agent responsible for test execution and QA verification."""
        for a in reversed(self.agents):
            if getattr(a, "is_tester", False):
                return a
        return None

    @property
    def worker_agents(self) -> list[AgentWorker]:
        """All agents responsible for analysis, implementation, refactoring, and docs."""
        workers = [a for a in self.agents if not getattr(a, "is_tester", False)]
        return workers if workers else self.agents

    def _init_agents(self) -> None:
        """
        Start all worker agents up to max_agents.
        N-1 agents are Worker Agents (analysis, coding, refactor, docs).
        The Nth agent (Agent-N) is always the dedicated QA & Test Verification Engineer.
        """
        worker_roles = [
            ("Code Navigator & System Analyst", "analysis"),
            ("Core Implementation & Coding Engineer", "coding"),
            ("Refactoring & Performance Engineer", "refactor"),
            ("Architecture & Documentation Specialist", "docs"),
        ]
        qa_role = ("Lead QA & Test Verification Engineer", "testing")

        logger.info("Main Orchestrator launching %d agents (queue limit: %d each, parallel: %s)...",
                    self.max_agents, self.queue_limit_per_agent, self.parallel)

        names = self.config.agent_names
        for i in range(self.max_agents):
            agent_id = names[i] if i < len(names) else f"Agent-{i+1}"
            is_tester = (i == self.max_agents - 1 and self.max_agents >= 2)
            if is_tester:
                role_name, specialty = qa_role
            else:
                role_name, specialty = worker_roles[i % len(worker_roles)]

            worker = AgentWorker(
                agent_id=agent_id,
                role=role_name,
                specialty=specialty,
                queue_limit=self.queue_limit_per_agent,
                model=self.model,
                api_key=self.api_key,
                workspace_root=self.workspace_root,
                token_budget=self.token_budget,
                run_logger=self.run_logger,
                is_tester=is_tester,
            )
            self.agents.append(worker)
            if is_tester:
                logger.info("Designated [%s] as the dedicated QA & Test Verification Agent (Nth agent).", agent_id)
            else:
                logger.info("Registered worker [%s] as %s (%s).", agent_id, role_name, specialty)

    def _note_objective(self, objective: str) -> None:
        if objective and not getattr(self.run_logger, "objective", ""):
            self.run_logger.objective = objective

    def discover_repository(self, run_tests: bool = True) -> tuple[FindingRegistry, RepositoryBaseline]:
        """Run proactive repository discovery across the target workspace."""
        logger.info("Executing proactive repository discovery on %s...", self.workspace_root)
        scanner = RepositoryScanner(self.workspace_root)
        should_run_tests = run_tests and not (self.api_key and self.api_key.startswith("dummy"))
        self.findings_registry, self.baseline = scanner.scan(
            objective=getattr(self.run_logger, "objective", ""),
            run_baseline_tests=should_run_tests,
        )
        self.verifier = IndependentVerifier(self.workspace_root, self.baseline)
        return self.findings_registry, self.baseline

    def identify_problems_and_create_tickets(self, objective: str) -> list[Ticket]:
        """
        Main orchestrator analyzes the high-level objective and discovery findings,
        generates discrete tickets with evidence, and schedules them.
        """
        logger.info("Main Orchestrator planning tickets for objective: %s", objective)
        self._note_objective(objective)

        # Ensure discovery has run
        if self.baseline is None:
            self.discover_repository(run_tests=True)

        planner = EvidenceDrivenPlanner(
            workspace_root=self.workspace_root,
            model=self.model,
            api_key=self.api_key,
            client=self._client,
            token_budget=self.token_budget,
        )
        tickets = planner.plan(
            objective=objective,
            findings=self.findings_registry,
            baseline=self.baseline,
            previous_tickets=self.all_tickets,
        )

        for t in tickets:
            self.all_tickets.append(t)
            self.pending_backlog.append(t)
            self.run_logger.ticket_created(t)

        logger.info("Main Orchestrator identified and raised %d evidence-backed tickets.", len(tickets))
        return tickets

    def run_autonomous_loop(
        self,
        objective: str,
        mode: str = "autonomous",
        on_step_callback: Callable[[Ticket], None] | None = None,
    ) -> dict[str, Any]:
        """
        Closed-loop autonomous engineering control loop:
        1. Proactive Discovery (baseline + static scan)
        2. Evidence-Driven Planning
        3. Execution (bounded concurrency / sequential)
        4. Independent Verification (scope, syntax, tests, diff)
        5. Assessment & Feedback (extract worker findings, generate follow-up tickets)
        6. Iterate until verified complete, budget exhausted, or stopped.
        """
        self._note_objective(objective)
        start_time = time.time()
        logger.info("=== Starting Autonomous Engineering Loop (Mode: %s) ===", mode.upper())
        logger.info("Objective: %s", objective)

        # Step 1: Discovery
        self.discover_repository(run_tests=(mode != "plan"))

        if mode == "audit":
            confirmed_defects = [
                f for f in self.findings_registry.list_all()
                if f.confidence == FindingConfidence.CONFIRMED or f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
            ]
            self.final_status = AutonomousRunState.AUDIT_COMPLETE.value
            summary = self.get_summary()
            summary["audit_complete"] = True
            summary["clean"] = (len(confirmed_defects) == 0)
            summary["confirmed_defects"] = [f.to_dict() for f in confirmed_defects]
            self.run_logger.finalize(summary)
            return summary

        # Step 2: Planning
        if not self.all_tickets:
            self.identify_problems_and_create_tickets(objective)

        if mode == "plan":
            self.final_status = AutonomousRunState.PLANNED.value
            summary = self.get_summary()
            summary["planned"] = True
            self.run_logger.finalize(summary)
            return summary

        # Step 3: Closed-Loop Execution and Verification
        planning_round = 0
        consecutive_no_progress = 0
        verifier = self.verifier or IndependentVerifier(self.workspace_root, self.baseline)

        while planning_round < self.max_planning_rounds:
            planning_round += 1
            logger.info("--- Autonomous Loop Round %d/%d ---", planning_round, self.max_planning_rounds)

            # Check time limit
            if time.time() - start_time > self.max_wall_clock_seconds:
                logger.warning("Wall-clock time budget reached (%.1fs).", self.max_wall_clock_seconds)
                self.final_status = AutonomousRunState.BUDGET_EXHAUSTED.value
                break

            # Check token limit
            if self.token_budget.exhausted:
                self._abort_for_budget()
                self.final_status = AutonomousRunState.BUDGET_EXHAUSTED.value
                break

            # Execute pending work
            unprocessed_before = len([t for t in self.all_tickets if t.status not in (TicketStatus.RESOLVED, TicketStatus.FAILED, TicketStatus.BLOCKED)])
            if unprocessed_before > 0:
                self.process_all_tickets(on_step_callback=on_step_callback)

            # Independent verification of resolved tickets
            failed_verification_count = 0
            for ticket in self.all_tickets:
                if ticket.status == TicketStatus.RESOLVED and not ticket.verified:
                    v_res = verifier.verify_ticket(ticket)
                    if not v_res.success:
                        ticket.status = TicketStatus.FAILED
                        ticket.verified = False
                        ticket.error = f"Independent verification failed: {v_res.summary}"
                        ticket.failure_code = "VERIFICATION_FAILED"
                        failed_verification_count += 1
                    else:
                        ticket.verified = True

            # Extract discoveries from workers
            newly_discovered_count = 0
            for ticket in self.all_tickets:
                for issue in ticket.follow_up_findings:
                    f = Finding.create(
                        title=issue.get("title", "Worker Discovered Issue"),
                        description=issue.get("description", ""),
                        file_path=issue.get("file_path"),
                        evidence=issue.get("evidence", ""),
                        category=FindingCategory.DEFECT,
                        confidence=FindingConfidence.HIGH,
                        severity=FindingSeverity.HIGH,
                    )
                    if self.findings_registry.add(f):
                        newly_discovered_count += 1
                        logger.info("Added worker-discovered finding [%s]: %s", f.id, f.title)

            # Aggregate verification
            agg_res = verifier.verify_aggregate()

            # Check if all completed cleanly
            all_resolved = len(self.all_tickets) > 0 and all(t.status == TicketStatus.RESOLVED for t in self.all_tickets)
            all_verified = len(self.all_tickets) > 0 and all(t.verified for t in self.all_tickets)
            if all_resolved and all_verified and failed_verification_count == 0 and newly_discovered_count == 0 and agg_res.success:
                self.final_status = AutonomousRunState.VERIFIED_COMPLETE.value
                logger.info("Autonomous Loop reached VERIFIED_COMPLETE.")
                break

            # Check max tickets budget
            if len(self.all_tickets) >= self.max_total_tickets:
                logger.warning("Reached maximum ticket limit (%d).", self.max_total_tickets)
                self.final_status = AutonomousRunState.INCOMPLETE.value
                break

            # Generate follow-up tickets for next round
            if planning_round < self.max_planning_rounds:
                resolved_fids = {fid for t in self.all_tickets if t.status == TicketStatus.RESOLVED for fid in t.finding_ids}
                unresolved = [
                    f for f in self.findings_registry.list_all()
                    if f.id not in resolved_fids and (f.confidence == FindingConfidence.CONFIRMED or f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH))
                ]
                if not unresolved and not agg_res.regressions:
                    if all_resolved and all_verified and agg_res.success:
                        self.final_status = AutonomousRunState.VERIFIED_COMPLETE.value
                    else:
                        self.final_status = AutonomousRunState.INCOMPLETE.value
                    break

                planner = EvidenceDrivenPlanner(
                    self.workspace_root,
                    model=self.model,
                    api_key=self.api_key,
                    client=self._client,
                    token_budget=self.token_budget,
                )
                follow_ups = planner.plan_follow_up(
                    objective=objective,
                    unresolved_findings=unresolved,
                    baseline=self.baseline,
                    existing_tickets=self.all_tickets,
                )
                if not follow_ups:
                    consecutive_no_progress += 1
                    if consecutive_no_progress >= 2:
                        logger.info("No further follow-up tickets possible; stopping loop.")
                        self.final_status = AutonomousRunState.NO_PROGRESS.value
                        break
                else:
                    consecutive_no_progress = 0
                    for fu in follow_ups:
                        if len(self.all_tickets) < self.max_total_tickets:
                            self.all_tickets.append(fu)
                            self.pending_backlog.append(fu)
                            self.run_logger.ticket_created(fu)
            else:
                consecutive_no_progress += 1

        # Final state check
        if self.final_status == AutonomousRunState.INCOMPLETE.value:
            if self.token_budget.exhausted:
                self.final_status = AutonomousRunState.BUDGET_EXHAUSTED.value
            elif any(t.status == TicketStatus.BLOCKED for t in self.all_tickets) and not any(t.status in (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED) for t in self.all_tickets):
                self.final_status = AutonomousRunState.BLOCKED.value
            elif any(t.status == TicketStatus.FAILED for t in self.all_tickets):
                self.final_status = AutonomousRunState.FAILED.value
            elif agg_res.success and self.all_tickets and all(t.status == TicketStatus.RESOLVED and t.verified for t in self.all_tickets):
                self.final_status = AutonomousRunState.VERIFIED_COMPLETE.value
            elif not any(t.status in (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED) for t in self.all_tickets):
                self.final_status = AutonomousRunState.NO_PROGRESS.value
            else:
                self.final_status = AutonomousRunState.INCOMPLETE.value

        summary = self.get_summary()
        self.run_logger.finalize(summary)
        return summary

    def _heuristic_problem_decomposition(self, objective: str) -> list[Ticket]:
        """Rule-based breakdown when LLM is unavailable or in offline test mode."""
        lines = [line.strip().lstrip("-*123456789. ") for line in objective.splitlines() if line.strip()]
        if len(lines) > 1:
            tickets = []
            for i, line in enumerate(lines[:5]):
                cat = "analysis" if i == 0 else ("testing" if "test" in line.lower() else "coding")
                tickets.append(Ticket.create(title=line[:50], description=line, category=cat))
            return tickets

        # Standard 3-phase decomposition for single-line objective:
        # Phase 1: Analysis
        t_analysis = Ticket.create(
            title=f"Analyze requirements for: {objective[:40]}",
            description=f"Inspect system architecture, dependencies, and requirements for: {objective}",
            category="analysis",
        )
        # Phase 2: Coding
        t_coding = Ticket.create(
            title=f"Implement changes for: {objective[:40]}",
            description=f"Implement code logic, functions, or fixes needed for: {objective}",
            category="coding",
            depends_on=[t_analysis.id],
        )
        # Phase 3: QA Verification & Testing by the Nth agent
        t_testing = Ticket.create(
            title=f"Validate and test: {objective[:40]}",
            description=f"Write tests, verify syntax, and confirm solution for: {objective}",
            category="testing",
            depends_on=[t_coding.id],
        )
        return [t_analysis, t_coding, t_testing]

    def _create_qa_verification_ticket(self, parent_ticket: Ticket) -> Ticket | None:
        """
        Ensure the Nth agent (Tester) tests and validates code changes made by worker agents.
        If a coding/refactor ticket completes and the run does not already include dedicated testing tickets,
        raise a QA verification ticket assigned to the Tester agent.
        """
        if not self.auto_qa or not self.tester_agent:
            return None

        # Only work tickets that modify code trigger QA validation
        if parent_ticket.category not in ("coding", "refactor"):
            return None

        # If the DAG or ticket set already includes testing/qa tickets, the Nth agent
        # is already tasked with testing in the workflow.
        has_testing_tickets = any(
            t.category in ("testing", "qa") and not t.id.startswith("TICK-QA-")
            for t in self.all_tickets
        )
        if has_testing_tickets:
            return None

        # Check if an existing QA verification ticket was already generated
        for t in self.all_tickets:
            if t.id == f"TICK-QA-{parent_ticket.id}":
                return None
            if parent_ticket.id in t.depends_on and t.category in ("testing", "qa"):
                return None

        qa_ticket = Ticket.create(
            title=f"QA Verification: Test changes for [{parent_ticket.id}] {parent_ticket.title[:35]}",
            description=(
                f"You are the dedicated QA & Test Verification Engineer ({self.tester_agent.agent_id}).\n"
                f"Worker agent {parent_ticket.assigned_agent_id} completed implementation ticket {parent_ticket.id}: '{parent_ticket.title}'.\n\n"
                f"Worker Output Summary:\n{parent_ticket.result or 'No output recorded'}\n\n"
                "YOUR MANDATORY QA VERIFICATION CHECKLIST:\n"
                "1. Inspect changes using `git_status` and `git_diff`.\n"
                "2. Run `check_syntax` on any modified files.\n"
                "3. Execute test suites (`run_command`) such as pytest or node tests.\n"
                "4. Confirm no regressions or broken functionality.\n"
                "5. Output your detailed QA test report adhering to [Agent Status: RESOLVED] and report findings to the Main Orchestrator."
            ),
            category="testing",
            depends_on=[parent_ticket.id],
        )
        qa_ticket.id = f"TICK-QA-{parent_ticket.id}"
        self.all_tickets.append(qa_ticket)
        self.pending_backlog.append(qa_ticket)
        self.run_logger.ticket_created(qa_ticket)
        logger.info("Main Orchestrator created QA verification ticket [%s] for Tester Agent [%s]",
                    qa_ticket.id, self.tester_agent.agent_id)
        return qa_ticket

    def dispatch_ticket(self, ticket: Ticket) -> AgentWorker | None:
        """
        Dispatch a single ticket to the most suitable agent that has queue capacity (< 3).
        Strategy:
        1. If ticket category is testing/qa:
           Strictly dispatch to self.tester_agent (if present).
        2. If ticket category is specific work (coding, analysis, refactor, docs):
           Strictly dispatch to worker agents (Agents 1..N-1).
        3. If ticket category is general or worker queues are full, allow tester agent to take general work.
        4. If no candidate agents have capacity, ticket stays in pending_backlog.
        """
        if ticket.assigned_agent_id:
            for a in self.agents:
                if a.agent_id == ticket.assigned_agent_id:
                    if ticket not in a.queue and a.can_accept_ticket():
                        a.enqueue_ticket(ticket)
                        if ticket in self.pending_backlog:
                            self.pending_backlog.remove(ticket)
                    return a

        # 1. Testing tickets route strictly to tester agent
        if ticket.category in ("testing", "qa") and self.tester_agent:
            if self.tester_agent.can_accept_ticket():
                self.tester_agent.enqueue_ticket(ticket)
                if ticket in self.pending_backlog:
                    self.pending_backlog.remove(ticket)
                return self.tester_agent
            logger.info("Tester agent [%s] queue is full (limit %d). Ticket %s held in backlog.",
                        self.tester_agent.agent_id, self.queue_limit_per_agent, ticket.id)
            return None

        # 2. Specific work tickets route strictly to worker agents
        available_workers = [a for a in self.worker_agents if a.can_accept_ticket()]
        if available_workers:
            # To maximize concurrent parallelism, prefer idle worker agents first
            idle_matching = [a for a in available_workers if a.specialty == ticket.category and a.queue_size == 0]
            if idle_matching:
                chosen_agent = idle_matching[0]
            else:
                other_idle = [a for a in available_workers if a.queue_size == 0]
                if other_idle:
                    chosen_agent = other_idle[0]
                else:
                    specialty_match = [a for a in available_workers if a.specialty == ticket.category]
                    if specialty_match:
                        chosen_agent = min(specialty_match, key=lambda a: a.queue_size)
                    else:
                        chosen_agent = min(available_workers, key=lambda a: a.queue_size)

            chosen_agent.enqueue_ticket(ticket)
            if ticket in self.pending_backlog:
                self.pending_backlog.remove(ticket)
            return chosen_agent

        # 3. If ticket is general and all workers are full, tester agent can take general capacity
        if ticket.category == "general" and self.tester_agent and self.tester_agent.can_accept_ticket():
            self.tester_agent.enqueue_ticket(ticket)
            if ticket in self.pending_backlog:
                self.pending_backlog.remove(ticket)
            return self.tester_agent

        logger.info("All eligible agent queues are full (limit %d). Ticket %s held in backlog.",
                    self.queue_limit_per_agent, ticket.id)
        return None

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
        """Block backlog tickets whose dependency permanently failed, was blocked, or does not exist."""
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

    def _handle_ticket_completion(self, completed: Ticket, resolved_tickets: list[Ticket]) -> bool:
        """
        Handle post-ticket completion lifecycle:
        - If resolved, record to resolved_tickets and trigger QA if auto_qa is True.
        - If failed and retries remain, re-queue with diagnostic guidance instead of cascading blocks.
        - If failed and retries exhausted, record to resolved_tickets as failed.
        Returns True if ticket concluded its lifecycle (resolved or exhausted).
        """
        if completed.status == TicketStatus.RESOLVED:
            resolved_tickets.append(completed)
            if self.auto_qa:
                self._create_qa_verification_ticket(completed)
            return True

        if completed.status == TicketStatus.FAILED:
            can_retry = (
                completed.retries < completed.max_retries
                and completed.failure_code not in ("TOKEN_BUDGET_EXHAUSTED", "CANCELLED")
                and not self.token_budget.exhausted
            )
            if can_retry:
                completed.retries += 1
                logger.warning(
                    "Ticket [%s] failed on attempt %d/%d (%s: %s). Re-queueing with diagnostic repair context.",
                    completed.id, completed.retries, completed.max_retries, completed.failure_code, completed.error
                )
                diagnostic = (
                    f"\n\n[PREVIOUS ATTEMPT {completed.retries} FAILED]\n"
                    f"Failure Code: {completed.failure_code}\n"
                    f"Error Details: {completed.error or 'Failed without output'}\n"
                    f"Remediation Guidance: Diagnose the error above. Make focused, surgical changes with "
                    f"replace_file_content, verify syntax with check_syntax, and submit a complete [Agent Status: RESOLVED] report."
                )
                completed.description += diagnostic
                completed.status = TicketStatus.READY
                completed.assigned_agent_id = None
                completed.error = None
                completed.failure_code = None
                if completed not in self.pending_backlog:
                    self.pending_backlog.append(completed)
                return False
            else:
                resolved_tickets.append(completed)
                return True

        return False

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
                        self._handle_ticket_completion(completed, resolved_tickets)
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

    def process_all_tickets_parallel(
        self,
        on_step_callback: Callable[[Ticket], None] | None = None
    ) -> list[Ticket]:
        """
        Executes tickets concurrently across agents using ThreadPoolExecutor.
        Independent tickets run in parallel on separate worker agents.
        Dependencies are respected via TicketDAG / _deps_satisfied.
        Freed slots and newly unlocked tickets are dispatched dynamically as agents finish.
        The Nth agent performs independent QA validation of completed changes.
        """
        resolved_tickets: list[Ticket] = []
        callback_lock = threading.Lock()

        def safe_callback(ticket: Ticket) -> None:
            if on_step_callback:
                with callback_lock:
                    on_step_callback(ticket)

        # Initial dispatch into available queues
        with self._lock:
            self.dispatch_all_pending()

        active_futures: dict[concurrent.futures.Future, AgentWorker] = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_agents) as executor:
            while True:
                # 1. Budget check
                if self.token_budget.exhausted:
                    with self._lock:
                        self._abort_for_budget()
                    break

                # 2. Launch tickets on all idle agents that have queued tickets
                with self._lock:
                    busy_agents = set(active_futures.values())
                    for agent in self.agents:
                        if agent not in busy_agents and agent.queue_size > 0:
                            future = executor.submit(agent.process_next_ticket, safe_callback)
                            active_futures[future] = agent

                # 3. If no agent is working, check if we're done or deadlocked
                if not active_futures:
                    with self._lock:
                        has_queued = any(a.queue_size > 0 for a in self.agents)
                        if not has_queued and not self.pending_backlog:
                            break  # All tickets processed
                        if self.pending_backlog and not has_queued:
                            # Deadlock guard: no running tasks, no queued tickets, but backlog remains
                            for t in list(self.pending_backlog):
                                self._block(t, "Dependencies can never be satisfied", "DEPENDENCY_FAILED")
                            break

                # 4. Wait for at least one future to finish
                done, _ = concurrent.futures.wait(
                    list(active_futures.keys()),
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    agent = active_futures.pop(future, None)
                    try:
                        completed = future.result()
                    except Exception as exc:
                        logger.exception("Agent [%s] failed with unexpected exception: %s",
                                         agent.agent_id if agent else "unknown", exc)
                        completed = None

                    if completed:
                        with self._lock:
                            self._handle_ticket_completion(completed, resolved_tickets)

                # 5. Dispatch newly unlocked backlog tickets
                with self._lock:
                    self.dispatch_all_pending()

        self.run_logger.finalize(self.get_summary())
        return resolved_tickets

    def process_all_tickets(
        self,
        parallel: bool | None = None,
        on_step_callback: Callable[[Ticket], None] | None = None
    ) -> list[Ticket]:
        """
        Execute all tickets across the agent fleet.
        Runs in parallel by default (or if configured in .env / arguments),
        or falls back to synchronous execution when parallel is False.
        """
        run_parallel = self.parallel if parallel is None else bool(parallel)
        if run_parallel and self.max_agents > 1:
            return self.process_all_tickets_parallel(on_step_callback=on_step_callback)
        return self.process_all_tickets_synchronously(on_step_callback=on_step_callback)

    def load_manifest(self, manifest_data: list[dict[str, Any]] | dict[str, Any]) -> list[Ticket]:
        """
        Load an explicit DAG of tickets from a manifest (e.g. prepared by Antigravity or JSON file).
        Validates dependencies using Kahn's algorithm before queueing.
        """
        if isinstance(manifest_data, dict):
            obj = manifest_data.get("objective")
            if obj:
                self._note_objective(str(obj))
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
            "status": self.final_status,
            "run_id": self.run_id,
            "model": self.model,
            "workspace_root": str(self.workspace_root),
            "token_usage": self.token_budget.snapshot(),
            "log_dir": str(self.run_logger.run_dir),
            "findings_count": len(self.findings_registry),
            "findings": self.findings_registry.to_dict_list(),
            "baseline": self.baseline.to_dict() if self.baseline else None,
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
                    "actions": t.actions,
                    "actual_files_modified": t.actual_files_modified,
                    "failure_code": t.failure_code,
                    "result": t.result,
                    "error": t.error,
                }
                for t in self.all_tickets
            ],
        }


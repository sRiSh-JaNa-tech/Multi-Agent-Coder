"""
Integration Test Suite for Production Upgrade: 10 Phases Validation.
Verifies state machine, security capabilities, worktrees, tool registry,
structured protocols, verifier contracts, and persistent SQLite store.
"""

import json
from pathlib import Path
import tempfile
import pytest

from multi_agent_coder.orchestrator.ticket import Ticket, TicketStatus, TicketDAG
from multi_agent_coder.orchestrator.planner import EvidenceDrivenPlanner, InvalidPlanError
from multi_agent_coder.security.permissions import AgentCapability, SecurityContext
from multi_agent_coder.orchestrator.worktree_manager import WorktreeManager
from multi_agent_coder.tools.registry import ToolRegistry
from multi_agent_coder.tools.search import execute_search_code
from multi_agent_coder.orchestrator.protocols import AgentReport, FindingReport
from multi_agent_coder.store.run_store import RunStateStore
from multi_agent_coder.orchestrator.controller import UnifiedRunController


def test_phase1_ticket_state_machine_and_cycle_error():
    # Disentangled status
    assert TicketStatus.QUEUED != TicketStatus.IN_PROGRESS
    assert TicketStatus.RESOLVED == "RESOLVED"
    
    t1 = Ticket.create(title="Task 1", description="Desc 1", category="coding")
    t2 = Ticket.create(title="Task 2", description="Desc 2", category="coding", depends_on=[t1.id])
    t1.depends_on = [t2.id]  # Cycle!

    planner = EvidenceDrivenPlanner(workspace_root=".")
    from multi_agent_coder.discovery.baseline import RepositoryBaseline
    baseline = RepositoryBaseline(workspace_root=Path("."))
    
    with pytest.raises(InvalidPlanError):
        planner._validate_and_repair([t1, t2], baseline)


def test_phase2_security_context_containment(tmp_path):
    ctx = SecurityContext.for_worker(workspace_root=tmp_path)
    assert ctx.has_capability(AgentCapability.READ_ONLY)
    assert ctx.has_capability(AgentCapability.WORKSPACE_WRITE)
    assert not ctx.has_capability(AgentCapability.ADMIN)

    # Path inside workspace
    inside_file = tmp_path / "src" / "app.py"
    assert ctx.is_path_within_workspace(inside_file)
    ctx.assert_path_within_workspace(inside_file)

    # Path outside workspace
    outside_file = tmp_path.parent / "secret.env"
    assert not ctx.is_path_within_workspace(outside_file)
    with pytest.raises(PermissionError):
        ctx.assert_path_within_workspace(outside_file)

    # Destructive command check
    with pytest.raises(PermissionError):
        ctx.assert_destructive_command("rm -rf /")


def test_phase3_worktree_manager(tmp_path):
    mgr = WorktreeManager(workspace_root=tmp_path)
    # If not a git repo, gracefully returns workspace root
    wt_path = mgr.setup_worktree_for_ticket("TICK-001")
    assert wt_path == tmp_path.resolve()
    diff = mgr.get_worktree_diff("TICK-001")
    assert diff == ""


def test_phase4_tool_registry():
    registry = ToolRegistry()
    registry.register(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {"msg": {"type": "string"}}},
        handler=lambda msg: f"Echo: {msg}",
        required_capability=AgentCapability.READ_ONLY,
    )

    ctx = SecurityContext(capabilities=[AgentCapability.READ_ONLY], workspace_root=".")
    schemas = registry.get_schemas(security_context=ctx)
    assert len(schemas) == 1
    assert schemas[0]["name"] == "test_tool"

    result = registry.execute("test_tool", {"msg": "hello"}, security_context=ctx)
    assert result == "Echo: hello"


def test_phase4_search_code_resilient_fallback(tmp_path):
    # Test file
    test_file = tmp_path / "hello.py"
    test_file.write_text("def find_me():\n    return 42\n", encoding="utf-8")

    # Call execute_search_code with vector_store=None, embedder=None
    result = execute_search_code(
        vector_store=None,
        embedder=None,
        tool_input={"query": "find_me"},
        workspace_root=tmp_path,
    )
    assert "find_me" in result
    assert "hello.py" in result


def test_phase5_structured_agent_report():
    report_text = """
    I have finished the assigned task.
    **Files Changed**: src/module.py, tests/test_module.py
    **Resolution Summary**: Successfully refactored caching logic and verified syntax.
    [Agent Status: RESOLVED]
    """
    report = AgentReport.from_text(report_text)
    assert report.status == "RESOLVED"
    assert report.verification_passed is True
    assert "src/module.py" in report.files_modified
    assert "tests/test_module.py" in report.files_modified
    assert "refactored caching" in report.summary


def test_phase8_sqlite_state_store(tmp_path):
    db_file = tmp_path / "test_store.db"
    store = RunStateStore(db_path=db_file)

    run_id = "test-run-101"
    store.record_run_start(run_id=run_id, objective="Test Objective", workspace_root=str(tmp_path), max_agents=8)

    ticket = Ticket.create(title="Ticket A", description="Desc A", category="coding")
    store.save_ticket_checkpoint(run_id=run_id, ticket=ticket)

    run_data = store.get_run(run_id)
    assert run_data is not None
    assert run_data["objective"] == "Test Objective"
    assert run_data["status"] == "RUNNING"

    tickets = store.get_run_tickets(run_id)
    assert len(tickets) == 1
    assert tickets[0]["title"] == "Ticket A"

    store.record_run_finish(run_id=run_id, status="COMPLETED", summary={"resolved": 1})
    run_data = store.get_run(run_id)
    assert run_data["status"] == "COMPLETED"


def test_phase9_unified_run_controller_dag_execution(tmp_path):
    db_file = tmp_path / "controller_store.db"
    controller = UnifiedRunController(
        workspace_root=tmp_path,
        max_agents=8,
        parallel=True,
        auto_qa=False,
        db_path=db_file,
    )

    tickets = [
        {
            "id": "TICK-MOCK-1",
            "title": "Mock Task 1",
            "description": "Mock description",
            "category": "analysis",
            "depends_on": [],
        }
    ]

    summary = controller.execute_dag(tickets=tickets, objective="Test Controller DAG")
    assert summary["total_tickets"] == 1
    assert controller.store.get_run(controller.run_id) is not None


def test_defect1_optional_security_context_backward_compatibility(tmp_path):
    from multi_agent_coder.tools.coding import execute_create_file, execute_write_file, execute_replace_file_content

    # Calling tool without security_context succeeds cleanly
    res1 = execute_create_file({"filepath": "test1.py", "content": "x = 1\n"}, workspace_root=tmp_path)
    assert "Successfully created" in res1
    assert (tmp_path / "test1.py").exists()

    res2 = execute_replace_file_content(
        {"filepath": "test1.py", "target_content": "x = 1", "replacement_content": "x = 2"},
        workspace_root=tmp_path,
    )
    assert "Successfully updated" in res2

    # Calling tool with security_context also succeeds
    ctx = SecurityContext.for_worker(tmp_path)
    res3 = execute_write_file({"filepath": "test1.py", "content": "x = 3\n"}, workspace_root=tmp_path, security_context=ctx)
    assert "Successfully updated" in res3


def test_defect2_dynamic_iteration_budget_scaling():
    from multi_agent_coder.orchestrator.agent_worker import _calculate_max_iterations

    t_simple = Ticket.create(title="Simple doc", description="doc", category="docs")
    assert _calculate_max_iterations(t_simple) == 20

    t_coding = Ticket.create(title="Multi-file coding", description="code", category="coding", target_files=["a.py", "b.py"])
    assert _calculate_max_iterations(t_coding) >= 40

    t_qa = Ticket.create(title="QA tests", description="test", category="testing")
    assert _calculate_max_iterations(t_qa) >= 30


def test_defect3_bounded_retry_repair_loop_prevents_cascading_block(tmp_path):
    from multi_agent_coder.orchestrator.main_orchestrator import MainOrchestrator

    orch = MainOrchestrator(workspace_root=tmp_path, max_agents=2, parallel=False)
    t_parent = Ticket.create(title="Parent Task", description="Initial description", category="coding")
    t_parent.id = "TICK-PARENT"
    t_parent.max_retries = 2
    t_child = Ticket.create(title="Child Task", description="Child description", category="coding", depends_on=["TICK-PARENT"])
    t_child.id = "TICK-CHILD"

    orch.all_tickets = [t_parent, t_child]
    orch.pending_backlog = [t_child]

    # Simulate parent failure on attempt 1
    t_parent.status = TicketStatus.FAILED
    t_parent.failure_code = "ITERATION_LIMIT"
    t_parent.error = "Reached iteration limit"

    resolved_list = []
    # Trigger completion lifecycle
    lifecycle_concluded = orch._handle_ticket_completion(t_parent, resolved_list)
    assert not lifecycle_concluded  # Not concluded because it is re-queued for retry
    assert t_parent.retries == 1
    assert t_parent.status == TicketStatus.READY
    assert "PREVIOUS ATTEMPT 1 FAILED" in t_parent.description
    assert t_parent in orch.pending_backlog

    # Check that dependent child is NOT blocked yet!
    orch._propagate_blocked()
    assert t_child.status != TicketStatus.BLOCKED
    assert t_child in orch.pending_backlog


def test_defect4_anti_collapse_and_syntax_safeguards(tmp_path):
    from multi_agent_coder.tools.coding import execute_create_file, execute_write_file

    # 1. Unescapes literal raw '\n' strings properly
    raw_escaped = "def hello():\\n    return 42\\n"
    res1 = execute_create_file({"filepath": "unescape_test.py", "content": raw_escaped}, workspace_root=tmp_path)
    assert "Successfully created" in res1
    file_content = (tmp_path / "unescape_test.py").read_text(encoding="utf-8")
    assert "\n" in file_content
    assert "\\n" not in file_content

    # 2. Syntax gate blocks invalid python before writing
    bad_syntax = "def broken(:\n    pass\n"
    res2 = execute_create_file({"filepath": "syntax_err.py", "content": bad_syntax}, workspace_root=tmp_path)
    assert "Rejected" in res2
    assert "SyntaxError" in res2
    assert not (tmp_path / "syntax_err.py").exists()

    # 3. Anti-collapse blocks replacing large files with <= 2 lines
    large_content = "\n".join([f"line_{i} = {i}" for i in range(50)])
    (tmp_path / "large_file.py").write_text(large_content, encoding="utf-8")

    res3 = execute_write_file({"filepath": "large_file.py", "content": "# collapsed\nx = 1"}, workspace_root=tmp_path)
    assert "Rejected full-file overwrite" in res3


def test_defect5_semantic_search_resilient_fallback_to_grep(tmp_path):
    # Ensure workspace file is located even when embedder/vector store is None
    sample_code = tmp_path / "service.py"
    sample_code.write_text("class PaymentProcessor:\n    def charge(self):\n        pass\n", encoding="utf-8")

    res = execute_search_code(
        vector_store=None,
        embedder=None,
        tool_input={"query": "PaymentProcessor"},
        workspace_root=tmp_path,
    )
    assert "PaymentProcessor" in res
    assert "service.py" in res


def test_logging_filehandler_and_run_log_retrieval(tmp_path):
    from multi_agent_coder.common.logging_config import setup_logging
    from multi_agent_coder.orchestrator.run_logger import SwarmRunLogger, read_run_log
    from multi_agent_coder.orchestrator.main_orchestrator import MainOrchestrator

    # 1. Test setup_logging writes to specified log_file
    custom_log = tmp_path / "custom.log"
    test_logger = setup_logging("test_mod", log_file=custom_log)
    test_logger.info("Test log line 12345")
    # Flush handlers
    for h in test_logger.handlers:
        h.flush()
    assert custom_log.exists()
    assert "Test log line 12345" in custom_log.read_text(encoding="utf-8")

    # 2. Test SwarmRunLogger writes run.log, events.jsonl, and action outputs
    run_log_dir = tmp_path / "swarm_runs"
    rl = SwarmRunLogger(
        log_dir=run_log_dir,
        objective="Verify Swarm Logging",
        workspace_root=tmp_path,
        model="gemini-2.5-flash-lite",
    )
    t = Ticket.create(title="Log Ticket", description="Desc", category="coding")
    rl.ticket_created(t)
    rl.ticket_assigned(t, agent_id="Agent-1", queue_depth=1)
    rl.ticket_started(t, agent_id="Agent-1")
    rl.tool_call("Agent-1", t.id, "replace_file_content", "app.py")
    rl.action_completed("Agent-1", t.id, "replace_file_content", "app.py", status="success", output="Successfully patched line 10")
    rl.ticket_completed(t, agent_id="Agent-1")
    rl.finalize({"total_tickets": 1, "resolved": 1, "failed": 0, "blocked": 0})

    assert rl.run_log_path.exists()
    run_log_content = rl.run_log_path.read_text(encoding="utf-8")
    assert "[RUN_STARTED]" in run_log_content
    assert "Verify Swarm Logging" in run_log_content
    assert "[TOOL_CALL]" in run_log_content
    assert "[ACTION]" in run_log_content
    assert "Successfully patched line 10" in run_log_content
    assert "[RUN_FINISHED]" in run_log_content

    # 3. Test read_run_log returns run_log text and path
    run_info = read_run_log(run_log_dir, run_id=rl.run_id)
    assert run_info["run_log_path"] == str(rl.run_log_path)
    assert "[RUN_STARTED]" in run_info["run_log"]
    assert run_info["finished"] is True

    # 4. Test load_manifest notes objective in run_logger
    orch = MainOrchestrator(workspace_root=tmp_path, max_agents=2, auto_qa=False)
    manifest = {
        "objective": "Manifest Specific Objective",
        "tickets": [{"title": "T1", "description": "D1", "category": "coding"}],
    }
    orch.load_manifest(manifest)
    assert orch.run_logger.objective == "Manifest Specific Objective"


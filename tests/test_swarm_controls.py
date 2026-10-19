"""
Unit tests for swarm controls:
- .env configuration parsing (MODEL_NAME, TOKEN_USAGE_LIMIT, TARGET_WORKSPACE, AGENT_NAMES)
- TokenBudget logic (unlimited vs capped, exhaustion checks)
- In-place workspace confinement for file tools (ignoring 'repo' argument, blocking traversal)
- Dependency-aware ticket scheduling & BLOCKED propagation on failure
- Run logger complete audit trail (events.jsonl, summary.json, runs_index.jsonl)
- Token budget exhaustion aborting remaining tickets
- Git push security guard on worker agents
- Honest ticket failure reporting (ITERATION_LIMIT, LOOP_DETECTED)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from multi_agent_coder.common.config import (
    ConfigError,
    SwarmConfig,
    parse_token_limit,
    parse_agent_names,
    resolve_workspace,
    workspace_source,
)
from multi_agent_coder.common.token_budget import TokenBudget, TokenBudgetExceeded
from multi_agent_coder.orchestrator.ticket import Ticket, TicketStatus
from multi_agent_coder.orchestrator.agent_worker import AgentWorker, AgentFailure
from multi_agent_coder.orchestrator.main_orchestrator import MainOrchestrator
from multi_agent_coder.orchestrator.run_logger import (
    SwarmRunLogger,
    read_run_log,
    read_run_index,
)
from multi_agent_coder.tools.files import (
    execute_read_file,
    execute_list_directory,
)
from multi_agent_coder.tools.coding import execute_write_file
from multi_agent_coder.mcp.server import create_mcp_server


# -----------------------------------------------------------------------------
# 1. Configuration tests
# -----------------------------------------------------------------------------
def test_parse_token_limit_unlimited_variants():
    for val in (None, "", "   ", "none", "None", "NULL", "null", "nil", "unlimited", "off", "false", "no", "-1", -1, 0):
        assert parse_token_limit(val) is None, f"Expected None for {val!r}"


def test_parse_token_limit_positive_numbers():
    assert parse_token_limit(500000) == 500000
    assert parse_token_limit("250000") == 250000
    assert parse_token_limit(" 1000 ") == 1000


def test_parse_token_limit_invalid_raises():
    with pytest.raises(ConfigError):
        parse_token_limit("not-a-number")
    with pytest.raises(ConfigError):
        parse_token_limit("500k")


def test_parse_agent_names():
    assert parse_agent_names(None) == []
    assert parse_agent_names("") == []
    assert parse_agent_names("Alpha, Beta, Gamma") == ["Alpha", "Beta", "Gamma"]
    with pytest.raises(ConfigError):
        parse_agent_names("Alpha, Alpha, Beta")


def test_resolve_workspace_precedence(tmp_path: Path, monkeypatch):
    dir_explicit = tmp_path / "explicit"
    dir_explicit.mkdir()
    dir_env = tmp_path / "env_target"
    dir_env.mkdir()
    dir_default = tmp_path / "default_dir"
    dir_default.mkdir()

    # 1. Explicit argument wins
    monkeypatch.setenv("TARGET_WORKSPACE", str(dir_env))
    assert resolve_workspace(dir_explicit, default=dir_default) == dir_explicit.resolve()
    assert workspace_source(dir_explicit) == "argument"

    # 2. TARGET_WORKSPACE wins when explicit is None
    assert resolve_workspace(None, default=dir_default) == dir_env.resolve()
    assert workspace_source(None) == "TARGET_WORKSPACE"

    # 3. Default wins when no TARGET_WORKSPACE
    monkeypatch.delenv("TARGET_WORKSPACE", raising=False)
    assert resolve_workspace(None, default=dir_default) == dir_default.resolve()

    # 4. Non-existent path raises ConfigError
    with pytest.raises(ConfigError):
        resolve_workspace(tmp_path / "does_not_exist")


# -----------------------------------------------------------------------------
# 2. Token Budget tests
# -----------------------------------------------------------------------------
def test_token_budget_unlimited():
    budget = TokenBudget(None)
    assert budget.unlimited is True
    assert budget.exhausted is False
    assert budget.remaining is None

    budget.record(100_000)
    budget.check()  # should not raise
    assert budget.used == 100_000
    assert budget.exhausted is False


def test_token_budget_limited_exhaustion():
    budget = TokenBudget(50_000)
    assert budget.unlimited is False
    assert budget.remaining == 50_000

    budget.record(20_000)
    budget.check()
    assert budget.remaining == 30_000
    assert budget.exhausted is False

    budget.record(35_000)
    assert budget.exhausted is True
    assert budget.remaining == 0
    with pytest.raises(TokenBudgetExceeded) as exc_info:
        budget.check()
    assert "exhausted" in str(exc_info.value).lower()


# -----------------------------------------------------------------------------
# 3. In-place workspace file isolation tests
# -----------------------------------------------------------------------------
def test_file_tools_in_place_workspace(tmp_path: Path):
    ws = tmp_path / "target_project"
    ws.mkdir()
    sub = ws / "sub"
    sub.mkdir()
    sample = sub / "app.py"
    sample.write_text("print('in target project')", encoding="utf-8")

    # execute_read_file with workspace_root ignores 'repo' param and reads target project in place
    content = execute_read_file(None, {"repo": "some-other-repo", "file_path": "sub/app.py"}, workspace_root=ws)
    assert "in target project" in content

    # execute_write_file writes in target project in place
    write_res = execute_write_file({"repo": "irrelevant", "file_path": "sub/new.py", "content": "x = 42"}, workspace_root=ws)
    assert (sub / "new.py").read_text(encoding="utf-8") == "x = 42"

    # execute_list_directory lists target project files
    listing = execute_list_directory(None, {"directory_path": "sub"}, workspace_root=ws)
    assert "app.py" in listing
    assert "new.py" in listing

    # Traversal attempt outside workspace_root is blocked safely
    res = execute_write_file({"file_path": "../../escaped.txt", "content": "bad"}, workspace_root=ws)
    assert "Error:" in res and "Path traversal blocked" in res


# -----------------------------------------------------------------------------
# 4. Dependency-aware scheduling and BLOCKED propagation
# -----------------------------------------------------------------------------
def test_dependency_scheduling_and_blocked_propagation(tmp_path: Path):
    orch = MainOrchestrator(
        max_agents=2,
        queue_limit_per_agent=2,
        workspace_root=tmp_path,
        api_key="dummy_key",
    )

    t1 = Ticket.create(title="Base module", description="Create base", category="coding")
    t2 = Ticket.create(title="Feature on base", description="Build feature", category="coding", depends_on=[t1.id])
    t3 = Ticket.create(title="Tests for feature", description="Test feature", category="testing", depends_on=[t2.id])
    t_indep = Ticket.create(title="Independent task", description="Unrelated docs", category="docs")

    orch.all_tickets = [t1, t2, t3, t_indep]
    orch.pending_backlog = [t1, t2, t3, t_indep]

    # Initial dispatch should only dispatch t1 and t_indep (t2 and t3 prerequisites not met)
    dispatched = orch.dispatch_all_pending()
    assert dispatched == 2
    assert t1.status == TicketStatus.QUEUED
    assert t_indep.status == TicketStatus.QUEUED
    assert t2 in orch.pending_backlog
    assert t3 in orch.pending_backlog

    # Simulate t1 failing
    t1.mark_failed("Syntax error occurred", code="AGENT_ERROR")

    # Next dispatch round: t2 should be BLOCKED because t1 failed, and t3 should be BLOCKED because t2 was blocked
    orch.dispatch_all_pending()
    assert t2.status == TicketStatus.BLOCKED
    assert t2.failure_code == "DEPENDENCY_FAILED"
    assert t3.status == TicketStatus.BLOCKED
    assert t3.failure_code == "DEPENDENCY_FAILED"


# -----------------------------------------------------------------------------
# 5. Run logger audit trail tests
# -----------------------------------------------------------------------------
def test_run_logger_audit_trail(tmp_path: Path):
    log_dir = tmp_path / "swarm_logs"
    logger = SwarmRunLogger(
        log_dir=log_dir,
        objective="Test Run",
        workspace_root=tmp_path,
        model="gemini-2.5-flash-lite",
        token_limit=100_000,
        max_agents=2,
        queue_limit=2,
    )

    t = Ticket.create(title="Task A", description="Desc A", category="coding")
    logger.ticket_created(t)
    logger.ticket_assigned(t, agent_id="Agent-1", queue_depth=1)
    logger.ticket_started(t, agent_id="Agent-1")
    logger.tool_call("Agent-1", t.id, "read_file", "app.py")
    logger.llm_usage("Agent-1", t.id, prompt=500, completion=200, total=700, run_total=700)
    logger.ticket_completed(t, agent_id="Agent-1")

    summary = {
        "total_tickets": 1,
        "resolved": 1,
        "failed": 0,
        "blocked": 0,
        "token_usage": {"used": 700, "limit": 100000},
    }
    logger.finalize(summary)

    # Verify run directory structure and contents
    run_data = read_run_log(log_dir, run_id=logger.run_id)
    assert run_data["summary"]["resolved"] == 1
    assert run_data["summary"]["total_tickets"] == 1
    event_types = [e["event"] for e in run_data["events"]]
    assert "ticket_created" in event_types
    assert "ticket_assigned" in event_types
    assert "ticket_started" in event_types
    assert "tool_call" in event_types
    assert "llm_usage" in event_types
    assert "ticket_completed" in event_types
    assert "run_finished" in event_types

    # Verify index
    index = read_run_index(log_dir)
    assert len(index) == 1
    assert index[0]["run_id"] == logger.run_id
    assert index[0]["resolved"] == 1


# -----------------------------------------------------------------------------
# 6. Token budget abort in orchestrator
# -----------------------------------------------------------------------------
def test_token_budget_abort_orchestrator(tmp_path: Path):
    orch = MainOrchestrator(
        max_agents=1,
        queue_limit_per_agent=2,
        workspace_root=tmp_path,
        token_limit=500,
        api_key="dummy_key",
    )

    t1 = Ticket.create(title="Task 1", description="First", category="coding")
    t2 = Ticket.create(title="Task 2", description="Second", category="coding")
    orch.all_tickets = [t1, t2]
    orch.pending_backlog = [t1, t2]

    # Mock execute_ticket_task to consume more tokens than budget
    def fake_execute(ticket):
        orch.token_budget.record(1000)
        return "Done task 1"

    agent = orch.agents[0]
    agent.execute_ticket_task = fake_execute

    resolved = orch.process_all_tickets_synchronously()
    assert len(resolved) == 1
    assert t1.status == TicketStatus.RESOLVED

    # Task 2 should be marked BLOCKED because token budget was exhausted
    assert t2.status == TicketStatus.BLOCKED
    assert t2.failure_code == "TOKEN_BUDGET_EXHAUSTED"


# -----------------------------------------------------------------------------
# 7. AgentWorker git push security guard
# -----------------------------------------------------------------------------
def test_agent_worker_git_push_guard(tmp_path: Path):
    worker = AgentWorker(
        agent_id="Agent-1",
        role="Coder",
        specialty="coding",
        workspace_root=tmp_path,
        api_key="dummy_key",
        allow_git_write=False,
    )

    # git_push should not be in declared tools
    worker_tools = worker._build_worker_tools()
    tool_names = {t["name"] for t in worker_tools[0]["function_declarations"]}
    assert "git_push" not in tool_names

    # Calling git_push directly returns an error and does not execute
    res = worker._execute_tool("git_push", {})
    assert "disabled" in res.lower()


# -----------------------------------------------------------------------------
# 8. Honest failure reporting (ITERATION_LIMIT and LOOP_DETECTED)
# -----------------------------------------------------------------------------
def test_agent_worker_honest_iteration_limit(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAX_WORKER_ITERATIONS", "2")
    worker = AgentWorker(
        agent_id="Agent-1",
        role="Coder",
        specialty="coding",
        workspace_root=tmp_path,
        api_key="real-api-key-to-trigger-loop",  # Not dummy
    )

    # Mock _generate to simulate agent calling a tool endlessly without finishing
    mock_call = MagicMock()
    mock_call.name = "run_command"
    mock_call.args = {"command": "echo test"}
    mock_part = MagicMock()
    mock_part.function_call = mock_call
    mock_part.text = None
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    mock_candidate = MagicMock(content=mock_content)
    mock_response = MagicMock(candidates=[mock_candidate])

    with patch.object(worker, "_generate", return_value=mock_response):
        t = Ticket.create(title="Endless task", description="Do stuff", category="coding")
        worker.queue.append(t)
        finished = worker.process_next_ticket()

        assert finished is not None
        assert finished.status == TicketStatus.FAILED
        assert finished.failure_code == "ITERATION_LIMIT"


# -----------------------------------------------------------------------------
# 9. MCP server tools and workspace argument
# -----------------------------------------------------------------------------
def test_mcp_server_tools_and_workspace():
    server = create_mcp_server()
    # Find registered tool names
    tool_names = set(server._tool_manager._tools.keys())
    assert "swarm_submit_dag" in tool_names
    assert "swarm_dispatch_objective" in tool_names
    assert "swarm_status" in tool_names
    assert "swarm_get_run_log" in tool_names
    assert "swarm_get_worktree_diff" in tool_names
    assert "swarm_merge_worktree" in tool_names


# -----------------------------------------------------------------------------
# 10. Optimistic concurrency race condition & collision recovery
# -----------------------------------------------------------------------------
def test_run_store_optimistic_concurrency_race_condition(tmp_path: Path):
    """
    Intentionally causes a concurrent race condition in run_store.py,
    proving that optimistic concurrency version checking catches the collision
    with ConcurrencyError and successfully recovers when state is re-fetched.
    """
    from multi_agent_coder.store.run_store import RunStateStore, ConcurrencyError

    db_path = tmp_path / "runs.db"
    store = RunStateStore(db_path)

    run_id = "run-race-test-01"
    store.record_run_start(run_id=run_id, objective="Test Race Condition Handling")

    # Step 1: Agent A and Agent B perform concurrent dirty reads of the current state
    state_a = store.get_run(run_id)
    state_b = store.get_run(run_id)

    assert state_a is not None and state_b is not None
    assert state_a["version"] == 1
    assert state_b["version"] == 1

    # Step 2: Agent A updates the run state first with expected_version=1
    new_version_a = store.update_run_state(
        run_id=run_id,
        state={"status": "IN_PROGRESS", "active_agent": "Agent-A"},
        expected_version=state_a["version"],
    )
    assert new_version_a == 2

    # Step 3: Agent B attempts to update the run state with its stale expected_version=1
    # Proves that the optimistic concurrency check catches the collision and raises ConcurrencyError!
    with pytest.raises(ConcurrencyError) as exc_info:
        store.update_run_state(
            run_id=run_id,
            state={"status": "IN_PROGRESS", "active_agent": "Agent-B"},
            expected_version=state_b["version"],  # Stale version 1!
        )
    assert "version collision" in str(exc_info.value).lower()

    # Step 4: Recovery: Agent B re-fetches the latest state, sees the current version, and reapplies
    fresh_state_b = store.get_run(run_id)
    assert fresh_state_b is not None
    assert fresh_state_b["version"] == 2
    assert fresh_state_b["state"]["active_agent"] == "Agent-A"

    new_version_b = store.update_run_state(
        run_id=run_id,
        state={"status": "IN_PROGRESS", "active_agent": "Agent-B", "recovered": True},
        expected_version=fresh_state_b["version"],
    )
    assert new_version_b == 3

    # Step 5: Final state verification
    final_run = store.get_run(run_id)
    assert final_run is not None
    assert final_run["version"] == 3
    assert final_run["state"]["active_agent"] == "Agent-B"
    assert final_run["state"]["recovered"] is True


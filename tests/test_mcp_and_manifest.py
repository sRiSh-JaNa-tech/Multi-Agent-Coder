"""
Tests for Manifest DAG ingestion, Headless execution, and MCP Server tools.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from multi_agent_coder.orchestrator.main_orchestrator import MainOrchestrator
from multi_agent_coder.orchestrator.ticket import TicketStatus
from multi_agent_coder.mcp.server import create_mcp_server


def test_main_orchestrator_load_manifest_valid():
    """Verify loading a pre-defined ticket DAG manifest."""
    manifest = {
        "objective": "Add caching layer",
        "tickets": [
            {
                "id": "TICK-TEST1",
                "title": "Analyze cache specs",
                "description": "Inspect cache memory limits",
                "category": "analysis",
                "depends_on": [],
            },
            {
                "id": "TICK-TEST2",
                "title": "Implement LRU cache",
                "description": "Write LRU cache class",
                "category": "coding",
                "depends_on": ["TICK-TEST1"],
            },
            {
                "id": "TICK-TEST3",
                "title": "Add cache tests",
                "description": "Verify LRU eviction",
                "category": "testing",
                "depends_on": ["TICK-TEST2"],
            },
        ],
    }

    orch = MainOrchestrator(max_agents=2, api_key="dummy-key")
    tickets = orch.load_manifest(manifest)

    assert len(tickets) == 3
    assert len(orch.all_tickets) == 3
    assert len(orch.pending_backlog) == 3
    assert orch.all_tickets[0].id == "TICK-TEST1"
    assert orch.all_tickets[1].depends_on == ["TICK-TEST1"]
    assert orch.all_tickets[2].depends_on == ["TICK-TEST2"]


def test_main_orchestrator_load_manifest_cycle_rejection():
    """Verify circular dependencies in manifest are caught by Kahn's algorithm."""
    cyclic_manifest = {
        "tickets": [
            {"id": "T1", "title": "A", "description": "A", "depends_on": ["T2"]},
            {"id": "T2", "title": "B", "description": "B", "depends_on": ["T1"]},
        ]
    }
    orch = MainOrchestrator(max_agents=2, api_key="dummy-key")
    with pytest.raises(ValueError, match="Cycle detected"):
        orch.load_manifest(cyclic_manifest)


def test_main_orchestrator_summary_format():
    """Verify export summary structure contains required fields."""
    orch = MainOrchestrator(max_agents=2, api_key="dummy-key")
    orch.load_manifest({
        "tickets": [
            {"id": "TICK-S1", "title": "Summary test", "description": "Test summary", "category": "coding"}
        ]
    })
    summary = orch.get_summary()

    assert "total_tickets" in summary
    assert "resolved" in summary
    assert "failed" in summary
    assert "agents" in summary
    assert "tickets" in summary
    assert len(summary["tickets"]) == 1
    assert summary["tickets"][0]["id"] == "TICK-S1"


def test_mcp_server_initialization_and_tool_registration():
    """Verify MCP server registers all expected tools."""
    server = create_mcp_server()
    assert server.name == "MultiAgentCoderSwarm"


def test_mcp_server_list_tools():
    """Verify tool discovery on the MCP server."""
    import asyncio
    server = create_mcp_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {t.name for t in tools}

    expected_tools = {
        "swarm_submit_dag",
        "swarm_dispatch_objective",
        "swarm_status",
        "swarm_get_worktree_diff",
        "swarm_merge_worktree",
    }
    assert expected_tools.issubset(tool_names)


def test_env_controls_max_agents_and_queue_limit(monkeypatch):
    """Verify that MAX_AGENTS and QUEUE_LIMIT_PER_AGENT in environment dynamically configure the swarm."""
    monkeypatch.setenv("MAX_AGENTS", "4")
    monkeypatch.setenv("QUEUE_LIMIT_PER_AGENT", "5")

    orch = MainOrchestrator(api_key="dummy-key")

    assert orch.max_agents == 4
    assert len(orch.agents) == 4
    assert orch.queue_limit_per_agent == 5
    for agent in orch.agents:
        assert agent.queue_limit == 5


def test_env_controls_queue_limit_aliases(monkeypatch):
    """Verify alternative env variable names AGENT_QUEUE_LIMIT and MAX_QUEUE_SIZE."""
    monkeypatch.delenv("QUEUE_LIMIT_PER_AGENT", raising=False)
    monkeypatch.setenv("AGENT_QUEUE_LIMIT", "2")
    orch1 = MainOrchestrator(api_key="dummy-key")
    assert orch1.queue_limit_per_agent == 2

    monkeypatch.delenv("AGENT_QUEUE_LIMIT", raising=False)
    monkeypatch.setenv("MAX_QUEUE_SIZE", "6")
    orch2 = MainOrchestrator(api_key="dummy-key")
    assert orch2.queue_limit_per_agent == 6


def test_prompt_scaffolding_structure():
    """Verify that worker system instruction includes all 5 cognitive phases and safety rules."""
    from multi_agent_coder.orchestrator.prompts import build_worker_system_instruction

    sys_inst = build_worker_system_instruction(
        agent_id="Agent-2",
        role="Core Implementation & Coding Engineer",
        specialty="coding",
        workspace_root="/test/repo",
    )

    assert "Agent-2" in sys_inst
    assert "PHASE 1: ORIENTATION" in sys_inst
    assert "PHASE 2: SURGICAL EDITING" in sys_inst
    assert "PHASE 3: SYNTAX VALIDATION" in sys_inst
    assert "PHASE 4: TEST & RUNTIME VERIFICATION" in sys_inst
    assert "PHASE 5: SELF-CORRECTION" in sys_inst
    assert "CROSS-PLATFORM COMMAND RESTRICTIONS" in sys_inst
    assert "ROLE SPECIALTY DIRECTIVES (CODING)" in sys_inst
    assert "[Agent Status: RESOLVED]" in sys_inst


def test_ticket_execution_prompt_structure():
    """Verify that ticket execution prompt renders task checklist and objective."""
    from multi_agent_coder.orchestrator.prompts import build_ticket_execution_prompt
    from multi_agent_coder.orchestrator.ticket import Ticket

    ticket = Ticket.create(
        title="Add LRU eviction",
        description="Implement Least Recently Used cache eviction with unit tests",
        category="coding",
    )

    prompt = build_ticket_execution_prompt(
        ticket=ticket,
        workspace_root="/test/repo",
        agent_id="Agent-2",
        role="Coding Engineer",
        specialty="coding",
    )

    assert ticket.id in prompt
    assert "Add LRU eviction" in prompt
    assert "Least Recently Used cache eviction" in prompt
    assert "STEP-BY-STEP EXECUTION CHECKLIST" in prompt
    assert "[ ] **Explore**" in prompt
    assert "[ ] **Validate**" in prompt
    assert "[ ] **Test**" in prompt




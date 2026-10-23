"""
Tests for general-purpose goal decomposition and autonomous iteration loop.
"""

from unittest.mock import MagicMock
from multi_agent_coder.orchestrator.planner import EvidenceDrivenPlanner
from multi_agent_coder.orchestrator.ticket import Ticket, TicketStatus
from multi_agent_coder.discovery.baseline import RepositoryBaseline, BaselineTestResult
from multi_agent_coder.orchestrator.verifier import IndependentVerifier


def test_goal_follow_up_stops_when_flag_found(tmp_path):
    baseline = RepositoryBaseline(
        workspace_root=tmp_path,
        project_type="generic",
        detected_test_command="",
        pre_existing_git_changes=[],
        test_baseline=BaselineTestResult(success=True, failing_tests=[]),
    )

    planner = EvidenceDrivenPlanner(
        workspace_root=tmp_path,
        api_key="mock_key",
    )

    # Ticket result contains flag
    t = Ticket.create(
        title="Execute solver",
        description="Run solver",
        category="coding",
    )
    t.status = TicketStatus.RESOLVED
    t.result = "Script succeeded! Output: FLAG{autonomous_solver_success_2026}"

    follow_ups = planner.plan_goal_follow_up(
        objective="Find the secret flag",
        existing_tickets=[t],
        baseline=baseline,
    )

    # Should detect the flag and return no further tickets
    assert follow_ups == []


def test_verifier_permits_wildcard_target_files(tmp_path):
    baseline = RepositoryBaseline(
        workspace_root=tmp_path,
        project_type="generic",
        detected_test_command="",
        pre_existing_git_changes=[],
        test_baseline=BaselineTestResult(success=True, failing_tests=[]),
    )
    verifier = IndependentVerifier(workspace_root=tmp_path, baseline=baseline)

    # Ticket with wildcard target_files (general purpose task)
    t = Ticket.create(
        title="Run exploration script",
        description="Inspect files",
        category="analysis",
        target_files=["*"],
    )
    t.actual_files_modified = ["exploit.py", "output.txt"]

    res = verifier.verify_ticket(t)
    # Should not report scope violation
    assert res.scope_violations == []


def test_goal_follow_up_generates_tickets_on_error(tmp_path):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '''
[
  {
    "title": "Retry with alternative payload",
    "description": "Previous attempt encountered 403 Forbidden. Try with auth header.",
    "category": "coding",
    "target_files": ["*"],
    "acceptance_criteria": ["Status code 200"],
    "depends_on": []
  }
]
'''
    mock_client.models.generate_content.return_value = mock_response

    baseline = RepositoryBaseline(
        workspace_root=tmp_path,
        project_type="generic",
        detected_test_command="",
        pre_existing_git_changes=[],
        test_baseline=BaselineTestResult(success=True, failing_tests=[]),
    )

    planner = EvidenceDrivenPlanner(
        workspace_root=tmp_path,
        api_key="mock_key",
        client=mock_client,
    )

    failed_t = Ticket.create(
        title="Probe API",
        description="GET /secret",
        category="coding",
    )
    failed_t.status = TicketStatus.FAILED
    failed_t.error = "HTTPError 403: Forbidden"

    follow_ups = planner.plan_goal_follow_up(
        objective="Extract data from /secret",
        existing_tickets=[failed_t],
        baseline=baseline,
    )

    assert len(follow_ups) == 1
    assert "Retry with alternative payload" in follow_ups[0].title
    assert follow_ups[0].target_files == ["*"]

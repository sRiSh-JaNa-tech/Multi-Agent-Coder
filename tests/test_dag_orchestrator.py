import pytest
from multi_agent_coder.orchestrator.ticket import Ticket, TicketDAG, TicketStatus

def test_dag_detects_direct_and_indirect_cycles():
    tickets = [
        Ticket(id="T1", title="Setup DB", description="...", depends_on=["T3"]),
        Ticket(id="T2", title="Auth API", description="...", depends_on=["T1"]),
        Ticket(id="T3", title="UI Form", description="...", depends_on=["T2"]),
    ]
    with pytest.raises(ValueError, match="Cycle detected"):
        TicketDAG(tickets)

def test_dag_rejects_unknown_dependency():
    tickets = [Ticket(id="T1", title="Task", description="...", depends_on=["NON_EXISTENT"])]
    with pytest.raises(ValueError, match="unknown ticket"):
        TicketDAG(tickets)

def test_dag_rejects_duplicate_dependencies():
    tickets = [
        Ticket(id="T1", title="Base", description="..."),
        Ticket(id="T2", title="Child", description="...", depends_on=["T1", "T1"]),
    ]
    with pytest.raises(ValueError, match="duplicate dependencies"):
        TicketDAG(tickets)

def test_dag_blocks_downstream_on_upstream_failure():
    t1 = Ticket(id="T1", title="Base", description="...")
    t2 = Ticket(id="T2", title="Child", description="...", depends_on=["T1"])
    t3 = Ticket(id="T3", title="Independent", description="...")
    dag = TicketDAG([t1, t2, t3])

    # Initially T1 and T3 are ready
    ready_ids = {t.id for t in dag.get_ready_tickets()}
    assert ready_ids == {"T1", "T3"}

    # Simulate T1 failing permanently
    t1.status = TicketStatus.FAILED
    t3.status = TicketStatus.COMPLETED

    ready_after_fail = dag.get_ready_tickets()
    assert ready_after_fail == []
    assert t2.status == TicketStatus.BLOCKED

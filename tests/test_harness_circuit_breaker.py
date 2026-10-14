import pytest
from multi_agent_coder.common.token_tracker import (
    ExecutionGuard,
    BudgetExceededError,
    InfiniteLoopError,
)

def test_trips_circuit_breaker_on_repeated_identical_tool_calls():
    guard = ExecutionGuard(max_tokens=10_000, max_identical_calls=3)
    args = {"query": "def main", "path": "src/"}

    guard.record_tool_call("search_code", args)
    guard.record_tool_call("search_code", args)

    # Third identical call must trip the circuit breaker
    with pytest.raises(InfiniteLoopError, match="Circuit breaker tripped"):
        guard.record_tool_call("search_code", args)

def test_enforces_token_budget_ceiling():
    guard = ExecutionGuard(max_tokens=1000)
    guard.record_tokens(prompt_tokens=400, completion_tokens=300)

    with pytest.raises(BudgetExceededError, match="Token budget exceeded"):
        guard.record_tokens(prompt_tokens=250, completion_tokens=100)

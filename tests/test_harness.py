"""
Unit & Integration Tests for the LLM Testing and Execution Harness.
Validates:
- BaseLLMAdapter & MockLLMAdapter
- CallableAdapter
- HarnessAgent ReAct loop (autonomous tool calling & synthesis)
- HarnessTicketWorker (queue limit 3, synchronous FIFO resolution)
- Token usage accumulation
- Error handling
"""

import unittest
from typing import Any

from multi_agent_coder.harness import (
    BaseLLMAdapter,
    CallableAdapter,
    HarnessAgent,
    HarnessTicketWorker,
    LLMResponse,
    Message,
    MockLLMAdapter,
    TokenUsage,
    ToolCall,
    ToolResult,
)
from multi_agent_coder.orchestrator.ticket import Ticket, TicketStatus


class TestLLMHarness(unittest.TestCase):
    """Test suite for the pluggable LLM harness."""

    def test_mock_adapter_basic(self):
        """Verify MockLLMAdapter yields scripted responses in sequence."""
        adapter = MockLLMAdapter(
            responses=[
                "First response",
                {"text": "Second with tool", "tool_calls": [{"name": "fake_tool", "args": {"x": 1}}]},
                LLMResponse(text="Third response", usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10)),
            ]
        )

        r1 = adapter.generate(messages=[Message(role="user", content="Hello")])
        self.assertEqual(r1.text, "First response")
        self.assertFalse(r1.has_tool_calls)

        r2 = adapter.generate(messages=[Message(role="user", content="Next")])
        self.assertEqual(r2.text, "Second with tool")
        self.assertTrue(r2.has_tool_calls)
        self.assertEqual(r2.tool_calls[0].name, "fake_tool")
        self.assertEqual(r2.tool_calls[0].args, {"x": 1})

        r3 = adapter.generate(messages=[Message(role="user", content="Final")])
        self.assertEqual(r3.text, "Third response")
        self.assertEqual(r3.usage.total_tokens, 10)

        # Fallback response when queue empty
        r4 = adapter.generate(messages=[])
        self.assertIn("No further scripted responses", r4.text)

    def test_callable_adapter(self):
        """Verify CallableAdapter executes arbitrary Python callable."""
        def custom_brain(messages: list[Message], tools: list[dict[str, Any]] | None, system_instruction: str | None = None):
            count = len(messages)
            return f"Processed {count} messages with model {system_instruction or 'none'}"

        adapter = CallableAdapter(fn=custom_brain, model_name="brain-1")
        resp = adapter.generate(
            messages=[Message(role="user", content="A"), Message(role="assistant", content="B")],
            system_instruction="sys",
        )
        self.assertIn("Processed 2 messages", resp.text)
        self.assertIn("sys", resp.text)

    def test_harness_agent_react_loop(self):
        """Verify HarnessAgent executes tool calls and feeds results back into LLM."""
        executed_math = []

        def mock_add(a: int, b: int) -> int:
            result = a + b
            executed_math.append(result)
            return result

        mock_adapter = MockLLMAdapter(
            responses=[
                # Turn 1: request tool call
                {
                    "text": "Adding numbers",
                    "tool_calls": [{"name": "add", "args": {"a": 40, "b": 2}}]
                },
                # Turn 2: final answer after receiving result
                "The sum is 42."
            ]
        )

        agent = HarnessAgent(
            adapter=mock_adapter,
            tool_registry={"add": mock_add},
            max_iterations=5,
        )

        result = agent.run("What is 40 + 2?")
        self.assertTrue(result.success)
        self.assertEqual(result.final_answer, "The sum is 42.")
        self.assertEqual(result.iterations, 2)
        self.assertEqual(result.tools_invoked, ["add"])
        self.assertEqual(executed_math, [42])

        # Check history has user -> assistant(tool_call) -> tool(result) -> assistant(final)
        roles = [m.role for m in agent.conversation_history]
        self.assertEqual(roles, ["user", "assistant", "tool", "assistant"])

    def test_harness_agent_tool_error_handling(self):
        """Verify HarnessAgent gracefully captures unknown or failing tools without crashing."""
        def broken_tool():
            raise RuntimeError("Database connection timed out")

        mock_adapter = MockLLMAdapter(
            responses=[
                {
                    "text": "Calling tools",
                    "tool_calls": [
                        {"name": "missing_tool", "args": {}},
                        {"name": "failing_tool", "args": {}},
                    ]
                },
                "Handled failures."
            ]
        )

        agent = HarnessAgent(
            adapter=mock_adapter,
            tool_registry={"failing_tool": broken_tool},
            max_iterations=5,
        )

        result = agent.run("Test error handling")
        self.assertTrue(result.success)
        self.assertEqual(result.final_answer, "Handled failures.")

        # Inspect tool results
        step1 = result.steps[0]
        self.assertEqual(len(step1.tool_results), 2)
        self.assertTrue(step1.tool_results[0].is_error)
        self.assertIn("not found in registry", step1.tool_results[0].output)
        self.assertTrue(step1.tool_results[1].is_error)
        self.assertIn("Database connection timed out", step1.tool_results[1].output)

    def test_harness_ticket_worker_queue_and_sync(self):
        """Verify HarnessTicketWorker enforces queue limit of 3 and synchronous execution."""
        mock_adapter = MockLLMAdapter(
            responses=[
                "Resolved Ticket 1",
                "Resolved Ticket 2",
                "Resolved Ticket 3",
            ]
        )

        worker = HarnessTicketWorker(
            agent_id="Worker-Sync-Test",
            role="Specialist",
            adapter=mock_adapter,
            queue_limit=3,
        )

        # Enqueue 3 tickets
        t1 = Ticket.create(title="Task 1", description="Desc 1")
        t2 = Ticket.create(title="Task 2", description="Desc 2")
        t3 = Ticket.create(title="Task 3", description="Desc 3")

        self.assertTrue(worker.can_accept_ticket())
        worker.enqueue_ticket(t1)
        worker.enqueue_ticket(t2)
        worker.enqueue_ticket(t3)

        self.assertEqual(worker.queue_size, 3)
        self.assertTrue(worker.is_full)
        self.assertFalse(worker.can_accept_ticket())

        # 4th ticket must be rejected
        t4 = Ticket.create(title="Task 4", description="Desc 4")
        with self.assertRaises(ValueError):
            worker.enqueue_ticket(t4)

        # Process all tickets synchronously
        resolved = worker.run_all_tickets_sync()
        self.assertEqual(len(resolved), 3)
        self.assertEqual(worker.queue_size, 0)
        self.assertFalse(worker.is_full)

        # Verify FIFO order and status transitions
        self.assertEqual([t.title for t in resolved], ["Task 1", "Task 2", "Task 3"])
        for t in resolved:
            self.assertEqual(t.status, TicketStatus.RESOLVED)
            self.assertIsNotNone(t.result)
            self.assertIsNotNone(t.started_at)
            self.assertIsNotNone(t.completed_at)

    def test_token_usage_aggregation(self):
        """Verify token counts aggregate properly across multi-turn runs."""
        mock_adapter = MockLLMAdapter(
            responses=[
                LLMResponse(
                    text="Step 1",
                    tool_calls=[ToolCall(name="noop", args={})],
                    usage=TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120)
                ),
                LLMResponse(
                    text="Step 2 Final",
                    usage=TokenUsage(prompt_tokens=150, completion_tokens=30, total_tokens=180)
                ),
            ]
        )

        agent = HarnessAgent(
            adapter=mock_adapter,
            tool_registry={"noop": lambda: "ok"},
            max_iterations=5,
        )

        res = agent.run("Calculate tokens")
        self.assertEqual(res.total_usage.prompt_tokens, 250)
        self.assertEqual(res.total_usage.completion_tokens, 50)
        self.assertEqual(res.total_usage.total_tokens, 300)


if __name__ == "__main__":
    unittest.main()

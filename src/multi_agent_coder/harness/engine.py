"""
Harness Agent Execution Engine.
Autonomous ReAct loop that executes tasks using an attached BaseLLMAdapter,
a pluggable tool registry, and an ExecutionGuard circuit breaker.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Callable

from ..common.token_tracker import ExecutionGuard, BudgetExceededError, InfiniteLoopError
from .base import BaseLLMAdapter
from .types import Message, ToolCall, ToolResult, TokenUsage, LLMResponse


@dataclass
class AgentStep:
    """Represents a single step in the agent reasoning and execution loop."""
    iteration: int
    thought: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    duration_s: float = 0.0


@dataclass
class AgentRunResult:
    """Summary result returned after agent execution completes."""
    final_answer: str
    steps: list[AgentStep] = field(default_factory=list)
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    tools_invoked: list[str] = field(default_factory=list)
    success: bool = True
    iterations: int = 0
    error: str | None = None


DEFAULT_SYSTEM_INSTRUCTION = """You are an expert autonomous software engineer and codebase navigator.
You have access to specialized tools to inspect files, edit code, check syntax, and run tests.

MANDATORY OPERATIONAL DISCIPLINE:
1. ORIENT FIRST: Never guess file contents or structure. Always call read_file or list_directory before editing.
2. SURGICAL EDITS: When modifying code, match target lines exactly (including whitespace/indentation). Do not leave placeholders.
3. SYNTAX GATING: Validate Python syntax immediately after any modification.
4. TEST VALIDATION: Execute tests (e.g. pytest) via run_command to confirm your solution works.
5. ERROR RECOVERY: If a tool call fails, diagnose the error and adjust your parameters. Never repeat identical failed calls.
6. RESOLUTION: Conclude with a clear summary of changes made, files modified, and verification results.
"""


class HarnessAgent:
    """
    Autonomous ReAct agent decoupled from any specific LLM provider.
    Can be attached to Gemini, Mock, OpenAI, or custom function adapters.
    Equipped with an ExecutionGuard circuit breaker for token spend and duplicate calls.
    """

    def __init__(
        self,
        adapter: BaseLLMAdapter,
        tool_declarations: list[dict[str, Any]] | None = None,
        tool_registry: dict[str, Callable] | None = None,
        system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION,
        max_iterations: int = 10,
        console: Any | None = None,
        guard: ExecutionGuard | None = None,
    ):
        self.adapter = adapter
        self.tool_declarations = tool_declarations or []
        self.tool_registry = tool_registry or {}
        self.system_instruction = system_instruction
        self.max_iterations = max_iterations
        self.console = console
        self.guard = guard or ExecutionGuard()
        self.conversation_history: list[Message] = []
        self.total_usage = TokenUsage()

    def register_tool(self, name: str, fn: Callable, declaration: dict[str, Any] | None = None) -> None:
        """Register a new tool and optionally its schema declaration."""
        self.tool_registry[name] = fn
        if declaration:
            self.tool_declarations.append(declaration)

    def run(self, prompt: str) -> AgentRunResult:
        """
        Execute an autonomous ReAct loop on the provided user prompt.
        Guarded against infinite tool loops and budget overruns.
        """
        self.conversation_history.append(Message(role="user", content=prompt))
        steps: list[AgentStep] = []
        tools_invoked: list[str] = []
        final_answer = ""
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            step_start = time.perf_counter()

            # Query the attached LLM adapter
            try:
                response: LLMResponse = self.adapter.generate(
                    messages=self.conversation_history,
                    tools=self.tool_declarations,
                    system_instruction=self.system_instruction,
                )
            except Exception as e:
                err_msg = f"LLM generation failed: {e}"
                if self.console:
                    self.console.print(f"[bold red]Adapter Error:[/bold red] {err_msg}")
                return AgentRunResult(
                    final_answer="",
                    steps=steps,
                    total_usage=self.total_usage,
                    tools_invoked=tools_invoked,
                    success=False,
                    iterations=iteration,
                    error=err_msg,
                )

            # Check and record tokens in ExecutionGuard
            try:
                self.guard.record_tokens(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )
            except BudgetExceededError as e:
                err_msg = f"ExecutionGuard tripped: {e}"
                if self.console:
                    self.console.print(f"[bold red]{err_msg}[/bold red]")
                return AgentRunResult(
                    final_answer="",
                    steps=steps,
                    total_usage=self.total_usage,
                    tools_invoked=tools_invoked,
                    success=False,
                    iterations=iteration,
                    error=err_msg,
                )

            # Accumulate token usage
            self.total_usage.prompt_tokens += response.usage.prompt_tokens
            self.total_usage.completion_tokens += response.usage.completion_tokens
            self.total_usage.total_tokens += response.usage.total_tokens

            step = AgentStep(
                iteration=iteration,
                thought=response.text,
                tool_calls=list(response.tool_calls),
            )

            if response.text and self.console:
                self.console.print(f"[cyan]Agent Thought:[/cyan] {response.text}")

            # Case A: Model requested tool calls
            if response.has_tool_calls:
                self.conversation_history.append(
                    Message(
                        role="assistant",
                        content=response.text,
                        tool_calls=response.tool_calls,
                    )
                )

                tool_results: list[ToolResult] = []
                for call in response.tool_calls:
                    # Guard against repeated identical tool calls
                    try:
                        self.guard.record_tool_call(call.name, call.args)
                    except InfiniteLoopError as e:
                        err_msg = f"ExecutionGuard tripped: {e}"
                        if self.console:
                            self.console.print(f"[bold red]{err_msg}[/bold red]")
                        return AgentRunResult(
                            final_answer="",
                            steps=steps,
                            total_usage=self.total_usage,
                            tools_invoked=tools_invoked,
                            success=False,
                            iterations=iteration,
                            error=err_msg,
                        )

                    tools_invoked.append(call.name)
                    tool_fn = self.tool_registry.get(call.name)

                    if self.console:
                        self.console.print(f"[yellow]Tool Call:[/yellow] {call.name}({call.args})")

                    if tool_fn is None:
                        out = f"Error: Tool '{call.name}' not found in registry."
                        tool_results.append(ToolResult(name=call.name, output=out, tool_call_id=call.id, is_error=True))
                        continue

                    try:
                        raw_out = tool_fn(**call.args)
                        out_str = str(raw_out)
                        tool_results.append(ToolResult(name=call.name, output=out_str, tool_call_id=call.id, is_error=False))
                        if self.console:
                            preview = out_str[:200] + ("..." if len(out_str) > 200 else "")
                            self.console.print(f"[green]Tool Output ({call.name}):[/green] {preview}")
                    except Exception as e:
                        err_out = f"Error executing tool '{call.name}': {e}"
                        tool_results.append(ToolResult(name=call.name, output=err_out, tool_call_id=call.id, is_error=True))
                        if self.console:
                            self.console.print(f"[bold red]Tool Execution Error:[/bold red] {err_out}")

                step.tool_results = tool_results
                step.duration_s = time.perf_counter() - step_start
                steps.append(step)

                # Feed results back to conversation history
                self.conversation_history.append(
                    Message(
                        role="tool",
                        tool_results=tool_results,
                    )
                )
                continue

            # Case B: Model produced final response
            final_answer = response.text or ""
            step.duration_s = time.perf_counter() - step_start
            steps.append(step)
            self.conversation_history.append(Message(role="assistant", content=final_answer))
            break

        return AgentRunResult(
            final_answer=final_answer,
            steps=steps,
            total_usage=self.total_usage,
            tools_invoked=tools_invoked,
            success=True,
            iterations=iteration,
        )

    @classmethod
    def with_codebase_tools(
        cls,
        adapter: BaseLLMAdapter,
        root_dir: str = ".",
        console: Any | None = None,
        max_iterations: int = 10,
        guard: ExecutionGuard | None = None,
    ) -> "HarnessAgent":
        """
        Factory to instantiate a HarnessAgent wired with the codebase tools and ExecutionGuard.
        """
        from ..tools import (
            FILE_TOOLS,
            CODING_TOOLS,
            EXECUTION_TOOLS,
            OUTLINE_TOOLS,
            execute_list_directory,
            execute_read_file,
            execute_create_file,
            execute_write_file,
            execute_replace_file_content,
            execute_run_command,
            execute_git_diff,
            execute_git_status,
            execute_check_syntax,
            execute_get_file_outline,
        )

        declarations = (
            FILE_TOOLS
            + CODING_TOOLS
            + EXECUTION_TOOLS
            + OUTLINE_TOOLS
        )

        def _wrap_read_file(**kwargs):
            if not kwargs.get("repo"):
                kwargs["repo"] = root_dir
            if not kwargs.get("filepath"):
                kwargs["filepath"] = kwargs.get("file_path") or kwargs.get("path") or kwargs.get("file")
            return execute_read_file(None, kwargs)

        def _wrap_list_directory(**kwargs):
            if not kwargs.get("repo"):
                kwargs["repo"] = root_dir
            if not kwargs.get("path") and kwargs.get("dir_path"):
                kwargs["path"] = kwargs.get("dir_path")
            return execute_list_directory(None, kwargs)

        registry = {
            "list_directory": _wrap_list_directory,
            "list_dir": _wrap_list_directory,
            "read_file": _wrap_read_file,
            "create_file": lambda **kwargs: execute_create_file(kwargs),
            "write_file": lambda **kwargs: execute_write_file(kwargs),
            "replace_file_content": lambda **kwargs: execute_replace_file_content(kwargs),
            "run_command": lambda **kwargs: execute_run_command(kwargs),
            "git_diff": lambda **kwargs: execute_git_diff(kwargs),
            "git_status": lambda **kwargs: execute_git_status(kwargs),
            "check_syntax": lambda **kwargs: execute_check_syntax(kwargs),
            "get_file_outline": lambda **kwargs: execute_get_file_outline(kwargs),
        }

        return cls(
            adapter=adapter,
            tool_declarations=declarations,
            tool_registry=registry,
            console=console,
            max_iterations=max_iterations,
            guard=guard,
        )

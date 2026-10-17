"""
Agent Worker with Synchronous Ticket Queue & Command/Git Tools.
Wraps an agent with a queue limit of 3 tickets, executed synchronously one by one,
with full access to terminal cmd execution (run_command), git tools, and file tools.
"""

from collections import deque
import os
import logging
import re
import time
from pathlib import Path
from typing import Callable, Any
from google import genai
from google.genai import types

try:
    from orchestrator.ticket import Ticket, TicketStatus
    from orchestrator.prompts import build_worker_system_instruction, build_ticket_execution_prompt
    from common.logging_config import setup_logging
except ImportError:
    from .ticket import Ticket, TicketStatus
    from .prompts import build_worker_system_instruction, build_ticket_execution_prompt
    from ..common.logging_config import setup_logging

from ..common.config import DEFAULT_MODEL, first_env
from ..common.token_budget import TokenBudget, TokenBudgetExceeded, usage_from_response
from ..common.token_tracker import ExecutionGuard, InfiniteLoopError

logger = setup_logging(__name__)

QUEUE_LIMIT_DEFAULT = 3

# Tools that mutate git remotes. Workers edit the target workspace in place;
# only the Lead Brain pushes after reviewing the diff, unless AGENT_GIT_WRITE_TOOLS is enabled.
GIT_WRITE_TOOLS = frozenset({"git_push"})

# File-mutating tools. A successful call changes workspace state, so loop detection restarts.
MUTATING_TOOLS = frozenset({"write_file", "create_file", "replace_file_content"})

# Calls whose result legitimately differs between identical invocations (state-dependent).
LOOP_EXEMPT_TOOLS = frozenset({"run_command", "check_syntax", "git_status", "git_diff", "git_log"})

LLM_ATTEMPTS = 3
LLM_RETRY_BASE_DELAY = 2.0
IDENTICAL_CALL_LIMIT = 4

_PSEUDO_CALL_RE = re.compile(r"default_api\.|tool_code|<ctrl\d+>", re.IGNORECASE)
_PSEUDO_CALL_CORRECTION = (
    "Your last message wrote a tool call as plain text, so nothing was executed. "
    "Use the real function-calling interface to call the tool. "
    "If the work is already finished, reply with the [Agent Status: RESOLVED] report instead."
)


class QueueFullError(Exception):
    """Raised when an agent worker's queue has reached its maximum capacity."""
    pass


class AgentFailure(Exception):
    """A ticket attempt ended unsuccessfully; ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _env_flag(name: str, default: bool = False) -> bool:
    raw = first_env(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _max_iterations() -> int:
    raw = first_env("MAX_WORKER_ITERATIONS", default="20") or "20"
    try:
        return max(1, int(raw))
    except ValueError:
        return 20


def _is_transient(exc: Exception) -> bool:
    """True for overload / rate-limit / server errors that are worth retrying."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in (429, 500, 502, 503, 504):
        return True
    text = str(exc).lower()
    return any(
        marker in text
        for marker in ("503", "unavailable", "resource_exhausted", "overloaded", "high demand", "429")
    )


def _describe_call(name: str, args: dict[str, Any]) -> str | None:
    """Short, content-free description of a tool call for logs (never file bodies)."""
    for key in ("filepath", "file_path", "path", "command"):
        value = args.get(key)
        if value:
            return str(value)[:200]
    return None


class AgentWorker:
    """
    An Agent with a ticket queue (limit 3).
    Tickets are queued up to the capacity, then executed strictly synchronously (one by one),
    with full access to cmd/terminal execution (run_command), git tools, and code modification.
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        specialty: str = "general",
        queue_limit: int = QUEUE_LIMIT_DEFAULT,
        model: str | None = None,
        api_key: str | None = None,
        workspace_root: Path | str | None = None,
        token_budget: TokenBudget | None = None,
        run_logger: Any | None = None,
        allow_git_write: bool | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.specialty = specialty
        self.queue_limit = queue_limit
        self.model = model or first_env("MODEL_NAME", "GEMINI_MODEL") or DEFAULT_MODEL
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()
        self.token_budget = token_budget
        self.run_logger = run_logger
        self.allow_git_write = (
            _env_flag("AGENT_GIT_WRITE_TOOLS", default=False)
            if allow_git_write is None
            else bool(allow_git_write)
        )
        self.tokens_used = 0

        # Internal FIFO queue - strictly holds up to queue_limit (3) tickets
        self.queue: list[Ticket] = []
        self.current_ticket: Ticket | None = None
        self.history: list[Ticket] = []

        # Client initialized on demand or passed
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not self.api_key:
                self.api_key = os.getenv("GEMINI_API_KEY", "")
            self._client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        return self._client

    @property
    def queue_size(self) -> int:
        return len(self.queue)

    @property
    def is_full(self) -> bool:
        return len(self.queue) >= self.queue_limit

    def can_accept_ticket(self) -> bool:
        """Check if this agent has capacity in its queue (limit: 3)."""
        return len(self.queue) < self.queue_limit

    def enqueue_ticket(self, ticket: Ticket) -> bool:
        """
        Add a ticket to this agent's queue.
        Raises QueueFullError if queue already has 3 tickets.
        """
        if len(self.queue) >= self.queue_limit:
            msg = (
                f"Agent '{self.agent_id}' queue is full: "
                f"cannot accept ticket {ticket.id} ({len(self.queue)}/{self.queue_limit} queued)."
            )
            logger.warning(msg)
            raise QueueFullError(msg)

        ticket.mark_queued(self.agent_id)
        self.queue.append(ticket)
        logger.info("Agent [%s] queued ticket [%s]: %s (Queue: %d/%d)",
                    self.agent_id, ticket.id, ticket.title, len(self.queue), self.queue_limit)
        if self.run_logger:
            self.run_logger.ticket_assigned(ticket, self.agent_id, len(self.queue))
        return True

    def _build_worker_tools(self) -> list[dict[str, Any]]:
        """Declare all cmd, git, and coding tools for the sub-agent."""
        try:
            from tools import EXECUTION_TOOLS, FILE_TOOLS, CODING_TOOLS
        except ImportError:
            from multi_agent_coder.tools import EXECUTION_TOOLS, FILE_TOOLS, CODING_TOOLS
        declarations = EXECUTION_TOOLS + FILE_TOOLS + CODING_TOOLS
        if not self.allow_git_write:
            declarations = [d for d in declarations if d.get("name") not in GIT_WRITE_TOOLS]
        return [{"function_declarations": declarations}]

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """Dispatch tool calls for the sub-agent in its target workspace directory."""
        if name in GIT_WRITE_TOOLS and not self.allow_git_write:
            return (
                f"Error: '{name}' is disabled for worker agents. Leave your changes uncommitted in "
                "the working tree; the Lead Brain reviews, commits and pushes."
            )
        try:
            from tools import (
                execute_run_command,
                execute_check_syntax,
                execute_git_status,
                execute_git_diff,
                execute_git_pull,
                execute_git_push,
                execute_git_commit,
                execute_git_add,
                execute_git_branch,
                execute_git_log,
                execute_read_file,
                execute_write_file,
                execute_replace_file_content,
                execute_create_file,
                execute_list_directory,
            )
        except ImportError:
            from multi_agent_coder.tools import (
                execute_run_command,
                execute_check_syntax,
                execute_git_status,
                execute_git_diff,
                execute_git_pull,
                execute_git_push,
                execute_git_commit,
                execute_git_add,
                execute_git_branch,
                execute_git_log,
                execute_read_file,
                execute_write_file,
                execute_replace_file_content,
                execute_create_file,
                execute_list_directory,
            )

        root = self.workspace_root
        dispatch = {
            "run_command": lambda inp: execute_run_command(inp, workspace_root=root),
            "check_syntax": lambda inp: execute_check_syntax(inp, workspace_root=root),
            "git_status": lambda inp: execute_git_status(inp, workspace_root=root),
            "git_diff": lambda inp: execute_git_diff(inp, workspace_root=root),
            "git_pull": lambda inp: execute_git_pull(inp, workspace_root=root),
            "git_push": lambda inp: execute_git_push(inp, workspace_root=root),
            "git_commit": lambda inp: execute_git_commit(inp, workspace_root=root),
            "git_add": lambda inp: execute_git_add(inp, workspace_root=root),
            "git_branch": lambda inp: execute_git_branch(inp, workspace_root=root),
            "git_log": lambda inp: execute_git_log(inp, workspace_root=root),
            # File tools are pinned to the target workspace: edits happen in place, never in a copy.
            "read_file": lambda inp: execute_read_file(None, inp, workspace_root=root),
            "write_file": lambda inp: execute_write_file(inp, workspace_root=root),
            "replace_file_content": lambda inp: execute_replace_file_content(inp, workspace_root=root),
            "create_file": lambda inp: execute_create_file(inp, workspace_root=root),
            "list_directory": lambda inp: execute_list_directory(None, inp, workspace_root=root),
        }
        handler = dispatch.get(name)
        if not handler:
            return f"Unknown tool: {name}"
        try:
            return str(handler(args))
        except Exception as exc:
            return f"Error executing {name}: {exc}"

    def _generate(
        self,
        messages: list[Any],
        system_instruction: str,
        worker_tools: list[dict[str, Any]],
        ticket: Ticket,
    ) -> Any:
        """One LLM call with budget enforcement, transient-error retry, and usage accounting."""
        for attempt in range(1, LLM_ATTEMPTS + 1):
            if self.token_budget:
                self.token_budget.check()
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=worker_tools,
                    ),
                )
            except Exception as exc:
                if attempt < LLM_ATTEMPTS and _is_transient(exc):
                    delay = LLM_RETRY_BASE_DELAY * attempt
                    logger.warning("Agent [%s] transient LLM error (%s); retry %d/%d in %.1fs",
                                   self.agent_id, type(exc).__name__, attempt, LLM_ATTEMPTS - 1, delay)
                    time.sleep(delay)
                    continue
                raise AgentFailure("LLM_ERROR", f"{type(exc).__name__}: {exc}") from exc

            self._account_usage(response, ticket)
            return response
        raise AgentFailure("LLM_ERROR", "LLM call failed after retries.")  # pragma: no cover

    def _account_usage(self, response: Any, ticket: Ticket) -> None:
        prompt, completion, total = usage_from_response(response)
        if not total:
            return
        ticket.tokens_used += total
        self.tokens_used += total
        run_total = total
        if self.token_budget:
            self.token_budget.record(total)
            run_total = self.token_budget.used
        if self.run_logger:
            self.run_logger.llm_usage(self.agent_id, ticket.id, prompt, completion, total, run_total)

    def execute_ticket_task(self, ticket: Ticket) -> str:
        """
        Execute the ticket task using Gemini with tool access (cmd, git, files)
        guided by cognitive prompt scaffolding.

        Returns the agent's final report on success. Raises ``AgentFailure`` (with a stable
        ``code``) or ``TokenBudgetExceeded`` when the ticket cannot be completed, so the
        ticket is recorded as FAILED instead of being reported as resolved.
        """
        prompt = build_ticket_execution_prompt(
            ticket=ticket,
            workspace_root=self.workspace_root,
            agent_id=self.agent_id,
            role=self.role,
            specialty=self.specialty,
        )

        # In offline/mock test environments
        if not self.api_key or self.api_key.startswith("dummy"):
            return (
                f"[{self.agent_id} Resolution]: Addressed '{ticket.title}' successfully. "
                f"Specialty '{self.specialty}' applied."
            )

        worker_tools = self._build_worker_tools()
        system_instruction = build_worker_system_instruction(
            agent_id=self.agent_id,
            role=self.role,
            specialty=self.specialty,
            workspace_root=self.workspace_root,
        )

        messages = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        max_iterations = _max_iterations()
        guard = ExecutionGuard(max_tokens=10**12, max_identical_calls=IDENTICAL_CALL_LIMIT)
        pseudo_call_strikes = 0

        for _ in range(max_iterations):
            response = self._generate(messages, system_instruction, worker_tools, ticket)
            if not response.candidates or not response.candidates[0].content:
                raise AgentFailure("EMPTY_RESPONSE", "Model returned no content (possibly blocked).")

            assistant_content = response.candidates[0].content
            messages.append(assistant_content)

            parts = assistant_content.parts or []
            function_calls = [p.function_call for p in parts if p.function_call]
            if not function_calls:
                text = "\n".join(p.text for p in parts if p.text).strip()

                # Flash-lite sometimes prints a tool call as text instead of calling it.
                if _PSEUDO_CALL_RE.search(text) and "[Agent Status: RESOLVED]" not in text:
                    pseudo_call_strikes += 1
                    if pseudo_call_strikes > 2:
                        raise AgentFailure(
                            "PSEUDO_TOOL_CALL",
                            "Agent kept writing tool calls as text instead of invoking tools.",
                        )
                    messages.append(
                        types.Content(role="user", parts=[types.Part(text=_PSEUDO_CALL_CORRECTION)])
                    )
                    continue

                if ticket.tool_calls == 0:
                    raise AgentFailure(
                        "NO_TOOL_ACTIVITY",
                        "Agent produced a final answer without calling any tool, so no work was done.",
                    )
                return text if text else f"[{self.agent_id} Completed]: Done."

            tool_responses = []
            for fc in function_calls:
                call_args = fc.args if fc.args is not None else {}
                ticket.tool_calls += 1
                detail = _describe_call(fc.name, call_args)
                logger.info("Agent [%s] calling tool %s%s", self.agent_id, fc.name,
                            f" ({detail})" if detail else "")
                if self.run_logger:
                    self.run_logger.tool_call(self.agent_id, ticket.id, fc.name, detail)

                if fc.name not in LOOP_EXEMPT_TOOLS:
                    try:
                        guard.record_tool_call(fc.name, dict(call_args))
                    except InfiniteLoopError as exc:
                        raise AgentFailure("LOOP_DETECTED", str(exc)) from exc

                res = self._execute_tool(fc.name, call_args)
                if fc.name in MUTATING_TOOLS and str(res).startswith("Successfully"):
                    guard.reset_call_counts()
                tool_responses.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": str(res)},
                        )
                    )
                )
            messages.append(types.Content(role="user", parts=tool_responses))

        raise AgentFailure(
            "ITERATION_LIMIT",
            f"Reached {max_iterations} tool iterations without a final report "
            "(raise MAX_WORKER_ITERATIONS or split the ticket into smaller tickets).",
        )

    def process_next_ticket(self, callback: Callable[[Ticket], None] | None = None) -> Ticket | None:
        """
        Process the next ticket from the queue strictly synchronously.
        Pops the head of the queue, executes it, marks it resolved, and archives it.
        """
        if not self.queue:
            return None

        ticket = self.queue.pop(0)
        self.current_ticket = ticket
        ticket.mark_in_progress()

        if callback:
            callback(ticket)

        logger.info("Agent [%s] STARTED ticket [%s]: %s", self.agent_id, ticket.id, ticket.title)
        if self.run_logger:
            self.run_logger.ticket_started(ticket, self.agent_id)

        try:
            result = self.execute_ticket_task(ticket)
            ticket.mark_resolved(result)
            logger.info("Agent [%s] RESOLVED ticket [%s] in %.2fs", self.agent_id, ticket.id, ticket.duration_seconds)
            if self.run_logger:
                self.run_logger.ticket_completed(ticket, self.agent_id)
        except TokenBudgetExceeded as e:
            self._record_failure(ticket, str(e), "TOKEN_BUDGET_EXHAUSTED")
        except AgentFailure as e:
            self._record_failure(ticket, str(e), e.code)
        except Exception as e:
            self._record_failure(ticket, f"{type(e).__name__}: {e}", "AGENT_ERROR")

        self.history.append(ticket)
        self.current_ticket = None

        if callback:
            callback(ticket)

        return ticket

    def _record_failure(self, ticket: Ticket, message: str, code: str) -> None:
        ticket.mark_failed(message, code)
        logger.error("Agent [%s] FAILED ticket [%s] (%s): %s",
                     self.agent_id, ticket.id, code, repr(message))
        if self.run_logger:
            self.run_logger.ticket_failed(ticket, self.agent_id)

    def process_all_synchronously(self, callback: Callable[[Ticket], None] | None = None) -> list[Ticket]:
        """Process all queued tickets strictly one by one (synchronously)."""
        resolved: list[Ticket] = []
        while self.queue:
            ticket = self.process_next_ticket(callback=callback)
            if ticket:
                resolved.append(ticket)
        return resolved

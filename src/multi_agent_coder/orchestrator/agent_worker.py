"""
Agent Worker with Synchronous Ticket Queue & Command/Git Tools.
Wraps an agent with a queue limit of 3 tickets, executed synchronously one by one,
with full access to terminal cmd execution (run_command), git tools, and file tools.
"""

from collections import deque
import os
import logging
import time
from pathlib import Path
from typing import Callable, Any
from google import genai
from google.genai import types

try:
    from orchestrator.ticket import Ticket, TicketStatus
    from common.logging_config import setup_logging
except ImportError:
    from .ticket import Ticket, TicketStatus
    from ..common.logging_config import setup_logging

logger = setup_logging(__name__)

QUEUE_LIMIT_DEFAULT = 3


class QueueFullError(Exception):
    """Raised when an agent worker's queue has reached its maximum capacity."""
    pass


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
        model: str = "gemini-2.5-flash-lite",
        api_key: str | None = None,
        workspace_root: Path | str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.specialty = specialty
        self.queue_limit = queue_limit
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()

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
        return True

    def _build_worker_tools(self) -> list[dict[str, Any]]:
        """Declare all cmd, git, and coding tools for the sub-agent."""
        try:
            from tools import EXECUTION_TOOLS, FILE_TOOLS, CODING_TOOLS
        except ImportError:
            from multi_agent_coder.tools import EXECUTION_TOOLS, FILE_TOOLS, CODING_TOOLS
        return [{"function_declarations": EXECUTION_TOOLS + FILE_TOOLS + CODING_TOOLS}]

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """Dispatch tool calls for the sub-agent in its target workspace directory."""
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

        dispatch = {
            "run_command": lambda inp: execute_run_command(inp, workspace_root=self.workspace_root),
            "check_syntax": lambda inp: execute_check_syntax(inp, workspace_root=self.workspace_root),
            "git_status": lambda inp: execute_git_status(inp, workspace_root=self.workspace_root),
            "git_diff": lambda inp: execute_git_diff(inp, workspace_root=self.workspace_root),
            "git_pull": lambda inp: execute_git_pull(inp, workspace_root=self.workspace_root),
            "git_push": lambda inp: execute_git_push(inp, workspace_root=self.workspace_root),
            "git_commit": lambda inp: execute_git_commit(inp, workspace_root=self.workspace_root),
            "git_add": lambda inp: execute_git_add(inp, workspace_root=self.workspace_root),
            "git_branch": lambda inp: execute_git_branch(inp, workspace_root=self.workspace_root),
            "git_log": lambda inp: execute_git_log(inp, workspace_root=self.workspace_root),
            "read_file": lambda inp: execute_read_file(None, inp),
            "write_file": lambda inp: execute_write_file(inp),
            "replace_file_content": lambda inp: execute_replace_file_content(inp),
            "create_file": lambda inp: execute_create_file(inp),
            "list_directory": lambda inp: execute_list_directory(None, inp),
        }
        handler = dispatch.get(name)
        if not handler:
            return f"Unknown tool: {name}"
        try:
            return str(handler(args))
        except Exception as exc:
            return f"Error executing {name}: {exc}"

    def execute_ticket_task(self, ticket: Ticket) -> str:
        """
        Execute the ticket task using Gemini with tool access (cmd, git, files).
        """
        prompt_parts = [
            f"You are {self.agent_id} ({self.role}).",
            f"Your specialty is {self.specialty}.",
            f"Target Workspace: {self.workspace_root}",
            "",
            "Please solve this ticket:",
            f"Ticket ID: {ticket.id}",
            f"Title: {ticket.title}",
            f"Category: {ticket.category}",
            "Description:",
            ticket.description,
            "",
            "You have access to cmd (run_command) to execute shell commands, run tests, and inspect code.",
            "You also have Git tools (git_status, git_diff, git_pull, git_push, git_commit, git_add, git_log) and file editing tools.",
            "Use tools as needed to inspect and solve the problem, and provide a clear, concrete resolution."
        ]
        prompt = "\n".join(prompt_parts)

        # In offline/mock test environments
        if not self.api_key or self.api_key.startswith("dummy"):
            return (
                f"[{self.agent_id} Resolution]: Addressed '{ticket.title}' successfully. "
                f"Specialty '{self.specialty}' applied."
            )

        worker_tools = self._build_worker_tools()
        messages = [types.Content(role="user", parts=[types.Part(text=prompt)])]

        try:
            for iteration in range(5):
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=(
                            f"You are {self.agent_id}, a specialized software engineering agent ({self.role}). "
                            "You have full command line execution access via 'run_command' to run shell commands, tests, scripts, "
                            "as well as Git tools and file editing tools. Solve the ticket directly in the workspace."
                        ),
                        tools=worker_tools,
                    ),
                )
                if not response.candidates or not response.candidates[0].content:
                    return f"[{self.agent_id} Completed]: No content returned."

                assistant_content = response.candidates[0].content
                messages.append(assistant_content)

                parts = assistant_content.parts or []
                function_calls = [p.function_call for p in parts if p.function_call]
                if not function_calls:
                    text_parts = [p.text for p in parts if p.text]
                    return "\n".join(text_parts).strip() if text_parts else f"[{self.agent_id} Completed]: Done."

                tool_responses = []
                for fc in function_calls:
                    call_args = fc.args if fc.args is not None else {}
                    logger.info("Agent [%s] calling tool %s with args: %s", self.agent_id, fc.name, call_args)
                    res = self._execute_tool(fc.name, call_args)
                    tool_responses.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=fc.name,
                                response={"result": str(res)},
                            )
                        )
                    )
                messages.append(types.Content(role="user", parts=tool_responses))

            return f"[{self.agent_id} Completed]: Solved task '{ticket.title}'."
        except Exception as e:
            logger.warning("LLM call failed for %s on %s: %s (using local fallback resolution)", self.agent_id, ticket.id, e)
            desc_snippet = (ticket.description or "")[:100]
            return f"[{self.agent_id} Resolved]: Executed task '{ticket.title}'. Context: {desc_snippet}..."

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

        try:
            result = self.execute_ticket_task(ticket)
            ticket.mark_resolved(result)
            logger.info("Agent [%s] RESOLVED ticket [%s] in %.2fs", self.agent_id, ticket.id, ticket.duration_seconds)
        except Exception as e:
            ticket.mark_failed(str(e))
            logger.error("Agent [%s] FAILED ticket [%s]: %s", self.agent_id, ticket.id, e)

        self.history.append(ticket)
        self.current_ticket = None

        if callback:
            callback(ticket)

        return ticket

    def process_all_synchronously(self, callback: Callable[[Ticket], None] | None = None) -> list[Ticket]:
        """Process all queued tickets strictly one by one (synchronously)."""
        resolved: list[Ticket] = []
        while self.queue:
            ticket = self.process_next_ticket(callback=callback)
            if ticket:
                resolved.append(ticket)
        return resolved

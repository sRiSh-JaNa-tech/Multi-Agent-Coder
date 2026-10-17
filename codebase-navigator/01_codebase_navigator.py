"""
Augmented LLM — Codebase Navigator (Anthropic)

Demonstrates the "Augmented LLM" pattern: an LLM enhanced with retrieval (RAG),
tools, and memory. This is the foundational building block of all agentic systems,
as described in Anthropic's "Building Effective Agents" guide.

The Codebase Navigator helps engineers explore and understand unfamiliar codebases.
Point it at any GitHub repo, and it will clone, index, and answer questions using
semantic search — while maintaining memory across sessions.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Any
from google import genai
from google.genai import types
from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from common import GeminiTokenTracker, setup_logging
from common.auth import ensure_api_key, validate_gemini_api_key, ensure_api_key, validate_gemini_api_key
from common.menu import interactive_menu
from common.ui import ConsoleUI

# Load environment variables
load_dotenv(find_dotenv())

logger = setup_logging(__name__)

MODEL = "gemini-2.5-flash-lite"

# Path to the cumulative token usage log
_TOKEN_CSV = Path(__file__).parent.parent / "logs" / "token_usage.csv"

SUGGESTED_REPOS = [
    "openai/swarm",
    "strands-agents/sdk-python",
    "anthropics/anthropic-sdk-python",
    "pallets/flask",
]


SYSTEM_PROMPT = """You are an advanced Codebase Navigator & Coding Agent — an AI assistant that \
helps software engineers explore, understand, modify, and test codebases.

## Your Capabilities

### 1. Navigation & Structural Inspection
- Cloning and indexing repositories: clone_and_index
- Listing indexed repositories: list_repos
- Semantic search across code: search_code
- Outline symbols & classes: get_file_outline
- Reading full file contents with line numbers: read_file
- Exploring directory structure: list_directory
- Finding exact regex patterns: grep

### 2. Code Modification & Implementation
- Creating new files: create_file
- Writing/overwriting files: write_file
- Surgical unique block replacement: replace_file_content

### 3. Git Operations & Repository Control
- Pulling latest remote changes: git_pull
- Pushing commits to remote: git_push
- Staging and creating commits: git_commit, git_add
- Branch listing and switching: git_branch
- Commit log history: git_log
- Inspecting git diff: git_diff
- Inspecting git status: git_status

### 4. Verification & Terminal Execution
- Validating Python/JSON syntax: check_syntax
- Running shell commands, tests & scripts: run_command

### 4. Memory
- Saving architectural patterns & preferences: save_memory
- Recalling stored context: recall_memory

## Workflow Rules
- Explore first before editing: use search_code, get_file_outline, or read_file to inspect code context.
- Keep changes surgical: use replace_file_content whenever possible.
- Always verify changes: run check_syntax and run_command (tests/linting) after modifying files.

## Response Style
- Be concise but thorough
- Show relevant code snippets with file paths and line numbers
- Explain architectural decisions when you discover them
- Suggest related areas to explore"""


# -- Tool registry ----------------------------------------------------------


def _build_tool_definitions() -> list[dict[str, Any]]:
    """Collect all tool definitions from tool modules."""
    try:
        from tools import (
            FILE_TOOLS,
            MEMORY_TOOLS,
            REPO_TOOLS,
            SEARCH_TOOLS,
            CODING_TOOLS,
            EXECUTION_TOOLS,
            OUTLINE_TOOLS,
            GIT_TOOLS,
        )
    except ImportError:
        from multi_agent_coder.tools import (
            FILE_TOOLS,
            MEMORY_TOOLS,
            REPO_TOOLS,
            SEARCH_TOOLS,
            CODING_TOOLS,
            EXECUTION_TOOLS,
            OUTLINE_TOOLS,
            GIT_TOOLS,
        )

    all_tools = (
        MEMORY_TOOLS
        + REPO_TOOLS
        + FILE_TOOLS
        + SEARCH_TOOLS
        + CODING_TOOLS
        + EXECUTION_TOOLS
        + OUTLINE_TOOLS
    )
    return [{"function_declarations": all_tools}]


def get_max_agents() -> int:
    """Read the maximum active agents limit from .env (defaults to 3)."""
    val = os.getenv("MAX_AGENTS", os.getenv("MAX_ACTIVE_AGENTS", "3")).strip()
    try:
        return max(1, int(val))
    except ValueError:
        return 3


class CodeNavigatorAgent:
    """
    An LLM augmented with retrieval, tools, coding capabilities, and memory.

    Implements the agentic loop: send message -> execute tools -> send results -> repeat
    until the LLM responds with just text.
    """
    _active_instances: set = set()

    def __init__(
        self,
        model: str = MODEL,
        console: Console | None = None,
        api_key: str | None = None,
        workspace_root: Path | str | None = None,
    ) -> None:
        max_agents = get_max_agents()
        if len(CodeNavigatorAgent._active_instances) >= max_agents:
            msg = (
                f"Agent launch limit exceeded: {len(CodeNavigatorAgent._active_instances)}/{max_agents} active agents. "
                "Adjust MAX_AGENTS in .env to allow more concurrent agents."
            )
            logger.error(msg)
            if console:
                console.print(f"[bold red]{msg}[/bold red]")
            raise RuntimeError(msg)

        self.console = console or Console()
        self.ui = ConsoleUI(console=self.console)
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()
        self.api_key = api_key or ensure_api_key(self.console)
        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.token_tracker = GeminiTokenTracker(csv_path=_TOKEN_CSV, model=model)
        self.tools = _build_tool_definitions()
        self.messages: list[types.Content] = []
        self.max_iterations = 20

        # Initialize shared components (the three augmentations)
        from indexer.embedder import Embedder
        from store.memory import MemoryStore
        from store.vector import VectorStore

        self.memory = MemoryStore()
        self.vector_store = VectorStore()
        self.embedder = Embedder(api_key=self.api_key)

        # Register instance only after full successful initialization
        CodeNavigatorAgent._active_instances.add(self)

    def close(self) -> None:
        """Release agent instance from active tracking."""
        CodeNavigatorAgent._active_instances.discard(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        CodeNavigatorAgent._active_instances.discard(self)

    def _build_system_prompt(self) -> str:
        """Build system prompt with memory context."""
        memory_summary = self.memory.summary()
        if memory_summary and memory_summary != "No memories stored yet.":
            return SYSTEM_PROMPT + f"\n\n## Recalled Memories\n{memory_summary}"
        return SYSTEM_PROMPT

    def _execute_tool(self, name: str, tool_input: dict[str, Any]) -> str:
        """Dispatch a tool call to the appropriate handler."""
        try:
            from tools import (
                execute_list_directory,
                execute_read_file,
                execute_recall_memory,
                execute_save_memory,
                execute_clone_and_index,
                execute_list_repos,
                execute_grep,
                execute_search_code,
                execute_create_file,
                execute_write_file,
                execute_replace_file_content,
                execute_run_command,
                execute_git_diff,
                execute_git_status,
                execute_git_pull,
                execute_git_push,
                execute_git_commit,
                execute_git_add,
                execute_git_branch,
                execute_git_log,
                execute_check_syntax,
                execute_get_file_outline,
            )
        except ImportError:
            from multi_agent_coder.tools import (
                execute_list_directory,
                execute_read_file,
                execute_recall_memory,
                execute_save_memory,
                execute_clone_and_index,
                execute_list_repos,
                execute_grep,
                execute_search_code,
                execute_create_file,
                execute_write_file,
                execute_replace_file_content,
                execute_run_command,
                execute_git_diff,
                execute_git_status,
                execute_git_pull,
                execute_git_push,
                execute_git_commit,
                execute_git_add,
                execute_git_branch,
                execute_git_log,
                execute_check_syntax,
                execute_get_file_outline,
            )

        ws = getattr(self, "workspace_root", Path.cwd())

        dispatch: dict[str, Any] = {
            "save_memory": lambda inp: execute_save_memory(self.memory, inp),
            "recall_memory": lambda inp: execute_recall_memory(self.memory, inp),
            "clone_and_index": lambda inp: execute_clone_and_index(
                self.vector_store, self.embedder, inp
            ),
            "list_repos": lambda inp: execute_list_repos(self.vector_store, inp),
            "read_file": lambda inp: execute_read_file(self.vector_store, inp),
            "list_directory": lambda inp: execute_list_directory(self.vector_store, inp),
            "search_code": lambda inp: execute_search_code(self.vector_store, self.embedder, inp),
            "grep": lambda inp: execute_grep(self.vector_store, self.embedder, inp),
            "create_file": lambda inp: execute_create_file(inp),
            "write_file": lambda inp: execute_write_file(inp),
            "replace_file_content": lambda inp: execute_replace_file_content(inp),
            "run_command": lambda inp: execute_run_command(inp, workspace_root=ws),
            "git_diff": lambda inp: execute_git_diff(inp, workspace_root=ws),
            "git_status": lambda inp: execute_git_status(inp, workspace_root=ws),
            "git_pull": lambda inp: execute_git_pull(inp, workspace_root=ws),
            "git_push": lambda inp: execute_git_push(inp, workspace_root=ws),
            "git_commit": lambda inp: execute_git_commit(inp, workspace_root=ws),
            "git_add": lambda inp: execute_git_add(inp, workspace_root=ws),
            "git_branch": lambda inp: execute_git_branch(inp, workspace_root=ws),
            "git_log": lambda inp: execute_git_log(inp, workspace_root=ws),
            "check_syntax": lambda inp: execute_check_syntax(inp, workspace_root=ws),
            "get_file_outline": lambda inp: execute_get_file_outline(inp),
        }

        handler = dispatch.get(name)
        if not handler:
            return f"Unknown tool: {name}"

        try:
            return str(handler(tool_input))
        except Exception as e:
            logger.error("Tool '%s' failed: %s", name, e)
            return f"Error executing {name}: {e}"

    def chat(self, user_message: str, console: Console) -> str:
        """Send a message and handle the agentic tool-use loop."""
        self.messages.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        for _iteration in range(self.max_iterations):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=self.messages,
                    config=types.GenerateContentConfig(
                        system_instruction=self._build_system_prompt(),
                        tools=self.tools,
                    ),
                )
            except Exception as e:
                err_str = str(e)
                auth_indicators = [
                    "API_KEY_INVALID",
                    "API key not valid",
                    "UNAUTHENTICATED",
                    "ACCESS_TOKEN_TYPE_UNSUPPORTED",
                    "401",
                    "403",
                    "invalid authentication",
                ]
                if any(k in err_str for k in auth_indicators):
                    logger.error("Gemini authentication failure: %s", e)
                    new_key = ensure_api_key(console, force_prompt=True)
                    self.api_key = new_key
                    self.client = genai.Client(api_key=new_key)
                    continue
                logger.error("Gemini API error: %s", e)
                return f"API error: {e}"

            self.token_tracker.track(response.usage_metadata, demo_name="Codebase Navigator")

            if not response.candidates or not response.candidates[0].content:
                logger.warning("Empty response received from Gemini.")
                return "Received empty response from model."

            # Add assistant's response to history
            assistant_content = response.candidates[0].content
            self.messages.append(assistant_content)

            parts = assistant_content.parts or []
            # Check for function calls
            function_calls = [p.function_call for p in parts if p.function_call]
            
            if not function_calls:
                # If no function calls, return the text response
                text_parts = [p.text for p in parts if p.text]
                return "\n".join(text_parts) if text_parts else "Done."

            # Execute each tool and print progress using ConsoleUI
            tool_responses = []
            for fc in function_calls:
                call_args = fc.args if fc.args is not None else {}
                self.ui.display_tool_call(fc.name, call_args)

                result = self._execute_tool(fc.name, call_args)

                self.ui.display_tool_result(fc.name, result)

                tool_responses.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": result}
                        )
                    )
                )

            # Add tool results to history
            self.messages.append(types.Content(role="user", parts=tool_responses))

        return "Reached maximum iterations. Please try a more specific question."


# -- Main -------------------------------------------------------------------


def main() -> None:
    """Main orchestration function."""
    import argparse
    parser = argparse.ArgumentParser(description="Codebase Navigator Agent")
    parser.add_argument("-p", "--prompt", type=str, help="Single prompt to execute directly")
    parser.add_argument("-r", "--repo", type=str, help="Repository or directory to explore (e.g. '.' or 'pallets/flask')")
    parser.add_argument("-d", "--dir", type=str, help="Target directory to open and work in (default: '.')")
    cli_args, _ = parser.parse_known_args()

    console = Console()
    ui = ConsoleUI(console=console)
    api_key = ensure_api_key(console)

    # 1. Direct one-shot prompt execution
    if cli_args.prompt:
        target = cli_args.dir or cli_args.repo or "."
        target_path = Path(target).expanduser().resolve()
        display_target = str(target_path) if target_path.is_dir() else target
        agent = CodeNavigatorAgent(model=MODEL, console=console, api_key=api_key, workspace_root=target_path if target_path.is_dir() else None)
        ui.display_app_banner(repo=display_target)
        console.print(f"[bold green]User Prompt:[/bold green] {cli_args.prompt}\n")
        response = agent.chat(cli_args.prompt, console)
        if response:
            ui.display_agent_response("Navigator", response)
        agent.token_tracker.report()
        return

    # 2. Interactive Directory Selection (Defaults to current directory '.')
    ui.display_app_banner()

    target = cli_args.dir or cli_args.repo
    if not target:
        cwd_display = str(Path.cwd())
        console.print(f"[bold cyan]Target Workspace Directory[/bold cyan] [dim](Press Enter for current directory '.', or enter custom path/repo)[/dim]: ", end="")
        try:
            user_choice = input().strip()
            target = user_choice if user_choice else "."
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Exiting.[/yellow]")
            return

    target_path = Path(target).expanduser().resolve()
    if target_path.is_dir():
        display_target = str(target_path)
        workspace_root = target_path
    else:
        display_target = target
        workspace_root = None

    agent = CodeNavigatorAgent(model=MODEL, console=console, api_key=api_key, workspace_root=workspace_root)
    ui.display_app_banner(repo=display_target)
    console.print(f"\n[bold green]Opening and indexing:[/bold green] {display_target}")
    response = agent.chat(f"index the repo {target}", console)
    if response:
        ui.display_agent_response("Navigator", response)

    console.print("\n[dim]Ask questions about the codebase. Type 'quit' to exit.[/dim]")

    try:
        while True:
            console.print("\n[bold green]You:[/bold green] ", end="")
            try:
                user_input = input().strip()
            except EOFError:
                break

            if user_input.lower() in ("exit", "quit", "q", ""):
                console.print("\n[yellow]Ending session...[/yellow]")
                break

            response = agent.chat(user_input, console)

            if response:
                ui.display_agent_response("Navigator", response)

            agent.token_tracker.report()

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")

    console.print("\n[bold]Session Summary:[/bold]")
    agent.token_tracker.report()

if __name__ == '__main__':
    main()

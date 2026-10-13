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

### 3. Verification & Execution
- Validating Python/JSON syntax: check_syntax
- Running terminal commands & tests: run_command
- Inspecting git diff: git_diff
- Inspecting git status: git_status

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
    from tools import (
        FILE_TOOLS,
        MEMORY_TOOLS,
        REPO_TOOLS,
        SEARCH_TOOLS,
        CODING_TOOLS,
        EXECUTION_TOOLS,
        OUTLINE_TOOLS,
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


def ensure_api_key(console: Console | None = None) -> str:
    """Ensure GEMINI_API_KEY is available in environment or prompt the user."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        return api_key

    _console = console or Console()
    _console.print(
        Panel(
            "[bold yellow]GEMINI_API_KEY not found in environment or .env[/bold yellow]\n\n"
            "Please enter your Google Gemini API key to proceed.",
            title="API Key Required",
            border_style="yellow",
        )
    )

    while True:
        try:
            if sys.stdin.isatty():
                entered_key = Prompt.ask("[bold green]Enter your GEMINI_API_KEY[/bold green]", password=True).strip()
            else:
                _console.print("[bold green]Enter your GEMINI_API_KEY:[/bold green] ", end="")
                entered_key = sys.stdin.readline().strip()

            if entered_key:
                os.environ["GEMINI_API_KEY"] = entered_key
                
                # Persist to .env in current folder if available
                env_file = Path(".env")
                try:
                    if not env_file.exists():
                        env_file.write_text(f"GEMINI_API_KEY={entered_key}\n", encoding="utf-8")
                    else:
                        cur = env_file.read_text(encoding="utf-8")
                        if "GEMINI_API_KEY" not in cur:
                            with env_file.open("a", encoding="utf-8") as ef:
                                ef.write(f"\nGEMINI_API_KEY={entered_key}\n")
                except Exception:
                    pass

                _console.print("[green]API key set successfully![/green]\n")
                return entered_key
            _console.print("[red]API key cannot be empty. Please enter a valid key.[/red]")
        except (KeyboardInterrupt, EOFError):
            _console.print("\n[yellow]Exiting: API key entry cancelled.[/yellow]")
            raise SystemExit(0)


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

    def __init__(self, model: str = MODEL, console: Console | None = None, api_key: str | None = None) -> None:
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
            execute_check_syntax,
            execute_get_file_outline,
        )

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
            "run_command": lambda inp: execute_run_command(inp),
            "git_diff": lambda inp: execute_git_diff(inp),
            "git_status": lambda inp: execute_git_status(inp),
            "check_syntax": lambda inp: execute_check_syntax(inp),
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
    console = Console()
    ui = ConsoleUI(console=console)
    api_key = ensure_api_key(console)
    agent = CodeNavigatorAgent(model=MODEL, console=console, api_key=api_key)

    ui.display_app_banner()

    repo = interactive_menu(
        console,
        SUGGESTED_REPOS,
        title="Select a Repo to Explore",
        allow_custom=True,
        custom_prompt="Enter owner/repo (e.g., pallets/flask)",
    )
    if not repo:
        return

    ui.display_app_banner(repo=repo)
    console.print(f"\n[bold green]Indexing:[/bold green] {repo}")
    response = agent.chat(f"index the repo {repo}", console)
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

    console.print()
    agent.token_tracker.report()


if __name__ == "__main__":
    main()

"""
Interactive LLM Harness Demonstration.
Demonstrates attaching different LLMs (Mock, Callable, Gemini) to codebase tools
and executing multi-agent tickets synchronously without modifying the main API agent.
"""

import argparse
import sys
from pathlib import Path

# Add current directory to sys.path so imports work seamlessly
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..harness import (
    CallableAdapter,
    GeminiAdapter,
    HarnessAgent,
    HarnessTicketWorker,
    LLMResponse,
    Message,
    MockLLMAdapter,
    ToolCall,
)
from ..orchestrator.ticket import Ticket

console = Console()


def demo_mock_adapter():
    """Demo 1: Attach MockLLMAdapter for instant offline tool calling."""
    console.print(Panel.fit(
        "[bold cyan]Demo 1: Mock LLM Adapter (Offline, 0-Cost, Scripted Tool Calling)[/bold cyan]",
        border_style="cyan"
    ))

    # Script a two-turn conversation:
    # 1. First turn: LLM decides to call `list_dir`
    # 2. Second turn: LLM reads the tool output and provides a final answer
    mock_adapter = MockLLMAdapter(
        responses=[
            {
                "text": "I will examine the files in the repository directory first.",
                "tool_calls": [
                    {"name": "list_dir", "args": {"dir_path": "."}}
                ]
            },
            "Based on list_dir, the repository contains the codebase-navigator, tools, and orchestrator modules."
        ],
        model_name="mock-scripted-fast",
    )

    console.print(f"[bold]Attached Adapter:[/bold] {mock_adapter}\n")

    agent = HarnessAgent.with_codebase_tools(
        adapter=mock_adapter,
        console=console,
        max_iterations=5,
    )

    prompt = "What files exist in the current working directory?"
    console.print(f"[bold green]User Prompt:[/bold green] {prompt}\n")

    result = agent.run(prompt)

    table = Table(title="Execution Summary", border_style="blue")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Success", str(result.success))
    table.add_row("Iterations", str(result.iterations))
    table.add_row("Tools Invoked", ", ".join(result.tools_invoked))
    table.add_row("Tokens Consumed", str(result.total_usage.total_tokens))
    table.add_row("Final Answer", result.final_answer)
    console.print(table)


def demo_callable_adapter():
    """Demo 2: Attach an arbitrary Python function as the LLM."""
    console.print(Panel.fit(
        "[bold magenta]Demo 2: Custom Callable Adapter (Attach Any Python Function)[/bold magenta]",
        border_style="magenta"
    ))

    def my_custom_llm_logic(messages: list[Message], tools: list | None, system_instruction: str | None = None) -> LLMResponse:
        last_msg = messages[-1]
        # If tool results are received, formulate conclusion
        if last_msg.role == "tool":
            return LLMResponse(
                text=f"Custom Callable observed tool output ({len(last_msg.tool_results)} results). Execution verified!"
            )
        # Otherwise, ask to inspect pyproject.toml
        return LLMResponse(
            text="Deciding to read pyproject.toml using custom logic...",
            tool_calls=[ToolCall(name="read_file", args={"file_path": "pyproject.toml"})]
        )

    callable_adapter = CallableAdapter(fn=my_custom_llm_logic, model_name="python-fn-v1")
    console.print(f"[bold]Attached Adapter:[/bold] {callable_adapter}\n")

    agent = HarnessAgent.with_codebase_tools(
        adapter=callable_adapter,
        console=console,
        max_iterations=5,
    )

    prompt = "Inspect the project configuration file."
    console.print(f"[bold green]User Prompt:[/bold green] {prompt}\n")
    result = agent.run(prompt)

    console.print(Panel(f"[bold green]Final Result:[/bold green] {result.final_answer}", border_style="green"))


def demo_gemini_adapter():
    """Demo 3: Attach real Gemini Live LLM adapter."""
    console.print(Panel.fit(
        "[bold yellow]Demo 3: Gemini Live API Adapter (gemini-2.5-flash-lite)[/bold yellow]",
        border_style="yellow"
    ))

    try:
        gemini_adapter = GeminiAdapter(model_name="gemini-2.5-flash-lite")
        console.print(f"[bold]Attached Adapter:[/bold] {gemini_adapter}\n")

        agent = HarnessAgent.with_codebase_tools(
            adapter=gemini_adapter,
            console=console,
            max_iterations=5,
        )

        prompt = "List the files in the tools directory and tell me what coding tools are available."
        console.print(f"[bold green]User Prompt:[/bold green] {prompt}\n")
        result = agent.run(prompt)

        console.print(Panel(f"[bold green]Final Gemini Response:[/bold green]\n{result.final_answer}", border_style="green"))
    except Exception as e:
        console.print(f"[bold red]Gemini Live Demo Skipped or Failed:[/bold red] {e}")


def demo_ticket_worker_with_harness():
    """Demo 4: Execute tickets using a harness-attached worker."""
    console.print(Panel.fit(
        "[bold green]Demo 4: Synchronous Multi-Agent Ticket Execution via Harness[/bold green]",
        border_style="green"
    ))

    # Use a mock adapter with scripted responses for 3 tickets
    mock_adapter = MockLLMAdapter(
        responses=[
            "Analyzed AST outline for tools/coding.py. All functions present.",
            "Ran test suite validation. 12/12 test cases passing.",
            "Codebase inspection complete. Architecture clean and decoupled.",
        ],
        model_name="mock-ticket-worker",
    )

    worker = HarnessTicketWorker(
        agent_id="Harness-Worker-1",
        role="Code Auditor",
        adapter=mock_adapter,
        specialty="Python Architecture",
        queue_limit=3,
        console=console,
    )

    t1 = Ticket.create(title="Audit AST Tools", description="Check AST outline generator", category="explore")
    t2 = Ticket.create(title="Verify Test Suite", description="Ensure test_ticket_system passes", category="testing")
    t3 = Ticket.create(title="Check Architecture", description="Verify harness decoupling", category="refactor")

    console.print("[bold]Enqueueing 3 tickets into worker (Queue Limit: 3)...[/bold]")
    worker.enqueue_ticket(t1)
    worker.enqueue_ticket(t2)
    worker.enqueue_ticket(t3)

    console.print(f"Worker queue size: {worker.queue_size}/3. Is full: {worker.is_full}")

    console.print("\n[bold]Executing tickets synchronously (one by one)...[/bold]\n")
    resolved_tickets = worker.run_all_tickets_sync()

    table = Table(title="Ticket Resolution Summary", border_style="green")
    table.add_column("Ticket ID", style="cyan")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Resolution")

    for t in resolved_tickets:
        table.add_row(t.id, t.title, t.status.value, t.result or "None")

    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="LLM Harness Demonstration")
    parser.add_argument("--mock", action="store_true", help="Run Mock Adapter Demo")
    parser.add_argument("--callable", action="store_true", help="Run Callable Adapter Demo")
    parser.add_argument("--gemini", action="store_true", help="Run Gemini Adapter Demo")
    parser.add_argument("--tickets", action="store_true", help="Run Ticket Worker Demo")
    parser.add_argument("--all", action="store_true", help="Run all non-interactive demos")
    args = parser.parse_args()

    if args.mock:
        demo_mock_adapter()
        return
    if args.callable:
        demo_callable_adapter()
        return
    if args.gemini:
        demo_gemini_adapter()
        return
    if args.tickets:
        demo_ticket_worker_with_harness()
        return
    if args.all:
        demo_mock_adapter()
        demo_callable_adapter()
        demo_ticket_worker_with_harness()
        return

    # Interactive Menu
    console.print(Panel.fit(
        "[bold cyan]Modular LLM Testing & Execution Harness[/bold cyan]\n"
        "[dim]Quickly attach any LLM (Gemini, Mock, Callable, OpenAI) without modifying the main agent API.[/dim]",
        border_style="cyan"
    ))

    console.print("1. [cyan]Mock LLM Adapter[/cyan] (Fast, offline, scripted ReAct tool-calling)")
    console.print("2. [magenta]Custom Callable Adapter[/magenta] (Attach any Python function)")
    console.print("3. [yellow]Gemini Live API Adapter[/yellow] (Live gemini-2.5-flash-lite)")
    console.print("4. [green]Ticket System with Attached LLM[/green] (Synchronous 3-queue limit)")
    console.print("5. [blue]Run All Offline Demos[/blue]")
    console.print("6. Exit")

    choice = input("\nSelect option (1-6): ").strip()
    if choice == "1":
        demo_mock_adapter()
    elif choice == "2":
        demo_callable_adapter()
    elif choice == "3":
        demo_gemini_adapter()
    elif choice == "4":
        demo_ticket_worker_with_harness()
    elif choice == "5":
        demo_mock_adapter()
        demo_callable_adapter()
        demo_ticket_worker_with_harness()
    else:
        console.print("[dim]Exiting harness demo.[/dim]")


if __name__ == "__main__":
    main()

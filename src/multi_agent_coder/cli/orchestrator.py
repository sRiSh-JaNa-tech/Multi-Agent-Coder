"""
Multi-Agent Ticket Orchestration CLI.
Provides interactive and headless execution modes for running multi-agent ticket pipelines.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.panel import Panel

from ..common.auth import ensure_api_key
from ..common.logging_config import setup_logging
from ..cli.ui.dashboard import TicketDashboard
from ..cli.ui.menu import interactive_menu
from ..orchestrator.main_orchestrator import MainOrchestrator
from ..orchestrator.ticket import TicketStatus

load_dotenv(find_dotenv())
logger = setup_logging(__name__)
console = Console()

SUGGESTED_PROBLEMS = [
    "Refactor caching layer to use LRU eviction, add hit/miss metrics, and verify with unit tests",
    "Audit codebase security vulnerabilities, add input sanitization guards, and generate security report",
    "Implement AST-based symbol outline tool, add error handling, and test with sample Python files",
    "Optimize embedding batch pipeline, add retry backoff strategy, and benchmark throughput",
]


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="multi-agent-coder orchestrator",
        description="Run the concurrent multi-agent ticket orchestrator.",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to a JSON manifest containing a pre-defined ticket DAG.",
    )
    parser.add_argument(
        "--objective",
        type=str,
        default=None,
        help="High-level objective string to decompose into tickets.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without interactive prompts or UI pauses (ideal for Antigravity / CI).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write the execution summary JSON.",
    )
    parser.add_argument(
        "--max-agents",
        type=int,
        default=None,
        help="Maximum number of parallel agents to launch (defaults to MAX_AGENTS from .env).",
    )
    parser.add_argument(
        "--queue-limit",
        type=int,
        default=None,
        help="Strict maximum tickets queued per agent (defaults to QUEUE_LIMIT_PER_AGENT from .env).",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Project directory the agents edit IN PLACE (defaults to TARGET_WORKSPACE from .env, then cwd). "
             "Never copy a project into the swarm repo.",
    )
    parser.add_argument(
        "--token-limit",
        type=str,
        default=None,
        help="Total token budget for the run: an integer, or 'none' for unlimited "
             "(defaults to TOKEN_USAGE_LIMIT from .env).",
    )
    return parser.parse_args(args)


def main(cli_args: list[str] | None = None) -> None:
    args = parse_args(cli_args)

    if args.headless:
        # In headless mode, read API key from environment directly
        api_key = os.getenv("GEMINI_API_KEY", "")
    else:
        api_key = ensure_api_key(console)

    extra = {}
    if args.token_limit is not None:
        extra["token_limit"] = args.token_limit
    try:
        orchestrator = MainOrchestrator(
            api_key=api_key,
            queue_limit_per_agent=args.queue_limit,
            max_agents=args.max_agents,
            workspace_root=args.workspace,
            **extra,
        )
    except ValueError as exc:  # ConfigError subclasses ValueError
        console.print(f"[bold red]Configuration error: {exc}[/bold red]")
        sys.exit(2)
    console.print(
        f"[dim]Workspace (edited in place): {orchestrator.workspace_root} | "
        f"model: {orchestrator.model} | run: {orchestrator.run_id}[/dim]"
    )
    dashboard = TicketDashboard(console=console)

    # 1. Determine problem source: manifest, CLI argument, or interactive menu
    manifest_tickets = None
    selected_problem = args.objective

    if args.manifest:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            console.print(f"[bold red]Error: Manifest file '{manifest_path}' not found.[/bold red]")
            sys.exit(1)
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        selected_problem = manifest_data.get("objective", f"Manifest: {manifest_path.name}")
        manifest_tickets = manifest_data

    elif not selected_problem:
        if args.headless:
            console.print("[bold red]Error: Must specify --manifest or --objective in --headless mode.[/bold red]")
            sys.exit(1)

        header = Panel(
            "[bold cyan]Multi-Agent Ticket Orchestration Hub[/bold cyan]\n\n"
            "1. The [bold yellow]Main Orchestrator[/bold yellow] starts all worker agents (up to MAX_AGENTS).\n"
            "2. Identifies sub-problems and raises discrete [bold green]Tickets[/bold green].\n"
            "3. Enforces a strict [bold magenta]Queue Limit of 3[/bold magenta] per agent.\n"
            "4. Agents process queued tickets [bold blue]synchronously one by one[/bold blue].",
            title="[bold green]Ticket Orchestration System[/bold green]",
            border_style="cyan",
        )

        selected_problem = interactive_menu(
            console,
            SUGGESTED_PROBLEMS,
            title="Select a Problem Statement or Enter Custom Objective",
            header=header,
            allow_custom=True,
            custom_prompt="Enter custom problem description",
        )

        if not selected_problem:
            console.print("[yellow]No problem selected. Exiting.[/yellow]")
            return

    if not args.headless:
        dashboard.render_header(selected_problem, orchestrator.max_agents, orchestrator.queue_limit_per_agent)

    # 2. Ingest tickets
    if manifest_tickets:
        if not args.headless:
            console.print(f"\n[bold yellow]Step 1: Loading manifest tickets from {args.manifest}...[/bold yellow]")
        tickets = orchestrator.load_manifest(manifest_tickets)
        if not args.headless:
            console.print(f"[green][OK] Loaded and validated {len(tickets)} DAG tickets.[/green]\n")
    else:
        if not args.headless:
            console.print("\n[bold yellow]Step 1: Main Orchestrator analyzing problem and raising tickets...[/bold yellow]")
        tickets = orchestrator.identify_problems_and_create_tickets(selected_problem)
        if not args.headless:
            console.print(f"[green][OK] Raised {len(tickets)} problem tickets.[/green]\n")

    # 3. Dispatch to agent queues
    if not args.headless:
        console.print("[bold yellow]Step 2: Dispatching tickets into agent queues (limit: 3 per agent)...[/bold yellow]")
    orchestrator.dispatch_all_pending()

    if not args.headless:
        dashboard.render_state(orchestrator.agents, orchestrator.all_tickets, orchestrator.pending_backlog)
        console.print("[bold yellow]Step 3: Agents executing tickets synchronously one by one...[/bold yellow]\n")

    def on_step(t):
        if not args.headless:
            dashboard.render_state(orchestrator.agents, orchestrator.all_tickets, orchestrator.pending_backlog)
            time.sleep(0.3)

    resolved = orchestrator.process_all_tickets_synchronously(on_step_callback=on_step)

    # 4. Final summary output
    summary = orchestrator.get_summary()
    summary["objective"] = selected_problem

    if not args.headless:
        dashboard.render_state(orchestrator.agents, orchestrator.all_tickets, orchestrator.pending_backlog)
        dashboard.render_resolution_summary(orchestrator.all_tickets)
    else:
        console.print(json.dumps(summary, indent=2))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        if not args.headless:
            console.print(f"[bold green]Saved summary report to {out_path}[/bold green]")


if __name__ == "__main__":
    main()

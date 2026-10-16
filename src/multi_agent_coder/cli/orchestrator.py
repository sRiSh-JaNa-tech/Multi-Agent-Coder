"""
02_ticket_orchestrator.py

Main Ticket Orchestration System.
The Main Orchestrator starts all agents (limit 3 from .env), identifies problems,
raises tickets, and distributes them to agents with a strict queue limit of 3.
Each agent processes its queued tickets strictly one by one (synchronously).
"""

import os
import sys
import time
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# Ensure module path resolution
_NAV_DIR = Path(__file__).resolve().parent
if str(_NAV_DIR) not in sys.path:
    sys.path.insert(0, str(_NAV_DIR))

from ..common.logging_config import setup_logging
from ..common.menu import interactive_menu
from orchestrator import MainOrchestrator, TicketDashboard, TicketStatus

load_dotenv(find_dotenv())
logger = setup_logging(__name__)
console = Console()

SUGGESTED_PROBLEMS = [
    "Refactor caching layer to use LRU eviction, add hit/miss metrics, and verify with unit tests",
    "Audit codebase security vulnerabilities, add input sanitization guards, and generate security report",
    "Implement AST-based symbol outline tool, add error handling, and test with sample Python files",
    "Optimize embedding batch pipeline, add retry backoff strategy, and benchmark throughput",
]



def main() -> None:
    api_key = ensure_api_key(console)
    dashboard = TicketDashboard(console=console)

    header = Panel(
        "[bold cyan]Multi-Agent Ticket Orchestration Hub[/bold cyan]\n\n"
        "1. The [bold yellow]Main Orchestrator[/bold yellow] starts all worker agents (up to MAX_AGENTS).\n"
        "2. Identifies sub-problems and raises discrete [bold green]Tickets[/bold green].\n"
        "3. Enforces a strict [bold magenta]Queue Limit of 3[/bold magenta] per agent.\n"
        "4. Agents process queued tickets [bold blue]synchronously one by one[/bold blue].",
        title="[bold green]Ticket Orchestration System[/bold green]",
        border_style="cyan"
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

    # Initialize Main Orchestrator
    orchestrator = MainOrchestrator(api_key=api_key, queue_limit_per_agent=3)
    dashboard.render_header(selected_problem, orchestrator.max_agents, orchestrator.queue_limit_per_agent)

    console.print("\n[bold yellow]Step 1: Main Orchestrator analyzing problem and raising tickets...[/bold yellow]")
    tickets = orchestrator.identify_problems_and_create_tickets(selected_problem)

    console.print(f"[green]✔ Raised {len(tickets)} problem tickets.[/green]\n")

    console.print("[bold yellow]Step 2: Dispatching tickets into agent queues (limit: 3 per agent)...[/bold yellow]")
    orchestrator.dispatch_all_pending()

    dashboard.render_state(orchestrator.agents, orchestrator.all_tickets, orchestrator.pending_backlog)

    console.print("[bold yellow]Step 3: Agents executing tickets synchronously one by one...[/bold yellow]\n")

    def on_step(t):
        dashboard.render_state(orchestrator.agents, orchestrator.all_tickets, orchestrator.pending_backlog)
        time.sleep(0.5)

    resolved = orchestrator.process_all_tickets_synchronously(on_step_callback=on_step)

    dashboard.render_state(orchestrator.agents, orchestrator.all_tickets, orchestrator.pending_backlog)
    dashboard.render_resolution_summary(orchestrator.all_tickets)


if __name__ == "__main__":
    main()

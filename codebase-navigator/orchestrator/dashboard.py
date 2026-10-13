"""
Rich Console Dashboard for Multi-Agent Ticket Orchestrator.
Renders real-time visual tables of agent queues (limit: 3) and ticket statuses.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from orchestrator.ticket import Ticket, TicketStatus
from orchestrator.agent_worker import AgentWorker


class TicketDashboard:
    """Renders ticket queues and agent execution progress using Rich."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render_header(self, objective: str, max_agents: int, queue_limit: int) -> None:
        """Render the banner for the ticket orchestration session."""
        lines = [
            "[bold cyan]Multi-Agent Ticket Orchestration Hub[/bold cyan]",
            "",
            f"[bold white]Identified Objective:[/bold white] {objective}",
            f"[dim]Worker Fleet: {max_agents} Agents | Strict Queue Limit: {queue_limit} tickets per agent | Mode: Synchronous FIFO[/dim]",
        ]
        self.console.print(Panel("\n".join(lines), title="[bold green]Ticket Orchestration System[/bold green]", border_style="cyan"))

    def render_state(self, agents: list[AgentWorker], tickets: list[Ticket], backlog: list[Ticket]) -> None:
        """Render the complete status of all agents and tickets."""
        # 1. Agent Queue Status Table
        agent_table = Table(title="[bold yellow]Worker Agent Fleet Status[/bold yellow]", expand=True, border_style="yellow")
        agent_table.add_column("Agent ID", style="bold cyan", width=12)
        agent_table.add_column("Role", style="white")
        agent_table.add_column("Specialty", style="magenta", width=12)
        agent_table.add_column("Queue (Max 3)", justify="center", width=16)
        agent_table.add_column("Current Task", style="green")
        agent_table.add_column("Completed", justify="right", width=10)

        for a in agents:
            q_color = "green" if a.queue_size < 2 else ("yellow" if a.queue_size < a.queue_limit else "bold red")
            q_text = f"[{q_color}]{a.queue_size}/{a.queue_limit}[/{q_color}]"
            curr = f"[bold cyan]{a.current_ticket.id}[/bold cyan]: {a.current_ticket.title[:30]}" if a.current_ticket else "[dim]Idle[/dim]"
            agent_table.add_row(
                a.agent_id,
                a.role,
                a.specialty,
                q_text,
                curr,
                str(len(a.history))
            )

        self.console.print(agent_table)

        # 2. Ticket Board Table
        ticket_table = Table(title="[bold cyan]Ticket Distribution & Execution Board[/bold cyan]", expand=True, border_style="cyan")
        ticket_table.add_column("Ticket ID", style="bold yellow", width=14)
        ticket_table.add_column("Title", style="white")
        ticket_table.add_column("Category", style="magenta", width=12)
        ticket_table.add_column("Assigned Agent", style="cyan", width=14)
        ticket_table.add_column("Status", justify="center", width=16)
        ticket_table.add_column("Duration", justify="right", width=10)

        for t in tickets:
            status_style = {
                TicketStatus.PENDING: "[yellow]PENDING[/yellow]",
                TicketStatus.QUEUED: "[magenta]QUEUED[/magenta]",
                TicketStatus.IN_PROGRESS: "[bold cyan]► IN PROGRESS[/bold cyan]",
                TicketStatus.RESOLVED: "[bold green]✔ RESOLVED[/bold green]",
                TicketStatus.FAILED: "[bold red]✖ FAILED[/bold red]",
            }.get(t.status, str(t.status))

            assigned = t.assigned_agent_id or "[dim]Backlog[/dim]"
            dur = f"{t.duration_seconds}s" if t.duration_seconds > 0 else "-"
            ticket_table.add_row(
                t.id,
                t.title[:45],
                t.category,
                assigned,
                status_style,
                dur,
            )

        self.console.print(ticket_table)

        if backlog:
            self.console.print(
                f"[bold yellow]Backlog Notice:[/bold yellow] {len(backlog)} ticket(s) waiting for an agent queue slot."
            )
        self.console.print()

    def render_resolution_summary(self, tickets: list[Ticket]) -> None:
        """Render final summary of all resolved tickets."""
        resolved = [t for t in tickets if t.status == TicketStatus.RESOLVED]
        failed = [t for t in tickets if t.status == TicketStatus.FAILED]

        self.console.print("\n" + "="*80)
        self.console.print(
            f"[bold green]Ticket Orchestration Completed:[/bold green] "
            f"{len(resolved)} resolved, {len(failed)} failed out of {len(tickets)} total tickets.\n"
        )

        for t in resolved:
            panel_lines = [
                f"[bold white]{t.title}[/bold white]",
                f"[dim]Assigned to: {t.assigned_agent_id} | Category: {t.category} | Time: {t.duration_seconds}s[/dim]",
                "",
                "[green]Resolution:[/green]",
                t.result or "Done.",
            ]
            self.console.print(
                Panel(
                    "\n".join(panel_lines),
                    title=f"[bold green]✔ {t.id} - RESOLVED[/bold green]",
                    border_style="green",
                )
            )

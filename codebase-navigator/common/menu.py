"""
Interactive Console Menu
Provides rich interactive CLI menus for selecting items or entering custom inputs.
"""

from typing import Any
from rich.console import Console
from rich.prompt import Prompt


def interactive_menu(
    console: Console,
    options: list[str],
    title: str = "Select an Option",
    header: Any = None,
    allow_custom: bool = True,
    custom_prompt: str = "Enter custom value",
) -> str | None:
    """Display an interactive menu and prompt for user selection."""
    if header:
        console.print(header)

    console.print(f"\n[bold cyan]{title}:[/bold cyan]")
    for idx, opt in enumerate(options, 1):
        console.print(f"  [bold yellow]{idx}[/bold yellow]) {opt}")

    if allow_custom:
        custom_idx = len(options) + 1
        console.print(f"  [bold yellow]{custom_idx}[/bold yellow]) [italic]Custom input...[/italic]")

    while True:
        try:
            choice = Prompt.ask("\nEnter choice", default="1")
            choice = choice.strip()
            if not choice:
                continue

            if choice.isdigit():
                num = int(choice)
                if 1 <= num <= len(options):
                    return options[num - 1]
                elif allow_custom and num == len(options) + 1:
                    custom_val = Prompt.ask(f"[bold green]{custom_prompt}[/bold green]").strip()
                    if custom_val:
                        return custom_val
                    console.print("[red]Input cannot be empty.[/red]")
                else:
                    console.print("[red]Invalid selection number.[/red]")
            else:
                # Direct string entry
                return choice
        except (KeyboardInterrupt, EOFError):
            return None

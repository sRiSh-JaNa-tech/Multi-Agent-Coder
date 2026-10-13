import sys
from typing import Any
from rich.box import ROUNDED, SIMPLE
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

# Ensure Windows terminals handle UTF-8 symbols cleanly
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class ConsoleUI:
    """Rich console presentation layer for agent activities, tools, diffs, and outcomes."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(force_terminal=True, color_system="auto")

    def display_app_banner(self, repo: str | None = None) -> None:
        """Render modern header panel with agent capabilities and active workspace."""
        title_text = Text()
        title_text.append("⚡ MULTI-AGENT CODEBASE NAVIGATOR & CODING AGENT ⚡\n", style="bold cyan")
        title_text.append(
            "Autonomous Collaboration: Orchestrator ── Navigator ── Coder ── Reviewer",
            style="dim italic",
        )

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold cyan", justify="left")
        grid.add_column(style="dim", justify="left")

        grid.add_row("🔍 Navigator", "Semantic RAG, AST outlines, exact grep & file reading")
        grid.add_row("💻 Coder", "Surgical text replacements, file creation & code patches")
        grid.add_row("🛡️ Reviewer", "Syntax validation, test runners, git diff analysis")
        grid.add_row("🧠 Memory", "Persistent architectural facts, insights & preferences")

        if repo:
            repo_status = Panel(
                Text.assemble(
                    ("Active Target: ", "bold yellow"),
                    (repo, "bold green"),
                ),
                box=ROUNDED,
                border_style="green",
            )
            content = Group(title_text, Rule(style="cyan"), grid, repo_status)
        else:
            content = Group(title_text, Rule(style="cyan"), grid)

        self.console.print(
            Panel(
                content,
                border_style="bright_blue",
                box=ROUNDED,
                padding=(1, 2),
            )
        )

    def display_agent_banner(self, agent_name: str, task: str) -> None:
        """Render distinct banner when a specific subagent takes action."""
        color_map = {
            "orchestrator": ("bold magenta", "magenta", "🎯"),
            "navigator": ("bold cyan", "cyan", "🔍"),
            "coder": ("bold green", "green", "💻"),
            "reviewer": ("bold yellow", "yellow", "🛡️"),
        }
        style, border, emoji = color_map.get(
            agent_name.lower(), ("bold white", "white", "🤖")
        )

        title = f"{emoji} [{style}]{agent_name.upper()} AGENT[/{style}]"
        self.console.print(
            Panel(
                f"[white]{task}[/white]",
                title=title,
                title_align="left",
                border_style=border,
                box=ROUNDED,
                padding=(0, 1),
            )
        )

    def display_tool_call(self, name: str, args: dict[str, Any]) -> None:
        """Render stylized card when a tool is called."""
        # Categorize tools for customized styling
        if name in ("create_file", "write_file", "replace_file_content"):
            category = "CODE EDIT"
            color = "green"
            icon = "✏️"
        elif name in ("run_command", "git_diff", "git_status", "check_syntax"):
            category = "EXECUTE"
            color = "yellow"
            icon = "⚡"
        elif name in ("get_file_outline", "search_code", "grep", "read_file", "list_directory"):
            category = "NAVIGATE"
            color = "cyan"
            icon = "🔍"
        else:
            category = "SYSTEM"
            color = "magenta"
            icon = "📦"

        # Build clean parameter badges
        param_table = Table.grid(padding=(0, 1))
        param_table.add_column(style=f"bold {color}")
        param_table.add_column(style="dim")
        param_table.add_column(style="white")

        safe_args = args if isinstance(args, dict) else {}
        for k, v in safe_args.items():
            str_v = str(v)
            if len(str_v) > 85:
                str_v = str_v[:82] + "..."
            param_table.add_row(f"{k}:", "→", str_v)

        panel_content = Group(
            Text.assemble(
                (f"{icon} [{category}] ", f"bold {color}"),
                (name, "bold white"),
            ),
            param_table,
        )

        self.console.print(
            Panel(
                panel_content,
                border_style=color,
                box=ROUNDED,
                padding=(0, 1),
            )
        )

    def display_tool_result(self, name: str, result: str) -> None:
        result = str(result) if result is not None else ""
        """Render customized view based on tool type."""
        # 1. Outline View
        if name == "get_file_outline" and not result.startswith("File not found"):
            self._render_outline(result)
            return

        # 2. Git Diff View
        if name == "git_diff":
            self._render_git_diff(result)
            return

        # 3. Command Execution View
        if name == "run_command":
            self._render_command_result(result)
            return

        # 4. Syntax Validation View
        if name == "check_syntax":
            self._render_syntax_result(result)
            return

        # 5. Code Edit Notifications
        if name in ("create_file", "write_file", "replace_file_content"):
            self._render_code_edit_result(result)
            return

        # Generic brief preview
        preview = result.strip()
        lines = preview.splitlines()
        if len(lines) > 8:
            compact = "\n".join(lines[:7]) + f"\n... [dim]({len(lines) - 7} more lines)[/dim]"
        else:
            compact = preview

        self.console.print(
            Panel(
                compact,
                title="[dim]Result[/dim]",
                title_align="left",
                border_style="dim",
                box=ROUNDED,
                padding=(0, 1),
            )
        )

    def _render_outline(self, text: str) -> None:
        """Render AST outlines as a clean interactive tree."""
        lines = text.splitlines()
        root_title = lines[0] if lines else "Symbols Outline"
        tree = Tree(f"[bold cyan]📁 {root_title}[/bold cyan]")
        current_class_node = None

        for line in lines[1:]:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("class "):
                current_class_node = tree.add(f"[bold yellow]🏛️ {stripped}[/bold yellow]")
            elif stripped.startswith("def ") or stripped.startswith("async def "):
                if line.startswith("    ") and current_class_node:
                    current_class_node.add(f"[green]λ {stripped}[/green]")
                else:
                    tree.add(f"[bold green]λ {stripped}[/bold green]")
            else:
                tree.add(f"[dim]{stripped}[/dim]")

        self.console.print(
            Panel(
                tree,
                title="[bold cyan]AST Outline Analysis[/bold cyan]",
                border_style="cyan",
                box=ROUNDED,
            )
        )

    def _render_git_diff(self, diff_text: str) -> None:
        """Render diff with native syntax highlighting."""
        if "No git diff detected" in diff_text:
            self.console.print(
                Panel(
                    "[dim green]✓ Clean working tree (no unstaged or staged diff)[/dim green]",
                    border_style="green",
                    box=ROUNDED,
                )
            )
            return

        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
        self.console.print(
            Panel(
                syntax,
                title="[bold yellow]Git Diff Inspector[/bold yellow]",
                border_style="yellow",
                box=ROUNDED,
            )
        )

    def _render_command_result(self, result: str) -> None:
        """Render terminal command execution panel with exit code badge."""
        has_exit_zero = "Exit code: 0" in result
        status_badge = (
            "[bold green]✓ SUCCESS (Code 0)[/bold green]"
            if has_exit_zero
            else "[bold red]✗ FAILURE (Non-Zero)[/bold red]"
        )
        border = "green" if has_exit_zero else "red"

        self.console.print(
            Panel(
                result,
                title=f"Terminal Output ── {status_badge}",
                title_align="left",
                border_style=border,
                box=ROUNDED,
            )
        )

    def _render_syntax_result(self, result: str) -> None:
        """Render syntax check banner."""
        if "Syntax valid" in result:
            self.console.print(
                Panel(
                    f"[bold green]✓ {result}[/bold green]",
                    border_style="green",
                    box=ROUNDED,
                )
            )
        else:
            self.console.print(
                Panel(
                    f"[bold red]✗ {result}[/bold red]",
                    border_style="red",
                    box=ROUNDED,
                )
            )

    def _render_code_edit_result(self, result: str) -> None:
        """Render code modification result."""
        is_success = "Successfully" in result
        border = "green" if is_success else "red"
        icon = "✓" if is_success else "✗"
        self.console.print(
            Panel(
                f"[{border}]{icon} {result}[/{border}]",
                border_style=border,
                box=ROUNDED,
            )
        )

    def display_agent_response(self, agent_name: str, response: str) -> None:
        """Render final markdown text from an agent."""
        color_map = {
            "orchestrator": "magenta",
            "navigator": "cyan",
            "coder": "green",
            "reviewer": "yellow",
        }
        border = color_map.get(agent_name.lower(), "blue")
        md = Markdown(response)
        self.console.print(
            Panel(
                md,
                title=f"[bold {border}]{agent_name.title()} Agent[/bold {border}]",
                border_style=border,
                box=ROUNDED,
                padding=(1, 2),
            )
        )

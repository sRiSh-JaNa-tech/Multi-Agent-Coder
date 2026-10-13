"""
Gemini Token Tracker
Tracks prompt, candidate, and total tokens across agent turns and writes cumulative stats.
"""

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.table import Table


class GeminiTokenTracker:
    """Tracks token consumption for Google Gemini API calls."""

    def __init__(self, csv_path: Path | str | None = None, model: str = "gemini-2.0-flash") -> None:
        self.csv_path = Path(csv_path) if csv_path else None
        self.model = model
        self.total_prompt_tokens = 0
        self.total_candidate_tokens = 0
        self.total_tokens = 0
        self.call_count = 0
        self.console = Console()

    def track(self, usage_metadata: Any, demo_name: str = "Codebase Navigator") -> None:
        """Record usage from a Gemini GenerateContent response."""
        if not usage_metadata:
            return

        prompt_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
        candidate_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0
        total_tokens = getattr(usage_metadata, "total_token_count", 0) or (prompt_tokens + candidate_tokens)

        self.total_prompt_tokens += prompt_tokens
        self.total_candidate_tokens += candidate_tokens
        self.total_tokens += total_tokens
        self.call_count += 1

        if self.csv_path:
            try:
                self.csv_path.parent.mkdir(parents=True, exist_ok=True)
                file_exists = self.csv_path.exists()
                with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow([
                            "timestamp",
                            "demo_name",
                            "model",
                            "prompt_tokens",
                            "candidate_tokens",
                            "total_tokens",
                        ])
                    writer.writerow([
                        datetime.now(timezone.utc).isoformat(),
                        demo_name,
                        self.model,
                        prompt_tokens,
                        candidate_tokens,
                        total_tokens,
                    ])
            except Exception:
                # Do not fail task if CSV write fails
                pass

    def report(self) -> None:
        """Display a rich summary table of token usage."""
        table = Table(title="Gemini Token Usage Summary", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Model", self.model)
        table.add_row("API Calls", str(self.call_count))
        table.add_row("Prompt Tokens", f"{self.total_prompt_tokens:,}")
        table.add_row("Candidate Tokens", f"{self.total_candidate_tokens:,}")
        table.add_row("Total Tokens", f"[bold green]{self.total_tokens:,}[/bold green]")

        self.console.print(table)

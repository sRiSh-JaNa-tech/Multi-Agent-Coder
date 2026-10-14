"""
Gemini Token Tracker and Execution Guard.
Tracks prompt, candidate, and total tokens across agent turns.
Provides ExecutionGuard circuit breaker against infinite tool loops and budget overruns.
"""

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.table import Table


class BudgetExceededError(Exception):
    """Raised when token consumption exceeds configured budget ceiling."""
    pass


class InfiniteLoopError(Exception):
    """Raised when an agent repeatedly executes identical tool calls."""
    pass


class ExecutionGuard:
    """
    Guards the agent loop against runaway spend and infinite tool loops.
    Enforces per-ticket token limits and state-hash deduplication.
    """

    def __init__(self, max_tokens: int = 50_000, max_identical_calls: int = 3):
        self.max_tokens = max_tokens
        self.max_identical_calls = max_identical_calls
        self.total_tokens = 0
        self._call_counts: dict[str, int] = {}

    def record_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Accumulate token spend and trip circuit breaker if ceiling exceeded."""
        self.total_tokens += prompt_tokens + completion_tokens
        if self.total_tokens > self.max_tokens:
            raise BudgetExceededError(
                f"Token budget exceeded: used {self.total_tokens} / {self.max_tokens} tokens."
            )

    def record_tool_call(self, tool_name: str, tool_args: dict) -> None:
        """Track tool-call signature hash; trip circuit breaker on repeated calls."""
        canonical = json.dumps({"tool": tool_name, "args": tool_args}, sort_keys=True)
        signature = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self._call_counts[signature] = self._call_counts.get(signature, 0) + 1

        if self._call_counts[signature] >= self.max_identical_calls:
            raise InfiniteLoopError(
                f"Circuit breaker tripped: tool '{tool_name}' called {self.max_identical_calls} "
                f"times with identical arguments {tool_args}."
            )

    def reset_call_counts(self) -> None:
        """Reset tool call tracking for a new turn or ticket."""
        self._call_counts.clear()


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

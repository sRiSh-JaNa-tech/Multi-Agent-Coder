"""
Run-wide token budget shared by the orchestrator and every worker agent.

``limit=None`` means any amount of usage is permitted. The budget is a *soft* ceiling:
the Gemini API only reports usage after a call completes, so the call that crosses the
limit finishes and every call after it is refused.
"""

from __future__ import annotations

import threading
from typing import Any


class TokenBudgetExceeded(Exception):
    """Raised before an LLM call when the run-wide token budget is already spent."""


def usage_from_response(response: Any) -> tuple[int, int, int]:
    """Extract (prompt, completion, total) token counts from a Gemini response."""
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return 0, 0, 0
    prompt = getattr(usage, "prompt_token_count", 0) or 0
    completion = getattr(usage, "candidates_token_count", 0) or 0
    total = getattr(usage, "total_token_count", 0) or (prompt + completion)
    return int(prompt), int(completion), int(total)


class TokenBudget:
    """Thread-safe token counter with an optional ceiling."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = limit if (limit is not None and limit > 0) else None
        self.used = 0
        self._lock = threading.Lock()

    @property
    def unlimited(self) -> bool:
        return self.limit is None

    @property
    def remaining(self) -> int | None:
        return None if self.limit is None else max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.limit is not None and self.used >= self.limit

    def record(self, tokens: int) -> None:
        if tokens > 0:
            with self._lock:
                self.used += tokens

    def check(self) -> None:
        """Raise ``TokenBudgetExceeded`` if no budget is left for another LLM call."""
        if self.exhausted:
            raise TokenBudgetExceeded(
                f"Token budget exhausted: used {self.used} of {self.limit} tokens."
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "limit_label": "unlimited" if self.limit is None else self.limit,
            "used": self.used,
            "remaining": self.remaining,
            "exhausted": self.exhausted,
        }

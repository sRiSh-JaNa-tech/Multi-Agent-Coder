import csv
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TokenUsageTracker(ABC):
    """
    Abstract base class for tracking token usage across API calls.

    Provides a common interface for different LLM providers while allowing
    provider-specific token extraction logic.
    """

    def __init__(self, csv_path: str | Path | None = None):
        """
        Initialize the token tracker.

        Args:
            csv_path: Optional path to a CSV file for persistent usage logging.
        """
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.csv_path = Path(csv_path) if csv_path else None
        if self.csv_path:
            self._init_csv()

    def _init_csv(self) -> None:
        """Initialize the CSV file with headers if it doesn't exist."""
        if not self.csv_path:
            return
        if not self.csv_path.exists():
            try:
                self.csv_path.parent.mkdir(parents=True, exist_ok=True)
                with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        ["timestamp", "demo", "model", "prompt_tokens", "completion_tokens", "total_tokens"]
                    )
            except Exception as e:
                logger.error("Failed to initialize token usage CSV at %s: %s", self.csv_path, e)
                self.csv_path = None

    def _log_to_csv(
        self, demo: str, model: str, prompt: int, completion: int, total: int
    ) -> None:
        """Append a row to the token usage CSV."""
        if not self.csv_path:
            return
        try:
            with self.csv_path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        demo,
                        model,
                        prompt,
                        completion,
                        total,
                    ]
                )
        except Exception as e:
            logger.error("Failed to log token usage to CSV: %s", e)

    @abstractmethod
    def track(self, usage: Any) -> None:
        """
        Track tokens from a response's usage data.

        Args:
            usage: Usage object from LLM response (format varies by provider)
        """
        pass

    def report(self) -> None:
        """Log the total token usage."""
        total = self.total_input_tokens + self.total_output_tokens
        logger.info(
            "Token Usage - Input: %d, Output: %d, Total: %d",
            self.total_input_tokens,
            self.total_output_tokens,
            total,
        )

    def get_total_tokens(self) -> int:
        """Get the total number of tokens used."""
        return self.total_input_tokens + self.total_output_tokens

    def get_input_tokens(self) -> int:
        """Get the total input tokens used."""
        return self.total_input_tokens

    def get_output_tokens(self) -> int:
        """Get the total output tokens used."""
        return self.total_output_tokens

    def reset(self) -> None:
        """Reset all token counts to zero."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0


class AnthropicTokenTracker(TokenUsageTracker):
    """
    Token tracker for Anthropic Claude API.

    Handles Anthropic's usage format including cache token accounting.
    """

    def __init__(self) -> None:
        super().__init__()
        self.total_cache_read_tokens = 0
        self.total_cache_creation_tokens = 0

    def track(self, usage: Any, demo_name: str = "Anthropic", model_name: str = "claude-3") -> None:
        """Track tokens from an Anthropic response, including cache tokens."""
        if hasattr(usage, "input_tokens") and hasattr(usage, "output_tokens"):
            prompt = usage.input_tokens
            completion = usage.output_tokens
            self.total_input_tokens += prompt
            self.total_output_tokens += completion
            # Track cache tokens when available (prompt caching)
            if hasattr(usage, "cache_read_input_tokens") and usage.cache_read_input_tokens:
                self.total_cache_read_tokens += usage.cache_read_input_tokens
            if hasattr(usage, "cache_creation_input_tokens") and usage.cache_creation_input_tokens:
                self.total_cache_creation_tokens += usage.cache_creation_input_tokens
            
            self._log_to_csv(demo_name, model_name, prompt, completion, prompt + completion)
        else:
            logger.warning(
                "Invalid Anthropic usage format: %s. Expected input_tokens and output_tokens.",
                type(usage),
            )

    def report(self) -> None:
        """Log total token usage with cache breakdown."""
        total = self.total_input_tokens + self.total_output_tokens
        cache_info = ""
        if self.total_cache_read_tokens or self.total_cache_creation_tokens:
            cache_info = (
                f", Cache Read: {self.total_cache_read_tokens:,}"
                f", Cache Create: {self.total_cache_creation_tokens:,}"
            )
        logger.info(
            "Token Usage — Input: %s, Output: %s, Total: %s%s",
            f"{self.total_input_tokens:,}",
            f"{self.total_output_tokens:,}",
            f"{total:,}",
            cache_info,
        )

    def get_cache_read_tokens(self) -> int:
        """Get total cache read tokens."""
        return self.total_cache_read_tokens

    def get_cache_creation_tokens(self) -> int:
        """Get total cache creation tokens."""
        return self.total_cache_creation_tokens

    def reset(self) -> None:
        """Reset all token counts to zero."""
        super().reset()
        self.total_cache_read_tokens = 0
        self.total_cache_creation_tokens = 0


class OpenAITokenTracker(TokenUsageTracker):
    """
    Token tracker for OpenAI API.

    Handles both OpenAI API formats:
    - Responses API: input_tokens, output_tokens
    - Chat Completions API: prompt_tokens, completion_tokens
    """

    def track(self, usage: Any, demo_name: str = "OpenAI", model_name: str = "gpt-4") -> None:
        """
        Track tokens from an OpenAI response.

        Args:
            usage: OpenAI usage object (supports both API formats)
        """
        prompt, completion = 0, 0
        # Responses API format
        if hasattr(usage, "input_tokens") and hasattr(usage, "output_tokens"):
            prompt = usage.input_tokens
            completion = usage.output_tokens
        # Chat Completions API format
        elif hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
            prompt = usage.prompt_tokens
            completion = usage.completion_tokens
        else:
            logger.warning(
                "Invalid OpenAI usage format: %s. Expected input_tokens/output_tokens or prompt_tokens/completion_tokens.",
                type(usage),
            )
            return

        self.total_input_tokens += prompt
        self.total_output_tokens += completion
        self._log_to_csv(demo_name, model_name, prompt, completion, prompt + completion)


class LiteLLMTokenTracker(TokenUsageTracker):
    """
    Token tracker for LiteLLM.

    Handles LiteLLM's normalized usage format with prompt_tokens and completion_tokens.
    """

    def track(self, usage: Any) -> None:
        """
        Track tokens from a LiteLLM response.

        Args:
            usage: LiteLLM usage object with prompt_tokens and completion_tokens
        """
        if hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
            self.total_input_tokens += usage.prompt_tokens
            self.total_output_tokens += usage.completion_tokens
        else:
            logger.warning(
                "Invalid LiteLLM usage format: %s. Expected prompt_tokens and completion_tokens.",
                type(usage),
            )


class GeminiTokenTracker(TokenUsageTracker):
    """Token tracker for Google Gemini API."""

    def __init__(self, csv_path: str | Path | None = None, model: str = "gemini-2.0-flash"):
        super().__init__(csv_path=csv_path)
        self.model = model
        self._turn = 0

    def track(self, usage: Any, demo_name: str | None = None) -> None:
        """Track tokens from Gemini's usage_metadata."""
        prompt, completion, total = 0, 0, 0
        if hasattr(usage, "prompt_token_count"):
            prompt = usage.prompt_token_count or 0
            completion = getattr(usage, "candidates_token_count", 0) or 0
            total = getattr(usage, "total_token_count", 0) or (prompt + completion)
        else:
            logger.warning("Invalid Gemini usage format: %s.", type(usage))
            return

        self.total_input_tokens += prompt
        self.total_output_tokens += completion
        
        # Determine demo name
        active_demo = demo_name or f"Gemini Session - Turn {self._turn}"
        
        self._log_to_csv(active_demo, self.model, prompt, completion, total)
        self._turn += 1

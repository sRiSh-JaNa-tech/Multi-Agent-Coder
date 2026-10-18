"""
Swarm configuration loaded from the environment (.env).

Single place that understands every swarm-level knob so the orchestrator, CLI and MCP
server all agree on defaults, aliases and validation.

Environment variables
---------------------
MODEL_NAME (alias GEMINI_MODEL)   Gemini model used by every worker. Default: gemini-2.5-flash-lite
TOKEN_USAGE_LIMIT (alias MAX_TOKENS)
                                  Total token budget for one swarm run. ``None`` (or empty /
                                  unlimited / off) means any amount of usage is permitted.
TARGET_WORKSPACE                  Absolute path of the project the swarm edits IN PLACE.
SWARM_LOG_DIR                     Where run logs are written. Relative paths resolve against the
                                  swarm repository root (never against the target workspace).
AGENT_NAMES                       Optional comma-separated agent ids, applied in roster order.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL = "gemini-2.5-flash-lite"

# Root of the multi-agent-coder repository itself (…/src/multi_agent_coder/common/config.py).
SWARM_REPO_ROOT = Path(__file__).resolve().parents[3]

# Values that mean "no token limit".
_UNLIMITED = {"", "none", "null", "nil", "unlimited", "off", "false", "no", "-1"}
_AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


class ConfigError(ValueError):
    """Raised when an environment value is present but invalid."""


def first_env(*names: str, default: str | None = None) -> str | None:
    """Return the first environment variable in ``names`` that is set (even if empty)."""
    for name in names:
        if name in os.environ:
            return os.environ[name]
    return default


def parse_bool(raw: str | bool | None, default: bool = True) -> bool:
    """Parse a boolean flag from string, bool, or environment variable."""
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def parse_token_limit(raw: str | int | None) -> int | None:
    """
    Parse a token limit. ``None``-like values and non-positive integers mean unlimited.

    A malformed value raises ``ConfigError`` rather than silently becoming "unlimited",
    because a typo such as ``50k`` would otherwise remove the spending cap.
    """
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None

    text = str(raw).strip().lower()
    if text in _UNLIMITED:
        return None
    try:
        value = int(text.replace("_", "").replace(",", ""))
    except ValueError as exc:
        raise ConfigError(
            f"Invalid TOKEN_USAGE_LIMIT {raw!r}: use a whole number of tokens (e.g. 500000) "
            "or 'None' for unlimited."
        ) from exc
    return value if value > 0 else None


def parse_agent_names(raw: str | None) -> list[str]:
    """Parse and validate the comma-separated AGENT_NAMES list."""
    if not raw or not raw.strip():
        return []
    names = [n.strip() for n in raw.split(",") if n.strip()]
    seen: set[str] = set()
    for name in names:
        if not _AGENT_NAME_RE.match(name):
            raise ConfigError(
                f"Invalid agent name {name!r}: use 1-32 letters, digits, '-' or '_' "
                "(must start with a letter or digit)."
            )
        if name.lower() in seen:
            raise ConfigError(f"Duplicate agent name {name!r} in AGENT_NAMES.")
        seen.add(name.lower())
    return names


def resolve_workspace(explicit: str | Path | None = None, default: Path | None = None) -> Path:
    """
    Resolve the directory the swarm edits in place.

    Precedence: explicit argument > TARGET_WORKSPACE env > ``default`` > current directory.
    The result must be an existing directory.
    """
    candidate: str | Path | None = explicit
    if not candidate:
        candidate = first_env("TARGET_WORKSPACE") or None
    if not candidate and default is not None:
        candidate = default
    path = Path(candidate).expanduser() if candidate else Path.cwd()
    path = path.resolve()
    if not path.is_dir():
        raise ConfigError(f"Target workspace does not exist or is not a directory: {path}")
    return path


def workspace_source(explicit: str | Path | None) -> str:
    """Describe where the workspace came from (for status/log output)."""
    if explicit:
        return "argument"
    if first_env("TARGET_WORKSPACE"):
        return "TARGET_WORKSPACE"
    return "default"


@dataclass(frozen=True)
class SwarmConfig:
    """Immutable snapshot of the swarm-level environment configuration."""

    model_name: str = DEFAULT_MODEL
    token_usage_limit: int | None = None
    log_dir: Path = field(default_factory=lambda: SWARM_REPO_ROOT / "logs" / "swarm")
    agent_names: list[str] = field(default_factory=list)
    parallel: bool = True
    auto_qa: bool = True

    @property
    def token_limit_label(self) -> str:
        return "unlimited" if self.token_usage_limit is None else str(self.token_usage_limit)

    @classmethod
    def from_env(cls) -> "SwarmConfig":
        model = (first_env("MODEL_NAME", "GEMINI_MODEL") or "").strip() or DEFAULT_MODEL

        raw_limit = first_env("TOKEN_USAGE_LIMIT", "MAX_TOKENS")
        limit = parse_token_limit(raw_limit)

        raw_dir = (first_env("SWARM_LOG_DIR") or "").strip()
        if raw_dir:
            log_dir = Path(raw_dir).expanduser()
            if not log_dir.is_absolute():
                log_dir = SWARM_REPO_ROOT / log_dir
        else:
            log_dir = SWARM_REPO_ROOT / "logs" / "swarm"

        parallel = parse_bool(first_env("SWARM_PARALLEL", "PARALLEL_EXECUTION"), default=True)
        auto_qa = parse_bool(first_env("AUTO_QA_TESTER", "AUTO_QA"), default=True)

        return cls(
            model_name=model,
            token_usage_limit=limit,
            log_dir=log_dir.resolve(),
            agent_names=parse_agent_names(first_env("AGENT_NAMES")),
            parallel=parallel,
            auto_qa=auto_qa,
        )

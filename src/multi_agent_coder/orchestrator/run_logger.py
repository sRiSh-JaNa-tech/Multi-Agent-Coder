"""
Persistent swarm run logs.

For every run this writes, under ``<SWARM_LOG_DIR>/``:

* ``runs/<run_id>/events.jsonl``  append-only stream: ticket created / assigned / started /
  completed / failed / blocked, every LLM usage record and every tool call
* ``runs/<run_id>/summary.json``  final per-ticket, per-agent and token totals
* ``runs_index.jsonl``            one line per finished run, for quick history queries

Logging never raises: an unwritable log directory degrades to a warning, it must not kill
a swarm run. The run directory is created lazily on the first write, so constructing an
orchestrator (e.g. in tests) leaves nothing on disk.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..common.logging_config import setup_logging

logger = setup_logging(__name__)

_MAX_TEXT = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _clip(value: Any, limit: int = _MAX_TEXT) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"... [+{len(value) - limit} chars]"
    return value


class SwarmRunLogger:
    """Writes the structured ticket ledger for one swarm run."""

    def __init__(
        self,
        log_dir: Path | str,
        *,
        objective: str = "",
        workspace_root: Path | str | None = None,
        model: str = "",
        token_limit: int | None = None,
        max_agents: int = 0,
        queue_limit: int = 0,
        run_id: str | None = None,
    ) -> None:
        self.log_dir = Path(log_dir)
        self.run_id = run_id or f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.run_dir = self.log_dir / "runs" / self.run_id
        self.events_path = self.run_dir / "events.jsonl"
        self.summary_path = self.run_dir / "summary.json"
        self.index_path = self.log_dir / "runs_index.jsonl"

        self.objective = objective
        self.workspace_root = str(workspace_root) if workspace_root else None
        self.model = model
        self.token_limit = token_limit
        self.max_agents = max_agents
        self.queue_limit = queue_limit
        self.started_at = _now_iso()

        self._lock = threading.Lock()
        self._warned = False
        self._started_event_written = False

    # ------------------------------------------------------------------ core
    def _write_line(self, path: Path, record: dict[str, Any]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            if not self._warned:
                self._warned = True
                logger.warning("Swarm run log unavailable (%s): %s", path, exc)

    def event(self, event_type: str, **fields: Any) -> None:
        if not self._started_event_written:
            self._started_event_written = True
            self._write_line(
                self.events_path,
                {
                    "ts": self.started_at,
                    "run_id": self.run_id,
                    "event": "run_started",
                    "objective": _clip(self.objective),
                    "workspace_root": self.workspace_root,
                    "model": self.model,
                    "token_limit": "unlimited" if self.token_limit is None else self.token_limit,
                    "max_agents": self.max_agents,
                    "queue_limit_per_agent": self.queue_limit,
                },
            )
        record = {"ts": _now_iso(), "run_id": self.run_id, "event": event_type}
        record.update({k: _clip(v) for k, v in fields.items()})
        self._write_line(self.events_path, record)

    # ------------------------------------------------------- ticket lifecycle
    def ticket_created(self, ticket: Any) -> None:
        self.event(
            "ticket_created",
            ticket_id=ticket.id,
            title=ticket.title,
            category=ticket.category,
            depends_on=list(ticket.depends_on),
        )

    def ticket_assigned(self, ticket: Any, agent_id: str, queue_depth: int) -> None:
        self.event(
            "ticket_assigned",
            ticket_id=ticket.id,
            agent_id=agent_id,
            category=ticket.category,
            queue_depth=queue_depth,
        )

    def ticket_started(self, ticket: Any, agent_id: str) -> None:
        self.event("ticket_started", ticket_id=ticket.id, agent_id=agent_id)

    def ticket_completed(self, ticket: Any, agent_id: str) -> None:
        self.event(
            "ticket_completed",
            ticket_id=ticket.id,
            agent_id=agent_id,
            duration_seconds=ticket.duration_seconds,
            tokens_used=ticket.tokens_used,
            tool_calls=ticket.tool_calls,
            result=ticket.result,
        )

    def ticket_failed(self, ticket: Any, agent_id: str | None) -> None:
        self.event(
            "ticket_failed",
            ticket_id=ticket.id,
            agent_id=agent_id,
            duration_seconds=ticket.duration_seconds,
            tokens_used=ticket.tokens_used,
            tool_calls=ticket.tool_calls,
            failure_code=ticket.failure_code,
            error=ticket.error,
        )

    def ticket_blocked(self, ticket: Any, reason: str, code: str) -> None:
        self.event(
            "ticket_blocked",
            ticket_id=ticket.id,
            agent_id=ticket.assigned_agent_id,
            failure_code=code,
            error=reason,
        )

    def llm_usage(
        self,
        agent_id: str,
        ticket_id: str | None,
        prompt: int,
        completion: int,
        total: int,
        run_total: int,
    ) -> None:
        self.event(
            "llm_usage",
            agent_id=agent_id,
            ticket_id=ticket_id,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            run_total_tokens=run_total,
        )

    def tool_call(self, agent_id: str, ticket_id: str, name: str, detail: str | None) -> None:
        self.event("tool_call", agent_id=agent_id, ticket_id=ticket_id, tool=name, detail=detail)

    def action_completed(self, agent_id: str, ticket_id: str, name: str, detail: str | None, status: str = "success") -> None:
        self.event("action", agent_id=agent_id, ticket_id=ticket_id, tool=name, detail=detail, status=status)

    # --------------------------------------------------------------- finalize
    def finalize(self, summary: dict[str, Any]) -> None:
        """Write summary.json and append this run to the cross-run index."""
        finished = _now_iso()
        payload = dict(summary)
        payload.update({"run_id": self.run_id, "started_at": self.started_at, "finished_at": finished})
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            with self._lock, open(self.summary_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            if not self._warned:
                self._warned = True
                logger.warning("Swarm run summary unavailable (%s): %s", self.summary_path, exc)

        self.event("run_finished", resolved=summary.get("resolved"), failed=summary.get("failed"),
                   blocked=summary.get("blocked"), total_tickets=summary.get("total_tickets"),
                   tokens_used=(summary.get("token_usage") or {}).get("used"))
        self._write_line(
            self.index_path,
            {
                "run_id": self.run_id,
                "started_at": self.started_at,
                "finished_at": finished,
                "objective": _clip(self.objective, 200),
                "workspace_root": self.workspace_root,
                "model": self.model,
                "total_tickets": summary.get("total_tickets"),
                "resolved": summary.get("resolved"),
                "failed": summary.get("failed"),
                "blocked": summary.get("blocked"),
                "tokens_used": (summary.get("token_usage") or {}).get("used"),
                "token_limit": "unlimited" if self.token_limit is None else self.token_limit,
            },
        )


def read_run_log(log_dir: Path | str, run_id: str | None = None, tail: int = 200) -> dict[str, Any]:
    """Read a run's summary and the last ``tail`` events. ``run_id=None`` selects the latest run."""
    base = Path(log_dir)
    runs_dir = base / "runs"
    if not runs_dir.is_dir():
        return {"error": f"No swarm runs logged yet under {base}"}

    if run_id is None:
        candidates = sorted((p for p in runs_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
        if not candidates:
            return {"error": f"No swarm runs logged yet under {base}"}
        run_dir = candidates[-1]
    else:
        run_dir = runs_dir / run_id
        if not run_dir.is_dir():
            return {"error": f"Run '{run_id}' not found under {runs_dir}"}

    events: list[dict[str, Any]] = []
    events_path = run_dir / "events.jsonl"
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    summary = None
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary = None

    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "finished": summary is not None,
        "summary": summary,
        "event_count": len(events),
        "events": events[-max(1, tail):],
    }


def read_run_index(log_dir: Path | str, limit: int = 10) -> list[dict[str, Any]]:
    """Return the most recent entries of the cross-run index (newest last)."""
    path = Path(log_dir) / "runs_index.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-max(1, limit):]

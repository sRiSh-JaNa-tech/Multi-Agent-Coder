"""
Persistent Run State Store.
SQLite-backed persistence for swarm execution runs, ticket checkpoints,
discovered findings, and agent actions.
"""

from contextlib import contextmanager
import copy
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

from ..common.logging_config import setup_logging

logger = setup_logging(__name__)


class ConcurrencyError(Exception):
    """Raised when an optimistic concurrency version check fails due to concurrent mutation."""
    pass


class RunStateStore:
    """Thread-safe SQLite store for runs, tickets, and findings with optimistic concurrency."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._lock = threading.RLock()
        if db_path is None:
            state_dir = Path.cwd() / ".multi_agent_coder"
            state_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = state_dir / "swarm_state.db"
        else:
            self.db_path = Path(db_path).resolve()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL,
                    workspace_root TEXT,
                    max_agents INTEGER,
                    created_at REAL,
                    completed_at REAL,
                    summary_json TEXT,
                    version INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    status TEXT NOT NULL,
                    assigned_agent_id TEXT,
                    depends_on_json TEXT,
                    result TEXT,
                    error TEXT,
                    failure_code TEXT,
                    tool_calls INTEGER DEFAULT 0,
                    tokens_used INTEGER DEFAULT 0,
                    verified INTEGER DEFAULT 0,
                    updated_at REAL,
                    version INTEGER DEFAULT 1,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                );

                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    category TEXT,
                    confidence TEXT,
                    severity TEXT,
                    file_path TEXT,
                    evidence TEXT,
                    resolved INTEGER DEFAULT 0,
                    created_at REAL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_tickets_run ON tickets(run_id);
                CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id);
            """)
            try:
                conn.execute("ALTER TABLE runs ADD COLUMN version INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE tickets ADD COLUMN version INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass

    def record_run_start(
        self,
        run_id: str,
        objective: str,
        workspace_root: str = "",
        max_agents: int = 3,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        now = time.time()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (run_id, objective, status, workspace_root, max_agents, created_at, version)
                VALUES (?, ?, 'RUNNING', ?, ?, ?, 1)
                """,
                (run_id, objective, str(workspace_root), max_agents, now),
            )
            return 1

    def update_run_state(
        self,
        run_id: str,
        status: str | None = None,
        summary: dict[str, Any] | None = None,
        expected_version: int | None = None,
        state: dict[str, Any] | None = None,
    ) -> int:
        """Update run status or summary with optimistic concurrency check."""
        now = time.time()
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT version, status, summary_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                raise ValueError(f"Run {run_id} not found in state store.")
            current_version = row["version"] or 1
            if expected_version is not None and current_version != expected_version:
                raise ConcurrencyError(
                    f"Run {run_id} optimistic concurrency version collision: expected version {expected_version}, found {current_version}"
                )
            new_version = current_version + 1
            if state is not None:
                if status is None:
                    status = state.get("status")
                if summary is None:
                    summary = state
            new_status = status if status is not None else row["status"]
            new_summary = json.dumps(summary) if summary is not None else row["summary_json"]

            conn.execute(
                """
                UPDATE runs
                SET status = ?, summary_json = ?, version = ?, completed_at = ?
                WHERE run_id = ?
                """,
                (new_status, new_summary, new_version, now, run_id),
            )
            return new_version

    def record_run_finish(
        self,
        run_id: str,
        status: str,
        summary: dict[str, Any],
        expected_version: int | None = None,
    ) -> int:
        now = time.time()
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT version FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row:
                current_version = row["version"] or 1
                if expected_version is not None and current_version != expected_version:
                    raise ConcurrencyError(
                        f"Run {run_id} optimistic concurrency violation: expected version {expected_version}, found {current_version}"
                    )
                new_version = current_version + 1
            else:
                new_version = 1

            conn.execute(
                """
                UPDATE runs
                SET status = ?, completed_at = ?, summary_json = ?, version = ?
                WHERE run_id = ?
                """,
                (status, now, json.dumps(summary), new_version, run_id),
            )
            return new_version

    def save_ticket_checkpoint(
        self,
        run_id: str,
        ticket: Any,
        expected_version: int | None = None,
    ) -> int:
        now = time.time()
        if isinstance(ticket, dict):
            ticket_id = str(ticket.get("id", ""))
            title = str(ticket.get("title", ""))
            desc = str(ticket.get("description", ""))
            cat = str(ticket.get("category", "general"))
            status = ticket.get("status", "PENDING")
            agent_id = ticket.get("assigned_agent_id")
            deps = ticket.get("depends_on", [])
            result = ticket.get("result")
            error = ticket.get("error")
            fcode = ticket.get("failure_code")
            calls = ticket.get("tool_calls", 0)
            tokens = ticket.get("tokens_used", 0)
            verified = 1 if ticket.get("verified", False) else 0
        else:
            ticket_id = str(getattr(ticket, "id", ""))
            title = str(getattr(ticket, "title", ""))
            desc = str(getattr(ticket, "description", ""))
            cat = str(getattr(ticket, "category", "general"))
            status = getattr(ticket, "status", "PENDING")
            agent_id = getattr(ticket, "assigned_agent_id", None)
            deps = getattr(ticket, "depends_on", [])
            result = getattr(ticket, "result", None)
            error = getattr(ticket, "error", None)
            fcode = getattr(ticket, "failure_code", None)
            calls = getattr(ticket, "tool_calls", 0)
            tokens = getattr(ticket, "tokens_used", 0)
            verified = 1 if getattr(ticket, "verified", False) else 0

        status_val = status.value if hasattr(status, "value") else str(status)

        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT version FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
            if row:
                current_version = row["version"] or 1
                if expected_version is not None and current_version != expected_version:
                    raise ConcurrencyError(
                        f"Ticket {ticket_id} optimistic concurrency violation: expected version {expected_version}, found {current_version}"
                    )
                new_version = current_version + 1
            else:
                new_version = 1

            conn.execute(
                """
                INSERT OR REPLACE INTO tickets (
                    ticket_id, run_id, title, description, category, status,
                    assigned_agent_id, depends_on_json, result, error, failure_code,
                    tool_calls, tokens_used, verified, updated_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    run_id,
                    title,
                    desc,
                    cat,
                    status_val,
                    agent_id,
                    json.dumps(deps),
                    result,
                    error,
                    fcode,
                    calls,
                    tokens,
                    verified,
                    now,
                    new_version,
                ),
            )
            return new_version

    def record_finding(self, run_id: str, finding: Any) -> None:
        if isinstance(finding, dict):
            fid = finding.get("id", "")
            title = finding.get("title", "")
            cat = finding.get("category", "defect")
            conf = finding.get("confidence", "high")
            sev = finding.get("severity", "medium")
            fpath = finding.get("file_path")
            evid = finding.get("evidence", "")
        else:
            fid = getattr(finding, "id", "")
            title = getattr(finding, "title", "")
            cat = getattr(finding, "category", "defect")
            conf = getattr(finding, "confidence", "high")
            sev = getattr(finding, "severity", "medium")
            fpath = getattr(finding, "file_path", None)
            evid = getattr(finding, "evidence", "")

        cat_val = cat.value if hasattr(cat, "value") else str(cat)
        conf_val = conf.value if hasattr(conf, "value") else str(conf)
        sev_val = sev.value if hasattr(sev, "value") else str(sev)

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO findings (
                    finding_id, run_id, title, category, confidence, severity, file_path, evidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (fid, run_id, title, cat_val, conf_val, sev_val, fpath, evid, time.time()),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("summary_json"):
                try:
                    res["summary"] = json.loads(res["summary_json"])
                    res["state"] = res["summary"]
                except Exception:
                    pass
            return copy.deepcopy(res)

    def get_run_tickets(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM tickets WHERE run_id = ?", (run_id,)).fetchall()
            tickets = []
            for r in rows:
                t = dict(r)
                if t.get("depends_on_json"):
                    try:
                        t["depends_on"] = json.loads(t["depends_on_json"])
                    except Exception:
                        t["depends_on"] = []
                tickets.append(t)
            return copy.deepcopy(tickets)

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
            if not row:
                return None
            t = dict(row)
            if t.get("depends_on_json"):
                try:
                    t["depends_on"] = json.loads(t["depends_on_json"])
                except Exception:
                    t["depends_on"] = []
            return copy.deepcopy(t)


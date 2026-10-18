"""
Persistent Run State Store.
SQLite-backed persistence for swarm execution runs, ticket checkpoints,
discovered findings, and agent actions.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time
from typing import Any

from ..common.logging_config import setup_logging

logger = setup_logging(__name__)


class RunStateStore:
    """Thread-safe SQLite store for runs, tickets, and findings."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            state_dir = Path.cwd() / ".multi_agent_coder"
            state_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = state_dir / "swarm_state.db"
        else:
            self.db_path = Path(db_path).resolve()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL,
                    workspace_root TEXT,
                    max_agents INTEGER,
                    created_at REAL,
                    completed_at REAL,
                    summary_json TEXT
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

    def record_run_start(
        self,
        run_id: str,
        objective: str,
        workspace_root: str,
        max_agents: int = 3,
    ) -> None:
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (run_id, objective, status, workspace_root, max_agents, created_at)
                VALUES (?, ?, 'RUNNING', ?, ?, ?)
                """,
                (run_id, objective, str(workspace_root), max_agents, now),
            )

    def record_run_finish(self, run_id: str, status: str, summary: dict[str, Any]) -> None:
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, completed_at = ?, summary_json = ?
                WHERE run_id = ?
                """,
                (status, now, json.dumps(summary), run_id),
            )

    def save_ticket_checkpoint(self, run_id: str, ticket: Any) -> None:
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

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tickets (
                    ticket_id, run_id, title, description, category, status,
                    assigned_agent_id, depends_on_json, result, error, failure_code,
                    tool_calls, tokens_used, verified, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

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

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO findings (
                    finding_id, run_id, title, category, confidence, severity, file_path, evidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (fid, run_id, title, cat_val, conf_val, sev_val, fpath, evid, time.time()),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("summary_json"):
                try:
                    res["summary"] = json.loads(res["summary_json"])
                except Exception:
                    pass
            return res

    def get_run_tickets(self, run_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
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
            return tickets

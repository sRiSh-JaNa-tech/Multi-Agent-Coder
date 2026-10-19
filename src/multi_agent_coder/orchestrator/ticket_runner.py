"""
Centralized File I/O Actor & Sequential Modification Consumer.
Provides single-threaded daemon queue processing for FileModificationTicket items,
completely eliminating concurrent read-modify-write collisions on the filesystem.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import queue
import threading
import time
from typing import Any

from .ticket import FileModificationTicket, Ticket, TicketStatus
from ..common.logging_config import setup_logging
from ..tools.coding import resolve_safe_path, apply_search_replace, _normalize_file_content

logger = setup_logging(__name__)


class FileIOWorker:
    """
    Single-threaded daemon consumer for FileModificationTicket operations (Actor pattern).
    Serializes all filesystem write mutations across concurrent agent threads.
    Encapsulates its queue and locks within this instance without global locking variables.
    """

    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self._queue: queue.Queue[tuple[FileModificationTicket, threading.Event]] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self.start()

    def start(self) -> None:
        """Start the single-threaded background consumer daemon."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._consume_loop, daemon=True, name="FileIO-ActorDaemon")
            self._thread.start()
            logger.info("Started FileIOWorker daemon consumer on %s", self.workspace_root)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the consumer daemon cleanly."""
        with self._lock:
            if not self._running:
                return
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def submit(self, ticket: FileModificationTicket, timeout: float = 30.0) -> FileModificationTicket:
        """Submit a modification ticket and block until the single-threaded worker executes it."""
        done_event = threading.Event()
        self._queue.put((ticket, done_event))
        if not done_event.wait(timeout=timeout):
            ticket.mark_failed(f"Timed out after {timeout}s waiting for FileIOWorker execution")
        return ticket

    async def asubmit(self, ticket: FileModificationTicket, timeout: float = 30.0) -> FileModificationTicket:
        """Asynchronously submit a modification ticket without blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.submit, ticket, timeout)

    async def enqueue_ticket(self, ticket: FileModificationTicket, timeout: float = 30.0) -> FileModificationTicket:
        """Convenience async enqueue alias for asubmit."""
        return await self.asubmit(ticket, timeout=timeout)

    def _consume_loop(self) -> None:
        while self._running:
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            mod_ticket, done_event = item
            try:
                self._apply_modification(mod_ticket)
            except Exception as exc:
                logger.error("Failed to apply file modification ticket: %s", exc)
                mod_ticket.mark_failed(str(exc))
            finally:
                self._queue.task_done()
                done_event.set()

    def _apply_modification(self, mod_ticket: FileModificationTicket) -> None:
        """Sequentially execute the file modification on the target workspace."""
        op = mod_ticket.operation.lower().strip()

        # Worktree merge operation
        if op in ("merge", "merge_worktree"):
            ticket_id = mod_ticket.ticket_id or mod_ticket.filepath
            target_branch = getattr(mod_ticket, "target_branch", None) or "main"
            try:
                from ..tools.repo import merge_worktree
                merge_worktree(self.workspace_root, ticket_id, target_branch=target_branch)
                mod_ticket.mark_applied()
            except Exception as exc:
                mod_ticket.mark_failed(f"Merge conflict/failure for ticket {ticket_id}: {exc}")
            return

        target_path = resolve_safe_path(self.workspace_root, mod_ticket.filepath)

        if op in ("write", "create"):
            content = _normalize_file_content(mod_ticket.content or "")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            mod_ticket.mark_applied()

        elif op in ("append", "append_line"):
            content = mod_ticket.content or ""
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(content)
            mod_ticket.mark_applied()

        elif op in ("replace", "patch"):
            search = mod_ticket.search_block or ""
            replace = mod_ticket.replace_block or ""
            apply_search_replace(self.workspace_root, mod_ticket.filepath, search, replace)
            mod_ticket.mark_applied()

        elif op in ("delete", "remove"):
            if target_path.exists():
                target_path.unlink()
            mod_ticket.mark_applied()

        else:
            raise ValueError(f"Unsupported FileModificationTicket operation: '{op}'")

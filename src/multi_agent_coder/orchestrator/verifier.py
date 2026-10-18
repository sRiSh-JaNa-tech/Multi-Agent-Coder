"""
Independent Verification Engine for Autonomous Multi-Agent Systems.
Examines concrete evidence (git diffs, syntax checks, test suites, and scope boundaries)
to independently verify work and detect regressions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any

from ..discovery.baseline import RepositoryBaseline
from .ticket import Ticket
from ..tools.execution import (
    execute_run_command,
    execute_check_syntax,
    execute_git_status,
    execute_git_diff,
)
from ..common.logging_config import setup_logging

logger = setup_logging(__name__)


@dataclass
class VerificationResult:
    """Detailed evidence from an independent verification pass."""
    success: bool
    ticket_id: str | None = None
    commands_run: list[dict[str, Any]] = field(default_factory=list)
    git_diff_snippet: str = ""
    modified_files: list[str] = field(default_factory=list)
    scope_violations: list[str] = field(default_factory=list)
    syntax_errors: list[str] = field(default_factory=list)
    test_failures: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    summary: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "ticket_id": self.ticket_id,
            "commands_run": self.commands_run,
            "git_diff_snippet": self.git_diff_snippet[:1000],
            "modified_files": self.modified_files,
            "scope_violations": self.scope_violations,
            "syntax_errors": self.syntax_errors,
            "test_failures": self.test_failures,
            "regressions": self.regressions,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


class IndependentVerifier:
    """
    Independently inspects workspace evidence without relying solely on worker assertions.
    """

    def __init__(
        self,
        workspace_root: Path | str,
        baseline: RepositoryBaseline | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.baseline = baseline

    def _get_current_modified_files(self) -> list[str]:
        """Inspect git status for modified and untracked files."""
        status_out = execute_git_status(workspace_root=self.workspace_root)
        files = []
        for line in status_out.splitlines():
            line = line.strip()
            if line.startswith("modified:") or line.startswith("both modified:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    files.append(parts[1].strip().replace("\\", "/"))
            elif line.startswith("??"):
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    files.append(parts[1].strip().replace("\\", "/"))
        return files

    def verify_ticket(self, ticket: Ticket) -> VerificationResult:
        """
        Verify a single completed ticket against its permitted scope, syntax, and tests.
        """
        logger.info("Independent verifier checking ticket [%s]: %s", ticket.id, ticket.title)
        modified_files = self._get_current_modified_files()

        # 1. Scope Boundary Check
        scope_violations: list[str] = []
        if ticket.target_files:
            norm_targets = {Path(t).as_posix().lower() for t in ticket.target_files}
            baseline_mod = {Path(b).as_posix().lower() for b in (self.baseline.pre_existing_git_changes if self.baseline else [])}

            for f in modified_files:
                f_norm = Path(f).as_posix().lower()
                # Ignore files that were already modified in the baseline
                if f_norm in baseline_mod:
                    continue
                # Ignore transient test outputs or logs
                if f_norm.endswith((".log", ".jsonl", ".pyc")) or "logs/" in f_norm:
                    continue
                if f_norm not in norm_targets:
                    # Check if prefix matches
                    matched_prefix = any(f_norm.startswith(target) for target in norm_targets)
                    if not matched_prefix:
                        scope_violations.append(f)

        # 2. Syntax Validation on Modified Files
        syntax_errors: list[str] = []
        for f in modified_files:
            if f.endswith(".py"):
                res = execute_check_syntax({"filepath": f}, workspace_root=self.workspace_root)
                if "SyntaxError" in res or "Error" in res:
                    syntax_errors.append(f"{f}: {res.strip()}")

        # 3. Verification Commands Execution
        commands_run: list[dict[str, Any]] = []
        test_failures: list[str] = []
        regressions: list[str] = []

        cmds_to_run = list(ticket.verification_commands)
        if not cmds_to_run and self.baseline and self.baseline.detected_test_command:
            cmds_to_run.append(self.baseline.detected_test_command)

        for cmd in cmds_to_run:
            if not cmd or not cmd.strip():
                continue
            logger.info("Running verification command: %s", cmd)
            out = execute_run_command({"command": cmd, "timeout_seconds": 60}, workspace_root=self.workspace_root)
            exit_code = 0
            for line in out.splitlines():
                if "Command failed with exit code" in line or "Exit code:" in line:
                    try:
                        exit_code = int(line.split(":")[-1].strip())
                    except ValueError:
                        exit_code = 1

            for line in out.splitlines():
                if "FAILED" in line or "FAIL " in line or "AssertionError" in line:
                    fail_snippet = line.strip()[:120]
                    test_failures.append(fail_snippet)
                    # Check if this failure was already present in the baseline
                    is_preexisting = False
                    if self.baseline and not self.baseline.test_baseline.success:
                        for base_fail in self.baseline.test_baseline.failing_tests:
                            if fail_snippet[:40] in base_fail or base_fail[:40] in fail_snippet:
                                is_preexisting = True
                                break
                    if not is_preexisting:
                        regressions.append(fail_snippet)

            commands_run.append({
                "command": cmd,
                "exit_code": exit_code,
                "output_snippet": out[:400],
            })

        # 4. Git diff snippet
        diff_snippet = execute_git_diff(workspace_root=self.workspace_root)[:1500]

        # Determine overall success
        has_cmd_failures = any(c["exit_code"] != 0 for c in commands_run)
        success = (
            len(scope_violations) == 0
            and len(syntax_errors) == 0
            and len(regressions) == 0
            and not has_cmd_failures
        )

        summary_parts = []
        if success:
            summary_parts.append(f"Verification PASSED for ticket {ticket.id}.")
        else:
            summary_parts.append(f"Verification FAILED for ticket {ticket.id}:")
            if scope_violations:
                summary_parts.append(f"  Scope violations ({len(scope_violations)}): {scope_violations}")
            if syntax_errors:
                summary_parts.append(f"  Syntax errors ({len(syntax_errors)}): {syntax_errors}")
            if regressions:
                summary_parts.append(f"  New test regressions ({len(regressions)}): {regressions}")
            elif has_cmd_failures:
                summary_parts.append("  Verification command exited with non-zero status.")

        summary = "\n".join(summary_parts)
        logger.info(summary)

        return VerificationResult(
            success=success,
            ticket_id=ticket.id,
            commands_run=commands_run,
            git_diff_snippet=diff_snippet,
            modified_files=modified_files,
            scope_violations=scope_violations,
            syntax_errors=syntax_errors,
            test_failures=test_failures,
            regressions=regressions,
            summary=summary,
        )

    def verify_aggregate(self) -> VerificationResult:
        """Run aggregate project-level checks across the entire workspace."""
        modified_files = self._get_current_modified_files()
        syntax_errors: list[str] = []
        for f in modified_files:
            if f.endswith(".py"):
                res = execute_check_syntax({"filepath": f}, workspace_root=self.workspace_root)
                if "SyntaxError" in res or "Error" in res:
                    syntax_errors.append(f"{f}: {res.strip()}")

        commands_run: list[dict[str, Any]] = []
        test_failures: list[str] = []
        regressions: list[str] = []

        if self.baseline and self.baseline.detected_test_command:
            cmd = self.baseline.detected_test_command
            out = execute_run_command({"command": cmd, "timeout_seconds": 90}, workspace_root=self.workspace_root)
            exit_code = 0
            for line in out.splitlines():
                if "Command failed with exit code" in line or "Exit code:" in line:
                    try:
                        exit_code = int(line.split(":")[-1].strip())
                    except ValueError:
                        exit_code = 1
            for line in out.splitlines():
                if "FAILED" in line or "FAIL " in line or "AssertionError" in line:
                    fail_snippet = line.strip()[:120]
                    test_failures.append(fail_snippet)
                    is_preexisting = False
                    if self.baseline and not self.baseline.test_baseline.success:
                        for base_fail in self.baseline.test_baseline.failing_tests:
                            if fail_snippet[:40] in base_fail or base_fail[:40] in fail_snippet:
                                is_preexisting = True
                                break
                    if not is_preexisting:
                        regressions.append(fail_snippet)

            commands_run.append({
                "command": cmd,
                "exit_code": exit_code,
                "output_snippet": out[:400],
            })

        has_cmd_failures = any(c["exit_code"] != 0 for c in commands_run)
        success = (
            len(syntax_errors) == 0
            and len(regressions) == 0
            and not has_cmd_failures
        )

        diff_snippet = execute_git_diff(workspace_root=self.workspace_root)[:1500]
        summary = "Aggregate verification PASSED." if success else f"Aggregate verification FAILED (regressions: {len(regressions)}, syntax errors: {len(syntax_errors)})."

        return VerificationResult(
            success=success,
            commands_run=commands_run,
            git_diff_snippet=diff_snippet,
            modified_files=modified_files,
            syntax_errors=syntax_errors,
            test_failures=test_failures,
            regressions=regressions,
            summary=summary,
        )

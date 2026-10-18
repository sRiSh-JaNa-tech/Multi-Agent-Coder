"""
Baseline Runner for Pre-Flight Repository Discovery.
Runs existing test suites, captures syntax baselines, and records pre-existing Git state
so the autonomous system distinguishes existing defects from introduced regressions.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import time
from typing import Any

from ..common.logging_config import setup_logging
from ..tools.execution import execute_run_command, execute_git_status, execute_check_syntax

logger = setup_logging(__name__)


@dataclass
class BaselineTestResult:
    """Record of test execution on an unmodified repository."""
    executed: bool = False
    command: str = ""
    exit_code: int = 0
    passed_count: int = 0
    failed_count: int = 0
    duration_seconds: float = 0.0
    output_snippet: str = ""
    failing_tests: list[str] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "executed": self.executed,
            "command": self.command,
            "exit_code": self.exit_code,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "duration_seconds": round(self.duration_seconds, 2),
            "output_snippet": self.output_snippet[:500],
            "failing_tests": self.failing_tests,
            "success": self.success,
        }


@dataclass
class RepositoryBaseline:
    """Complete baseline snapshot of a repository prior to autonomous planning."""
    workspace_root: Path
    project_type: str = "unknown"
    manifests_found: list[str] = field(default_factory=list)
    pre_existing_git_changes: list[str] = field(default_factory=list)
    syntax_error_files: list[str] = field(default_factory=list)
    test_baseline: BaselineTestResult = field(default_factory=BaselineTestResult)
    detected_test_command: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_root": str(self.workspace_root),
            "project_type": self.project_type,
            "manifests_found": self.manifests_found,
            "pre_existing_git_changes": self.pre_existing_git_changes,
            "syntax_error_files": self.syntax_error_files,
            "test_baseline": self.test_baseline.to_dict(),
            "detected_test_command": self.detected_test_command,
            "timestamp": self.timestamp,
        }


def detect_project_type_and_test_command(workspace_root: Path | str) -> tuple[str, str | None, list[str]]:
    """Detect whether repo is Python, Node.js, Go, Rust, etc., and infer standard test command."""
    root = Path(workspace_root).resolve()
    manifests: list[str] = []
    project_type = "unknown"
    test_cmd = None

    if (root / "package.json").is_file():
        manifests.append("package.json")
        project_type = "nodejs"
        try:
            pkg_data = json.loads((root / "package.json").read_text(encoding="utf-8"))
            scripts = pkg_data.get("scripts", {})
            if "test" in scripts and "no test specified" not in scripts["test"].lower():
                test_cmd = "npm test"
        except Exception:
            pass

        # Check for standalone test files if npm test is generic or absent
        if not test_cmd:
            tests_dir = root / "tests"
            if tests_dir.is_dir():
                test_files = [f.name for f in tests_dir.glob("*.test.js")]
                if "e2e.test.js" in test_files:
                    test_cmd = "node tests/e2e.test.js"
                elif test_files:
                    test_cmd = f"node tests/{test_files[0]}"

    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file() or (root / "requirements.txt").is_file():
        if (root / "pyproject.toml").is_file():
            manifests.append("pyproject.toml")
        if (root / "setup.py").is_file():
            manifests.append("setup.py")
        if (root / "requirements.txt").is_file():
            manifests.append("requirements.txt")
        project_type = "python"
        test_cmd = test_cmd or "pytest"

    if (root / "Cargo.toml").is_file():
        manifests.append("Cargo.toml")
        project_type = "rust"
        test_cmd = test_cmd or "cargo test"

    if (root / "go.mod").is_file():
        manifests.append("go.mod")
        project_type = "go"
        test_cmd = test_cmd or "go test ./..."

    return project_type, test_cmd, manifests


def capture_git_baseline(workspace_root: Path | str) -> list[str]:
    """Capture modified and untracked files present BEFORE the agent begins work."""
    status_output = execute_git_status(workspace_root=workspace_root)
    changes = []
    for line in status_output.splitlines():
        line = line.strip()
        if not line or line.startswith("Clean working tree") or line.startswith("No changes"):
            continue
        if line.startswith("modified:") or line.startswith("both modified:"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                changes.append(parts[1].strip().replace("\\", "/"))
        else:
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                changes.append(parts[1].strip().replace("\\", "/"))
    return changes


def run_baseline_tests(
    workspace_root: Path | str,
    test_command: str | None = None,
    timeout_s: int = 60
) -> BaselineTestResult:
    """Execute existing test command in the workspace to establish ground truth."""
    if not test_command:
        return BaselineTestResult(executed=False)

    start_time = time.time()
    try:
        raw_result = execute_run_command(
            {"command": test_command, "timeout_seconds": timeout_s},
            workspace_root=workspace_root
        )
        duration = time.time() - start_time
        lines = raw_result.splitlines()

        # Parse exit code
        exit_code = 0
        for line in lines:
            if "Command failed with exit code" in line or "Exit code:" in line:
                try:
                    exit_code = int(line.split(":")[-1].strip())
                except ValueError:
                    exit_code = 1

        failing_tests = []
        for line in lines:
            if "FAILED" in line or "FAIL " in line or "AssertionError" in line:
                failing_tests.append(line.strip()[:100])

        success = (exit_code == 0) and (len(failing_tests) == 0)
        return BaselineTestResult(
            executed=True,
            command=test_command,
            exit_code=exit_code,
            duration_seconds=duration,
            output_snippet=raw_result[:800],
            failing_tests=failing_tests[:10],
            success=success,
        )
    except Exception as e:
        logger.warning("Baseline test execution failed: %s", e)
        return BaselineTestResult(
            executed=True,
            command=test_command,
            exit_code=-1,
            output_snippet=str(e),
            success=False,
        )


def capture_repository_baseline(
    workspace_root: Path | str,
    run_tests: bool = True
) -> RepositoryBaseline:
    """Run full baseline assessment on the target repository."""
    root = Path(workspace_root).resolve()
    project_type, test_cmd, manifests = detect_project_type_and_test_command(root)
    git_changes = capture_git_baseline(root)

    test_res = BaselineTestResult(executed=False)
    if run_tests and test_cmd:
        logger.info("Executing baseline test command '%s' in %s...", test_cmd, root)
        test_res = run_baseline_tests(root, test_cmd)
        if test_res.success:
            logger.info("Baseline tests PASSED cleanly.")
        else:
            logger.warning("Baseline tests FAILED (%d failures identified before changes).", len(test_res.failing_tests))

    return RepositoryBaseline(
        workspace_root=root,
        project_type=project_type,
        manifests_found=manifests,
        pre_existing_git_changes=git_changes,
        test_baseline=test_res,
        detected_test_command=test_cmd,
    )

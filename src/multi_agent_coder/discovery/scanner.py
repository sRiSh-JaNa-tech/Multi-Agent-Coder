"""
Static and Evidence-Driven Repository Scanner.
Inspects a target repository for syntax errors, baseline test failures,
code smells, security risks, placeholder implementations, and missing requirements.
Produces structured findings for the autonomous planner.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
from typing import Any

from .baseline import RepositoryBaseline, capture_repository_baseline
from .findings import (
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingRegistry,
    FindingSeverity,
)
from ..common.logging_config import setup_logging

logger = setup_logging(__name__)

# Patterns for discovering suspicious implementations, bugs, or debt
TODO_PATTERN = re.compile(r"(?i)\b(TODO|FIXME|XXX|HACK|BUG)\b[:\s]*(.*)")
PLACEHOLDER_PATTERN = re.compile(
    r"(?i)(raise\s+NotImplementedError|return\s+(None|null|nil)\s*;\s*//\s*(stub|placeholder|todo)|\bpass\b\s*#\s*todo)"
)
HARDCODED_SECRET_PATTERN = re.compile(
    r"""(?i)(?:api_key|secret|password|auth_token|jwt_secret)\s*=\s*['"][A-Za-z0-9_\-\.]{12,}['"]"""
)
INSECURE_EVAL_PATTERN = re.compile(r"""\b(eval|exec)\s*\(""")
EMPTY_EXCEPT_PATTERN = re.compile(r"""except(\s+Exception)?:\s*\n\s*pass\b""")

# Skip scanning these noisy directories
IGNORE_DIRS = frozenset({
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".agents",
})


class RepositoryScanner:
    """
    Automated discovery engine that statically and deterministically analyzes
    a workspace before planning, turning detected anomalies into structured findings.
    """

    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def scan(
        self,
        objective: str = "",
        baseline: RepositoryBaseline | None = None,
        run_baseline_tests: bool = True,
    ) -> tuple[FindingRegistry, RepositoryBaseline]:
        """
        Execute full proactive repository discovery.
        Returns:
            (FindingRegistry containing prioritized findings, RepositoryBaseline snapshot)
        """
        registry = FindingRegistry()

        # Step 1: Capture or use provided baseline
        if baseline is None:
            baseline = capture_repository_baseline(self.workspace_root, run_tests=run_baseline_tests)

        # Step 2: Convert failing baseline tests into CONFIRMED findings
        if baseline.test_baseline.executed and not baseline.test_baseline.success:
            for fail_line in baseline.test_baseline.failing_tests:
                finding = Finding.create(
                    title=f"Failing test: {fail_line[:60]}",
                    description=(
                        f"The repository baseline test suite failed before any changes were made. "
                        f"Failure detail: {fail_line}"
                    ),
                    category=FindingCategory.DEFECT,
                    confidence=FindingConfidence.CONFIRMED,
                    severity=FindingSeverity.HIGH,
                    evidence=baseline.test_baseline.output_snippet[:600],
                    impact="Application test suite does not pass; functionality or regression protection is broken.",
                    suggested_remediation=f"Investigate failure in '{fail_line}' and fix underlying implementation.",
                    verification_strategy=baseline.detected_test_command or "run test suite",
                )
                registry.add(finding)

        # Step 3: Check Python syntax on all .py files
        self._scan_python_syntax(registry)

        # Step 4: Scan for code patterns (placeholders, security, empty exceptions)
        self._scan_source_patterns(registry)

        # Step 5: Check project-level structural requirements (test files, CI, manifests)
        self._scan_project_structure(registry, baseline)

        logger.info(
            "Proactive discovery completed for %s. Found %d structured findings.",
            self.workspace_root,
            len(registry),
        )
        return registry, baseline

    def _scan_python_syntax(self, registry: FindingRegistry) -> None:
        """Parse all Python files to detect syntax errors deterministically."""
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                if file.endswith(".py"):
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(self.workspace_root).as_posix()
                    try:
                        content = full_path.read_text(encoding="utf-8", errors="ignore")
                        ast.parse(content, filename=rel_path)
                    except SyntaxError as syn_err:
                        finding = Finding.create(
                            title=f"SyntaxError in {rel_path}: {syn_err.msg}",
                            description=(
                                f"File contains invalid Python syntax at line {syn_err.lineno}: {syn_err.text}"
                            ),
                            category=FindingCategory.DEFECT,
                            confidence=FindingConfidence.CONFIRMED,
                            severity=FindingSeverity.CRITICAL,
                            file_path=rel_path,
                            line_number=syn_err.lineno,
                            evidence=f"SyntaxError: {syn_err.msg} at line {syn_err.lineno}",
                            impact="File cannot be imported or executed at runtime.",
                            suggested_remediation="Correct the syntax error.",
                            verification_strategy=f"python -m py_compile {rel_path}",
                        )
                        registry.add(finding)
                    except Exception:
                        pass

    def _scan_source_patterns(self, registry: FindingRegistry) -> None:
        """Scan source files for placeholders, dangerous functions, and empty catches."""
        extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs"}
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                ext = Path(file).suffix.lower()
                if ext not in extensions:
                    continue

                full_path = Path(root) / file
                rel_path = full_path.relative_to(self.workspace_root).as_posix()

                try:
                    content = full_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                lines = content.splitlines()
                for i, line in enumerate(lines, 1):
                    # Check placeholders / NotImplementedError
                    if PLACEHOLDER_PATTERN.search(line):
                        registry.add(Finding.create(
                            title=f"Incomplete placeholder implementation in {rel_path}",
                            description=f"Placeholder or NotImplementedError found: '{line.strip()}'",
                            category=FindingCategory.DEFECT,
                            confidence=FindingConfidence.HIGH,
                            severity=FindingSeverity.MEDIUM,
                            file_path=rel_path,
                            line_number=i,
                            evidence=f"Line {i}: {line.strip()}",
                            impact="Unimplemented code path will fail if reached at runtime.",
                            suggested_remediation="Provide complete implementation for the placeholder.",
                            verification_strategy="Run unit tests covering this function.",
                        ))

                    # Check hardcoded secrets
                    if HARDCODED_SECRET_PATTERN.search(line):
                        registry.add(Finding.create(
                            title=f"Potential hardcoded credential in {rel_path}",
                            description=f"Possible secret or API key assignment found at line {i}.",
                            category=FindingCategory.SECURITY,
                            confidence=FindingConfidence.MEDIUM,
                            severity=FindingSeverity.HIGH,
                            file_path=rel_path,
                            line_number=i,
                            evidence=f"Line {i}: [REDACTED SECRET ASSIGNMENT]",
                            impact="Hardcoded credentials risk exposure in version control.",
                            suggested_remediation="Load credential from environment variables instead.",
                            verification_strategy="Verify secrets are loaded via os.getenv / process.env.",
                        ))

                    # Check eval/exec usage
                    if ext == ".py" and INSECURE_EVAL_PATTERN.search(line) and not line.strip().startswith("#"):
                        registry.add(Finding.create(
                            title=f"Insecure dynamic code execution in {rel_path}",
                            description=f"Usage of eval() or exec() found at line {i}.",
                            category=FindingCategory.SECURITY,
                            confidence=FindingConfidence.HIGH,
                            severity=FindingSeverity.HIGH,
                            file_path=rel_path,
                            line_number=i,
                            evidence=f"Line {i}: {line.strip()}",
                            impact="Dynamic evaluation can lead to arbitrary code execution vulnerabilities.",
                            suggested_remediation="Replace dynamic evaluation with safe parsing or AST traversal.",
                            verification_strategy="Audit inputs to ensure no untrusted evaluation occurs.",
                        ))

                    # Check TODO / FIXME
                    m = TODO_PATTERN.search(line)
                    if m and not line.strip().startswith(("#!", "/*", "*/")):
                        tag = m.group(1).upper()
                        todo_text = m.group(2).strip()
                        if todo_text and len(todo_text) > 4:
                            registry.add(Finding.create(
                                title=f"{tag} comment in {rel_path}: {todo_text[:40]}",
                                description=f"{tag} noted in code: '{todo_text}'",
                                category=FindingCategory.CODE_SMELL if tag == "TODO" else FindingCategory.DEFECT,
                                confidence=FindingConfidence.HIGH,
                                severity=FindingSeverity.LOW if tag == "TODO" else FindingSeverity.MEDIUM,
                                file_path=rel_path,
                                line_number=i,
                                evidence=f"Line {i}: {line.strip()}",
                                impact=f"Documented technical debt or defect: {todo_text}",
                                suggested_remediation=f"Address {tag}: {todo_text}",
                                verification_strategy="Verify code behavior with relevant test.",
                            ))

    def _scan_project_structure(
        self,
        registry: FindingRegistry,
        baseline: RepositoryBaseline,
    ) -> None:
        """Check for structural gaps like missing tests, missing documentation, or broken setup."""
        # Check if project lacks tests entirely
        has_tests = False
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                if "test" in file.lower() or file.endswith(("_test.py", ".test.js", ".spec.js", "_test.go")):
                    has_tests = True
                    break
            if has_tests:
                break

        if not has_tests:
            registry.add(Finding.create(
                title="Repository lacks automated tests",
                description="No test directory or test files detected in the project.",
                category=FindingCategory.TEST_GAP,
                confidence=FindingConfidence.HIGH,
                severity=FindingSeverity.MEDIUM,
                impact="Code changes cannot be automatically verified against regressions.",
                suggested_remediation="Create a test suite covering critical paths.",
                verification_strategy="Run test runner after creating test cases.",
            ))


def run_discovery(
    workspace_root: Path | str,
    objective: str = "",
    run_baseline_tests: bool = True,
) -> tuple[FindingRegistry, RepositoryBaseline]:
    """Convenience helper to run discovery on a workspace."""
    scanner = RepositoryScanner(workspace_root)
    return scanner.scan(objective=objective, run_baseline_tests=run_baseline_tests)

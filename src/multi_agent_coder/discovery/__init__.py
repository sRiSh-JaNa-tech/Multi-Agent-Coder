"""
Discovery package for autonomous multi-agent software engineering.
Exports structured findings, baseline assessment, and proactive repository scanner.
"""

from .findings import (
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingRegistry,
    FindingSeverity,
)
from .baseline import (
    BaselineTestResult,
    RepositoryBaseline,
    capture_git_baseline,
    capture_repository_baseline,
    detect_project_type_and_test_command,
    run_baseline_tests,
)
from .scanner import RepositoryScanner, run_discovery

__all__ = [
    "Finding",
    "FindingCategory",
    "FindingConfidence",
    "FindingRegistry",
    "FindingSeverity",
    "BaselineTestResult",
    "RepositoryBaseline",
    "capture_git_baseline",
    "capture_repository_baseline",
    "detect_project_type_and_test_command",
    "run_baseline_tests",
    "RepositoryScanner",
    "run_discovery",
]

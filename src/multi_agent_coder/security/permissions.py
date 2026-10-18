"""
Security Context and Fine-Grained Capability-Based Permissions.
Enforces workspace path containment via os.path.commonpath and restricts
destructive terminal commands.
"""

from enum import Enum, auto
import os
from pathlib import Path
import re


class AgentCapability(Enum):
    READ_ONLY = auto()
    WORKSPACE_WRITE = auto()
    EXECUTE_TESTS = auto()
    GIT_WORKTREE_WRITE = auto()
    ADMIN = auto()


class SecurityContext:
    def __init__(self, capabilities: list[AgentCapability] | set[AgentCapability], workspace_root: str | Path):
        self.capabilities = set(capabilities)
        self.workspace_root = str(Path(workspace_root).resolve())

    @classmethod
    def for_worker(cls, workspace_root: str | Path) -> "SecurityContext":
        """Standard worker capability set: read, write within workspace, execute tests/tools."""
        return cls(
            capabilities={
                AgentCapability.READ_ONLY,
                AgentCapability.WORKSPACE_WRITE,
                AgentCapability.EXECUTE_TESTS,
                AgentCapability.GIT_WORKTREE_WRITE,
            },
            workspace_root=workspace_root,
        )

    @classmethod
    def for_tester(cls, workspace_root: str | Path) -> "SecurityContext":
        """QA tester capability set: read-only on repo files, execute tests/checkers."""
        return cls(
            capabilities={
                AgentCapability.READ_ONLY,
                AgentCapability.EXECUTE_TESTS,
            },
            workspace_root=workspace_root,
        )

    @classmethod
    def for_admin(cls, workspace_root: str | Path) -> "SecurityContext":
        """Unrestricted admin context."""
        return cls(
            capabilities=set(AgentCapability),
            workspace_root=workspace_root,
        )

    def has_capability(self, capability: AgentCapability) -> bool:
        return capability in self.capabilities or AgentCapability.ADMIN in self.capabilities

    def is_path_within_workspace(self, filepath: str | Path) -> bool:
        try:
            abs_filepath = str(Path(filepath).resolve())
            abs_workspace_root = self.workspace_root
            common = os.path.commonpath([abs_workspace_root, abs_filepath])
            return common == abs_workspace_root
        except (ValueError, OSError):
            return False

    def assert_path_within_workspace(self, filepath: str | Path) -> None:
        if not self.is_path_within_workspace(filepath):
            raise PermissionError(
                f"Operation on path '{filepath}' is outside the workspace root '{self.workspace_root}'"
            )

    def assert_capability(self, capability: AgentCapability) -> None:
        if not self.has_capability(capability):
            raise PermissionError(f"Operation requires capability '{capability.name}'")

    def assert_destructive_command(self, command: str) -> None:
        destructive_patterns = [
            r"\brm\s+-rf\b",
            r"\bgit\s+push\s+--force\b",
            r"\bmkfs\b",
            r"\bdd\s+if=.*of=.*",
            r"\bfdisk\b",
            r"\bparted\b",
            r"\bformat\b",
            r"\breboot\b",
            r"\bshutdown\b",
        ]
        for pattern in destructive_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                if not self.has_capability(AgentCapability.ADMIN):
                    raise PermissionError(f"Destructive command '{command}' requires ADMIN capability")

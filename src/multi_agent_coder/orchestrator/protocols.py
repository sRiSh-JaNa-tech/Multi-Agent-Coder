"""
Typed Communication Protocols & Structured Agent Reports.
Defines schemas and parsers for agent status reports, finding discoveries,
and verification outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
import re
from typing import Any


@dataclass
class FindingReport:
    title: str
    description: str = ""
    file_path: str | None = None
    evidence: str = ""
    category: str = "defect"  # defect, test_failure, security, design, documentation
    confidence: str = "high"  # low, medium, high, confirmed
    severity: str = "high"    # low, medium, high, critical

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentReport:
    status: str                                  # RESOLVED, FAILED, BLOCKED
    summary: str
    files_modified: list[str] = field(default_factory=list)
    tests_executed: list[dict[str, Any]] = field(default_factory=list)
    discovered_findings: list[FindingReport] = field(default_factory=list)
    verification_passed: bool = False
    error: str | None = None
    tool_call_count: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["discovered_findings"] = [f.to_dict() for f in self.discovered_findings]
        return data

    @classmethod
    def from_text(cls, text: str) -> "AgentReport":
        """
        Parse structured agent report from agent output text.
        Supports JSON markdown blocks or regex parsing of standard status reports.
        """
        # 1. Try parsing JSON block if present
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if "status" in data or "Agent Status" in data:
                    findings = [
                        FindingReport(**f) if isinstance(f, dict) else FindingReport(title=str(f))
                        for f in data.get("discovered_findings", data.get("findings", []))
                    ]
                    return cls(
                        status=data.get("status", data.get("Agent Status", "RESOLVED")),
                        summary=data.get("summary", data.get("Resolution Summary", "")),
                        files_modified=data.get("files_modified", data.get("Files Changed", [])),
                        tests_executed=data.get("tests_executed", []),
                        discovered_findings=findings,
                        verification_passed=bool(data.get("verification_passed", True)),
                        error=data.get("error"),
                    )
            except Exception:
                pass

        # 2. Parse standard markdown [Agent Status: RESOLVED]
        status = "RESOLVED" if "[Agent Status: RESOLVED]" in text else ("FAILED" if "[Agent Status: FAILED]" in text else "COMPLETED")
        
        # Extract files changed
        files_modified = []
        files_match = re.search(r"\*\*Files Changed\*\*:\s*([^\n]+)", text)
        if files_match:
            raw_files = files_match.group(1)
            files_modified = [f.strip(" `*") for f in re.split(r"[,;]", raw_files) if f.strip(" `*")]

        # Extract summary
        summary = text.strip()
        summary_match = re.search(r"\*\*Resolution Summary\*\*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)", text)
        if summary_match:
            summary = summary_match.group(1).strip()
        elif len(summary) > 300:
            summary = summary[:300] + "..."

        return cls(
            status=status,
            summary=summary,
            files_modified=files_modified,
            verification_passed=(status == "RESOLVED"),
        )

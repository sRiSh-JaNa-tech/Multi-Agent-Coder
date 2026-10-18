"""
Structured Finding Model and Registry for Proactive Repository Discovery.
Defines evidence-backed findings with severity, confidence, line citations, and remediation strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import re
import time
from typing import Any


class FindingCategory(str, Enum):
    DEFECT = "defect"
    SECURITY = "security"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    ARCHITECTURE = "architecture"
    TEST_GAP = "test_gap"
    CODE_SMELL = "code_smell"


class FindingConfidence(str, Enum):
    CONFIRMED = "CONFIRMED"  # Backed by failing test, syntax error, or direct execution proof
    HIGH = "HIGH"            # Static analysis pattern with unambiguous evidence
    MEDIUM = "MEDIUM"        # Heuristic detection with moderate likelihood
    LOW = "LOW"              # Speculative or minor stylistic observation


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"    # System crash, security vulnerability, data loss
    HIGH = "HIGH"            # Broken core flow, major regression, missing validation
    MEDIUM = "MEDIUM"        # Performance bottleneck, poor error handling, unhandled edge case
    LOW = "LOW"              # Missing test coverage, code smell, minor TODO
    INFO = "INFO"            # Informational architectural observation


@dataclass
class Finding:
    """An evidence-backed defect, vulnerability, or improvement discovered in a repository."""
    id: str
    title: str
    description: str
    category: FindingCategory = FindingCategory.DEFECT
    confidence: FindingConfidence = FindingConfidence.HIGH
    severity: FindingSeverity = FindingSeverity.MEDIUM
    file_path: str | None = None
    line_number: int | None = None
    evidence: str = ""
    impact: str = ""
    suggested_remediation: str = ""
    verification_strategy: str = ""
    human_approval_required: bool = False
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        category: FindingCategory | str = FindingCategory.DEFECT,
        confidence: FindingConfidence | str = FindingConfidence.HIGH,
        severity: FindingSeverity | str = FindingSeverity.MEDIUM,
        file_path: str | None = None,
        line_number: int | None = None,
        evidence: str = "",
        impact: str = "",
        suggested_remediation: str = "",
        verification_strategy: str = "",
        human_approval_required: bool = False,
        custom_id: str | None = None,
    ) -> "Finding":
        if isinstance(category, str):
            try:
                category = FindingCategory(category.lower())
            except ValueError:
                category = FindingCategory.DEFECT

        if isinstance(confidence, str):
            try:
                confidence = FindingConfidence(confidence.upper())
            except ValueError:
                confidence = FindingConfidence.MEDIUM

        if isinstance(severity, str):
            try:
                severity = FindingSeverity(severity.upper())
            except ValueError:
                severity = FindingSeverity.MEDIUM

        if not custom_id:
            fp_slug = (file_path or "sys").replace("\\", "/").split("/")[-1].split(".")[0][:8]
            cat_slug = category.value[:3].upper()
            content_hash = hashlib.md5(f"{title}:{file_path}:{line_number}".encode()).hexdigest()[:4].upper()
            finding_id = f"FIND-{cat_slug}-{fp_slug}-{content_hash}"
        else:
            finding_id = custom_id

        return cls(
            id=finding_id,
            title=title.strip(),
            description=description.strip(),
            category=category,
            confidence=confidence,
            severity=severity,
            file_path=file_path.replace("\\", "/") if file_path else None,
            line_number=line_number,
            evidence=evidence.strip(),
            impact=impact.strip(),
            suggested_remediation=suggested_remediation.strip(),
            verification_strategy=verification_strategy.strip(),
            human_approval_required=human_approval_required,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "confidence": self.confidence.value,
            "severity": self.severity.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "evidence": self.evidence,
            "impact": self.impact,
            "suggested_remediation": self.suggested_remediation,
            "verification_strategy": self.verification_strategy,
            "human_approval_required": self.human_approval_required,
            "created_at": self.created_at,
        }

    @property
    def fingerprint(self) -> str:
        """Normalized fingerprint for deduplication."""
        norm_title = re.sub(r"\W+", "_", self.title.lower()).strip("_")[:40]
        fp = self.file_path or "any"
        line = self.line_number or 0
        return f"{self.category.value}:{fp}:{line}:{norm_title}"


class FindingRegistry:
    """Thread-safe collection of repository findings with deduplication and priority sorting."""

    SEVERITY_WEIGHTS = {
        FindingSeverity.CRITICAL: 100,
        FindingSeverity.HIGH: 75,
        FindingSeverity.MEDIUM: 50,
        FindingSeverity.LOW: 25,
        FindingSeverity.INFO: 10,
    }

    CONFIDENCE_WEIGHTS = {
        FindingConfidence.CONFIRMED: 1.0,
        FindingConfidence.HIGH: 0.85,
        FindingConfidence.MEDIUM: 0.6,
        FindingConfidence.LOW: 0.3,
    }

    def __init__(self) -> None:
        self._findings: dict[str, Finding] = {}
        self._fingerprints: set[str] = set()

    def add(self, finding: Finding) -> bool:
        """Add finding if not already present by fingerprint. Returns True if added."""
        fp = finding.fingerprint
        if fp in self._fingerprints:
            return False
        if finding.id in self._findings:
            # Generate alternate ID
            finding.id = f"{finding.id}-{len(self._findings)}"
        self._findings[finding.id] = finding
        self._fingerprints.add(fp)
        return True

    def get(self, finding_id: str) -> Finding | None:
        return self._findings.get(finding_id)

    def list_all(self) -> list[Finding]:
        return list(self._findings.values())

    def prioritized(self) -> list[Finding]:
        """Return findings sorted by highest severity and confidence score first."""
        def score(f: Finding) -> float:
            sev = self.SEVERITY_WEIGHTS.get(f.severity, 20)
            conf = self.CONFIDENCE_WEIGHTS.get(f.confidence, 0.5)
            return sev * conf

        return sorted(self._findings.values(), key=score, reverse=True)

    def filter_by_category(self, category: FindingCategory | str) -> list[Finding]:
        target = category if isinstance(category, FindingCategory) else FindingCategory(str(category).lower())
        return [f for f in self._findings.values() if f.category == target]

    def __len__(self) -> int:
        return len(self._findings)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [f.to_dict() for f in self.prioritized()]

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict_list(), indent=indent)

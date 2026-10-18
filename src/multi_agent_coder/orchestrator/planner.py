"""
Evidence-Driven Planning Engine for Autonomous Multi-Agent Systems.
Translates repository discovery findings, baseline results, and user objectives
into validated, dependency-aware tickets with strict scopes and verification criteria.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
from google import genai
from google.genai import types

from ..discovery.findings import Finding, FindingCategory, FindingConfidence, FindingRegistry, FindingSeverity
from ..discovery.baseline import RepositoryBaseline
from .ticket import Ticket, TicketDAG, TicketStatus
from ..common.logging_config import setup_logging
from ..common.token_budget import TokenBudget, usage_from_response

logger = setup_logging(__name__)


class InvalidPlanError(Exception):
    """Raised when an execution plan has unresolvable dependency cycles or invalid structure."""
    pass


class EvidenceDrivenPlanner:
    """
    Synthesizes repository evidence, baseline status, and the user objective
    to produce structured, verified work tickets.
    """

    def __init__(
        self,
        workspace_root: Path | str,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        client: genai.Client | None = None,
        token_budget: TokenBudget | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.model = model
        self.api_key = api_key or ""
        self._client = client
        self.token_budget = token_budget

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        return self._client

    def _is_finding_relevant_to_objective(self, finding: Finding, objective: str) -> bool:
        """Check if finding is directly mentioned or relevant to the objective text."""
        if not objective:
            return False
        obj_lower = objective.lower()
        if finding.file_path:
            fp_parts = Path(finding.file_path).parts
            if any(part.lower() in obj_lower for part in fp_parts if len(part) > 2):
                return True
        words = [w.lower() for w in re.findall(r"\w+", finding.title) if len(w) > 3]
        if any(w in obj_lower for w in words):
            return True
        return False

    def plan(
        self,
        objective: str,
        findings: FindingRegistry,
        baseline: RepositoryBaseline,
        previous_tickets: list[Ticket] | None = None,
        max_tickets: int = 8,
    ) -> list[Ticket]:
        """
        Generate an evidence-backed task plan based on discovery findings, baseline, and objective.
        """
        logger.info("Planner generating tickets for objective: '%s' (%d findings available)",
                    objective[:60], len(findings))

        prioritized = findings.prioritized()
        # Filter findings relevant to objective, confirmed defects, defects/security issues, and critical/high issues
        relevant_findings = [
            f for f in prioritized
            if f.confidence == FindingConfidence.CONFIRMED
            or f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
            or f.category in (FindingCategory.DEFECT, FindingCategory.SECURITY)
            or self._is_finding_relevant_to_objective(f, objective)
        ]
        if not relevant_findings:
            relevant_findings = prioritized[:6]
        else:
            relevant_findings = relevant_findings[:8]

        tickets: list[Ticket] = []

        # Attempt LLM-assisted evidence-driven planning if credentials available
        if self.api_key and not self.api_key.startswith("dummy"):
            try:
                tickets = self._plan_with_llm(
                    objective=objective,
                    findings=relevant_findings,
                    baseline=baseline,
                    previous_tickets=previous_tickets or [],
                    max_tickets=max_tickets,
                )
            except Exception as exc:
                logger.warning("LLM planning failed (%s); falling back to deterministic planning.", exc)

        # Fallback to deterministic evidence-driven plan
        if not tickets:
            tickets = self._plan_deterministic(
                objective=objective,
                findings=relevant_findings,
                baseline=baseline,
                previous_tickets=previous_tickets or [],
            )

        # Validate and repair tickets
        validated_tickets = self._validate_and_repair(tickets, baseline)
        logger.info("Planner produced %d validated tickets.", len(validated_tickets))
        return validated_tickets

    def _plan_with_llm(
        self,
        objective: str,
        findings: list[Finding],
        baseline: RepositoryBaseline,
        previous_tickets: list[Ticket],
        max_tickets: int,
    ) -> list[Ticket]:
        if self.token_budget:
            self.token_budget.check()

        findings_summary = [
            {
                "id": f.id,
                "title": f.title,
                "category": f.category.value,
                "severity": f.severity.value,
                "confidence": f.confidence.value,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "evidence": f.evidence[:200],
                "suggested_remediation": f.suggested_remediation,
            }
            for f in findings
        ]

        prompt = f"""You are the Principal Multi-Agent Planning Architect.
Synthesize the following objective and repository discovery findings into an actionable, dependency-aware task DAG.

OBJECTIVE:
{objective}

PROJECT CONTEXT:
Type: {baseline.project_type}
Detected Test Command: {baseline.detected_test_command or "None"}
Baseline Test Status: {"PASSED" if baseline.test_baseline.success else "FAILED (" + str(len(baseline.test_baseline.failing_tests)) + " failures)"}
Pre-existing Git changes: {baseline.pre_existing_git_changes or "None (Clean)"}

DISCOVERY FINDINGS:
{json.dumps(findings_summary, indent=2)}

REQUIREMENTS:
1. Every ticket must link to supporting finding_ids where applicable.
2. Specify exact target_files to constrain worker modification scope.
3. Every ticket must have clear acceptance_criteria and verification_commands.
4. Set up dependencies: implementation tickets first, followed by QA and test verification.
5. Limit plan to at most {max_tickets} high-value tickets.
6. Output ONLY a valid JSON array of ticket objects.

Format:
[
  {{
    "title": "Clear action-oriented title",
    "description": "Specific requirements and implementation instructions",
    "category": "analysis" | "coding" | "testing" | "refactor" | "security" | "docs",
    "finding_ids": ["FIND-..."],
    "target_files": ["src/..."],
    "acceptance_criteria": ["Criteria 1", "Criteria 2"],
    "verification_commands": ["pytest ..."],
    "depends_on": [],
    "risk_level": "low" | "medium" | "high" | "critical",
    "priority": 1
  }}
]"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are a Chief Software Systems Architect. Output valid JSON array only."
            ),
        )
        if self.token_budget:
            _, _, tot = usage_from_response(response)
            self.token_budget.record(tot)

        text = (response.text or "").strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []

        raw_list = json.loads(match.group(0))
        tickets: list[Ticket] = []
        for item in raw_list:
            ticket = Ticket.create(
                title=item.get("title", "Untitled Ticket"),
                description=item.get("description", ""),
                category=item.get("category", "coding"),
                depends_on=item.get("depends_on", []),
                finding_ids=item.get("finding_ids", []),
                target_files=item.get("target_files", []),
                acceptance_criteria=item.get("acceptance_criteria", []),
                verification_commands=item.get("verification_commands", []),
                risk_level=item.get("risk_level", "medium"),
                priority=int(item.get("priority", 2)),
                expected_deliverables=item.get("expected_deliverables", []),
            )
            tickets.append(ticket)
        return tickets

    def _plan_deterministic(
        self,
        objective: str,
        findings: list[Finding],
        baseline: RepositoryBaseline,
        previous_tickets: list[Ticket],
    ) -> list[Ticket]:
        """Deterministic rule-based planning when LLM is offline or test mode."""
        tickets: list[Ticket] = []
        coding_ticket_ids: list[str] = []

        # If we have confirmed findings (e.g. failing tests, syntax errors), build targeted tickets
        if findings:
            for f in findings:
                target_file = f.file_path or ""
                v_cmds = []
                if baseline.detected_test_command:
                    v_cmds.append(baseline.detected_test_command)
                if target_file.endswith(".py"):
                    v_cmds.append(f"python -m py_compile {target_file}")

                t = Ticket.create(
                    title=f"Fix {f.category.value}: {f.title[:50]}",
                    description=(
                        f"Remediate finding {f.id} in {f.file_path or 'codebase'}.\n"
                        f"Problem: {f.description}\n"
                        f"Evidence: {f.evidence}\n"
                        f"Remediation: {f.suggested_remediation}"
                    ),
                    category="coding" if f.category in (FindingCategory.DEFECT, FindingCategory.SECURITY) else "refactor",
                    finding_ids=[f.id],
                    target_files=[f.file_path] if f.file_path else [],
                    acceptance_criteria=[
                        f"Finding {f.id} is resolved with verifiable code modification.",
                        "No regressions introduced to existing functionality."
                    ],
                    verification_commands=v_cmds,
                    risk_level="high" if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH) else "medium",
                    priority=1 if f.confidence == FindingConfidence.CONFIRMED else 2,
                )
                tickets.append(t)
                coding_ticket_ids.append(t.id)
        else:
            # No findings discovered; plan exploration/implementation directly for objective
            t_work = Ticket.create(
                title=f"Execute: {objective[:45]}",
                description=f"Inspect workspace and implement necessary changes for: {objective}",
                category="coding",
                acceptance_criteria=[f"Objective '{objective}' fulfilled and verified."],
                verification_commands=[baseline.detected_test_command] if baseline.detected_test_command else [],
            )
            tickets.append(t_work)
            coding_ticket_ids.append(t_work.id)

        # Always append a final QA verification ticket depending on the implementation tickets
        v_cmd_qa = [baseline.detected_test_command] if baseline.detected_test_command else ["git diff"]
        t_qa = Ticket.create(
            title=f"QA Verification: Validate solution for '{objective[:35]}'",
            description=(
                f"Perform comprehensive independent verification of changes made for: '{objective}'.\n"
                "Run test suites, inspect git diff, and confirm zero regressions."
            ),
            category="testing",
            depends_on=coding_ticket_ids,
            acceptance_criteria=[
                "All test suites pass cleanly.",
                "Git diff shows only intended, scoped modifications.",
                "Syntax and linting checks pass."
            ],
            verification_commands=v_cmd_qa,
            priority=1,
        )
        tickets.append(t_qa)
        return tickets

    def _validate_and_repair(
        self,
        tickets: list[Ticket],
        baseline: RepositoryBaseline,
    ) -> list[Ticket]:
        """
        Validate ticket fields, enforce unique IDs, check dependency graphs,
        and repair missing verification commands.
        """
        if not tickets:
            return []

        # Deduplicate and ensure unique IDs
        seen_ids: set[str] = set()
        clean_tickets: list[Ticket] = []

        for t in tickets:
            while t.id in seen_ids:
                t.id = f"{t.id}-R"
            seen_ids.add(t.id)

            # Repair empty verification commands
            if not t.verification_commands and baseline.detected_test_command:
                t.verification_commands = [baseline.detected_test_command]

            # Repair empty acceptance criteria
            if not t.acceptance_criteria:
                t.acceptance_criteria = [f"Successfully resolve requirements for '{t.title}'."]

            # Sanitize category
            valid_cats = {"analysis", "coding", "testing", "refactor", "security", "docs", "general"}
            if t.category.lower() not in valid_cats:
                t.category = "coding"

            clean_tickets.append(t)

        # Validate DAG dependencies
        all_ids = {t.id for t in clean_tickets}
        for t in clean_tickets:
            t.depends_on = [dep for dep in t.depends_on if dep in all_ids and dep != t.id]

        try:
            TicketDAG(clean_tickets)
        except ValueError as err:
            logger.error("Ticket DAG contains invalid or circular dependencies: %s", err)
            raise InvalidPlanError(f"Plan validation failed due to circular dependencies: {err}") from err

        return clean_tickets

    def plan_follow_up(
        self,
        objective: str,
        unresolved_findings: list[Finding],
        baseline: RepositoryBaseline,
        existing_tickets: list[Ticket],
        max_retries: int = 2,
    ) -> list[Ticket]:
        """Generate follow-up tickets for newly discovered findings or failed verification steps."""
        if not unresolved_findings:
            return []

        actionable_findings = [
            f for f in unresolved_findings
            if f.confidence == FindingConfidence.CONFIRMED
            or f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
            or f.category in (FindingCategory.DEFECT, FindingCategory.SECURITY)
            or self._is_finding_relevant_to_objective(f, objective)
        ]
        if not actionable_findings:
            return []

        logger.info("Planner evaluating %d actionable findings for follow-up against %d existing tickets.",
                    len(actionable_findings), len(existing_tickets))
        follow_ups: list[Ticket] = []

        for finding in actionable_findings:
            # 1. Skip if already active in an uncompleted ticket
            is_active = any(
                finding.id in t.finding_ids and t.status in (TicketStatus.PENDING, TicketStatus.IN_PROGRESS, TicketStatus.QUEUED)
                for t in existing_tickets
            )
            if is_active:
                logger.debug("Finding %s is already active in a pending ticket; skipping.", finding.id)
                continue

            # 2. Skip if already resolved and verified
            is_resolved = any(
                finding.id in t.finding_ids and t.status == TicketStatus.RESOLVED and t.verified
                for t in existing_tickets
            )
            if is_resolved:
                logger.debug("Finding %s was already resolved and verified; skipping.", finding.id)
                continue

            # 3. Check bounded retry limit
            failed_attempts = sum(
                1 for t in existing_tickets
                if finding.id in t.finding_ids and t.status == TicketStatus.FAILED
            )
            if failed_attempts >= max_retries:
                logger.warning(
                    "Finding %s reached retry limit (%d/%d attempts); no duplicate tickets will be generated.",
                    finding.id, failed_attempts, max_retries
                )
                continue

            retry_suffix = f" (Retry {failed_attempts + 1})" if failed_attempts > 0 else ""
            v_cmds = [baseline.detected_test_command] if baseline.detected_test_command else []
            t = Ticket.create(
                title=f"Follow-up{retry_suffix}: {finding.title[:45]}",
                description=(
                    f"Follow-up remediation for discovered finding {finding.id}.\n"
                    f"Evidence: {finding.evidence}\n"
                    f"Suggested action: {finding.suggested_remediation}\n"
                    + (f"Note: Prior attempt {failed_attempts} failed verification. Refine implementation.\n" if failed_attempts > 0 else "")
                ),
                category="coding",
                finding_ids=[finding.id],
                target_files=[finding.file_path] if finding.file_path else [],
                acceptance_criteria=[f"Resolve finding {finding.id} without regressions."],
                verification_commands=v_cmds,
                priority=1,
            )
            follow_ups.append(t)

        return self._validate_and_repair(follow_ups, baseline)

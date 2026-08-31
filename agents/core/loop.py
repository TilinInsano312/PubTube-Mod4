"""Core structures for the PubTube Modulo 4 agentic development loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Phase(str, Enum):
    """Ordered phases used by the agentic development loop."""

    ANALYZE = "ANALYZE"
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    VERIFY = "VERIFY"
    REVIEW = "REVIEW"
    DECIDE = "DECIDE"


class Decision(str, Enum):
    """Valid terminal or continuation decisions for an agent iteration."""

    DONE = "DONE"
    CONTINUE = "CONTINUE"
    BLOCKED = "BLOCKED"


class ValidationStatus(str, Enum):
    """Validation result status for checks and traced changes."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_VERIFIED = "NOT VERIFIED"


@dataclass(frozen=True)
class AcceptanceCriterion:
    """Expected outcome that must be covered by evidence."""

    id: str
    description: str


@dataclass(frozen=True)
class ValidationCheck:
    """Executed validation command or manual inspection result."""

    name: str
    result: ValidationStatus
    evidence: str


@dataclass(frozen=True)
class TestSummary:
    """Aggregate test counts for the final task report."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class ChangeTrace:
    """Traceability entry linking a change to a requirement and validation."""

    id: str
    requirement: str
    file: str
    change: str
    validation: str
    result: ValidationStatus


@dataclass
class AgentRun:
    """Mutable state for one agentic task run.

    Args:
        task: One-sentence description of the requested task.
        scope: Files or components expected to be affected.
        acceptance_criteria: Requirements that define successful completion.
        risks: Known risks that must be considered before finishing.
    """

    task: str
    scope: list[str] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    changes: list[ChangeTrace] = field(default_factory=list)
    validations: list[ValidationCheck] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    tests: TestSummary = field(default_factory=TestSummary)
    phase: Phase = Phase.ANALYZE

    def set_plan(self, steps: list[str]) -> None:
        """Replace the current plan with concrete implementation steps."""

        self.plan = steps
        self.phase = Phase.PLAN

    def record_change(self, change: ChangeTrace) -> None:
        """Record one logical change and its validation evidence."""

        self.changes.append(change)
        self.phase = Phase.IMPLEMENT

    def record_validation(self, check: ValidationCheck) -> None:
        """Record a validation check executed during the task."""

        self.validations.append(check)
        self.phase = Phase.VERIFY

    def set_test_summary(self, passed: int, failed: int = 0, skipped: int = 0) -> None:
        """Store aggregate test results for the final report."""

        self.tests = TestSummary(passed=passed, failed=failed, skipped=skipped)

    def record_review(self, finding: str | None = None) -> None:
        """Mark review phase and optionally store a review finding."""

        if finding:
            self.limitations.append(finding)
        self.phase = Phase.REVIEW

    def record_decision(self, decision: str) -> None:
        """Store a relevant architectural or process decision."""

        self.decisions.append(decision)

    def verified_requirements(self) -> set[str]:
        """Return requirement IDs backed by passing traceability entries."""

        return {
            change.requirement
            for change in self.changes
            if change.result == ValidationStatus.PASS
        }

    def missing_requirements(self) -> list[AcceptanceCriterion]:
        """Return acceptance criteria without passing evidence."""

        verified = self.verified_requirements()
        return [
            criterion
            for criterion in self.acceptance_criteria
            if criterion.id not in verified
        ]

    def failed_validations(self) -> list[ValidationCheck]:
        """Return validation checks that failed."""

        return [
            check
            for check in self.validations
            if check.result == ValidationStatus.FAIL
        ]

    def decide(self, blocked_reason: str | None = None) -> Decision:
        """Evaluate the current run and return the next decision.

        Args:
            blocked_reason: External dependency or missing information that
                prevents meaningful progress.

        Returns:
            The current decision according to the loop completion rules.
        """

        self.phase = Phase.DECIDE
        if blocked_reason:
            self.pending.append(blocked_reason)
            return Decision.BLOCKED

        if self.missing_requirements() or self.failed_validations() or self.pending:
            return Decision.CONTINUE

        return Decision.DONE

    def render_final_report(self, status: Decision | str) -> str:
        """Render a compact Markdown report for the task."""

        status_value = _report_status(status)
        summary = _format_list([self.task], empty_value="- No summary provided.")
        changes = _format_list(
            [
                f"`{change.file}`: {change.change}"
                for change in self.changes
            ],
            empty_value="- None",
        )
        traceability = _format_list(
            [
                f"{change.requirement} -> {change.id} -> {change.result.value}"
                for change in self.changes
            ],
            empty_value="- None",
        )
        validation = _format_list(
            [
                f"`{check.name}` -> {check.result.value} ({check.evidence})"
                for check in self.validations
            ],
            empty_value="- None",
        )
        decisions = _format_optional_section("Decisions", self.decisions)
        limitations = _format_optional_section("Risks / Limitations", self.limitations)
        pending = _format_list(self.pending, empty_value="- None")

        sections = [
            "## Status",
            status_value,
            "## Summary",
            summary,
            "## Changes",
            changes,
            "## Traceability",
            traceability,
            "## Validation",
            validation,
            "## Tests",
            (
                f"Passed: {self.tests.passed}\n"
                f"Failed: {self.tests.failed}\n"
                f"Skipped: {self.tests.skipped}"
            ),
        ]

        if decisions:
            sections.append(decisions)
        if limitations:
            sections.append(limitations)

        sections.extend(["## Pending", pending])
        return "\n\n".join(sections)


def _format_list(items: list[str], empty_value: str) -> str:
    """Render a Markdown bullet list from plain strings."""

    if not items:
        return empty_value
    return "\n".join(f"- {item}" for item in items)


def _format_optional_section(title: str, items: list[str]) -> str:
    """Render a Markdown section only when it has content."""

    if not items:
        return ""
    return f"## {title}\n\n{_format_list(items, empty_value='- None')}"


def _report_status(status: Decision | str) -> str:
    """Convert loop decisions into the final report status vocabulary."""

    if status == Decision.CONTINUE:
        return "PARTIAL"
    if isinstance(status, Decision):
        return status.value
    return status


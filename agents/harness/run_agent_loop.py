"""Command-line harness helpers for the PubTube Modulo 4 agent loop."""

from __future__ import annotations

import argparse

from agents.core import AcceptanceCriterion, AgentRun, Decision
from agents.orchestrator import AgentOrchestrator


def build_agent_run(
    task: str,
    acceptance_criteria: list[str] | None = None,
    scope: list[str] | None = None,
) -> AgentRun:
    """Create the initial state for an agentic task run.

    Args:
        task: One-sentence task description.
        acceptance_criteria: Optional acceptance criteria descriptions.
        scope: Optional files or components expected to be affected.

    Returns:
        Initial `AgentRun` ready for analysis and planning.
    """

    criteria = [
        AcceptanceCriterion(id=f"AC{index}", description=description)
        for index, description in enumerate(acceptance_criteria or [], start=1)
    ]
    return AgentRun(task=task, scope=scope or [], acceptance_criteria=criteria)


def render_run_brief(run: AgentRun) -> str:
    """Render a compact operational brief for the next loop step."""

    orchestrator = AgentOrchestrator()
    next_step = orchestrator.next_step(run)
    criteria = "\n".join(
        f"- {criterion.id}: {criterion.description}"
        for criterion in run.acceptance_criteria
    )
    scope = "\n".join(f"- `{item}`" for item in run.scope)

    return "\n\n".join(
        [
            "# Agent Run Brief",
            f"Task: {run.task}",
            f"Current phase: {run.phase.value}",
            f"Assigned agent: {next_step.agent.name}",
            f"Skill: {next_step.skill.name}",
            f"Expected output: {next_step.expected_output}",
            "## Scope",
            scope or "- Not defined",
            "## Acceptance Criteria",
            criteria or "- Not defined",
        ]
    )


def main() -> None:
    """Print an initial run brief from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Prepare an agentic task run brief for PubTube Modulo 4."
    )
    parser.add_argument("task", help="Task description.")
    parser.add_argument(
        "--ac",
        action="append",
        default=[],
        help="Acceptance criterion. Can be used multiple times.",
    )
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="File or component in scope. Can be used multiple times.",
    )
    parser.add_argument(
        "--final-report",
        action="store_true",
        help="Render an empty partial final report instead of a brief.",
    )
    args = parser.parse_args()

    run = build_agent_run(
        task=args.task,
        acceptance_criteria=args.ac,
        scope=args.scope,
    )

    if args.final_report:
        print(run.render_final_report(Decision.CONTINUE))
        return

    print(render_run_brief(run))


if __name__ == "__main__":
    main()


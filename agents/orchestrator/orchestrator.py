"""Phase-to-agent orchestration for PubTube Modulo 4 agent runs."""

from dataclasses import dataclass

from agents.core import AgentRun, Phase
from agents.profiles import AgentProfile, DEFAULT_AGENT_PROFILES
from agents.skills import DEFAULT_SKILLS, SkillDefinition


@dataclass(frozen=True)
class OrchestrationStep:
    """Assignment of one loop phase to a profile and skill."""

    phase: Phase
    agent: AgentProfile
    skill: SkillDefinition
    expected_output: str


class AgentOrchestrator:
    """Builds a deterministic execution plan for the agentic loop."""

    def __init__(
        self,
        profiles: dict[str, AgentProfile] | None = None,
        skills: dict[str, SkillDefinition] | None = None,
    ) -> None:
        """Initialize the orchestrator with profile and skill catalogs.

        Args:
            profiles: Optional replacement profile catalog.
            skills: Optional replacement skill catalog.
        """

        self.profiles = profiles or DEFAULT_AGENT_PROFILES
        self.skills = skills or DEFAULT_SKILLS

    def build_plan(self) -> list[OrchestrationStep]:
        """Return the default phase execution plan."""

        return [
            self._step(
                Phase.ANALYZE,
                "software_engineer",
                "repository_inspection",
                "TASK, SCOPE, AC y RISKS definidos.",
            ),
            self._step(
                Phase.PLAN,
                "software_engineer",
                "repository_inspection",
                "Plan de 3 a 7 pasos verificables.",
            ),
            self._step(
                Phase.IMPLEMENT,
                "software_engineer",
                "implementation",
                "Cambio minimo aplicado.",
            ),
            self._step(
                Phase.VERIFY,
                "qa_validator",
                "validation",
                "Criterios marcados PASS, FAIL o NOT VERIFIED.",
            ),
            self._step(
                Phase.REVIEW,
                "reviewer",
                "diff_review",
                "Diff revisado sin cambios accidentales conocidos.",
            ),
            self._step(
                Phase.DECIDE,
                "documentation_curator",
                "reporting",
                "Reporte final con estado y evidencia.",
            ),
        ]

    def next_step(self, run: AgentRun) -> OrchestrationStep:
        """Return the orchestration step matching the current run phase."""

        for step in self.build_plan():
            if step.phase == run.phase:
                return step
        raise ValueError(f"Unsupported agent phase: {run.phase}")

    def _step(
        self,
        phase: Phase,
        profile_id: str,
        skill_id: str,
        expected_output: str,
    ) -> OrchestrationStep:
        """Create one plan step from catalog identifiers."""

        return OrchestrationStep(
            phase=phase,
            agent=self.profiles[profile_id],
            skill=self.skills[skill_id],
            expected_output=expected_output,
        )


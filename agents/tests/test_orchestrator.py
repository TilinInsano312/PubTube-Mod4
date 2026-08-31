from agents import AgentOrchestrator, AgentRun, Phase


def test_orchestrator_builds_default_phase_plan() -> None:
    orchestrator = AgentOrchestrator()

    plan = orchestrator.build_plan()

    assert [step.phase for step in plan] == [
        Phase.ANALYZE,
        Phase.PLAN,
        Phase.IMPLEMENT,
        Phase.VERIFY,
        Phase.REVIEW,
        Phase.DECIDE,
    ]
    assert plan[0].agent.id == "software_engineer"
    assert plan[3].agent.id == "qa_validator"
    assert plan[4].agent.id == "reviewer"
    assert plan[5].skill.id == "reporting"


def test_orchestrator_returns_next_step_for_run_phase() -> None:
    run = AgentRun(task="Validar orquestador.", phase=Phase.VERIFY)
    orchestrator = AgentOrchestrator()

    step = orchestrator.next_step(run)

    assert step.phase == Phase.VERIFY
    assert step.agent.id == "qa_validator"
    assert step.skill.id == "validation"


from agents.core import Phase
from agents.harness.run_agent_loop import build_agent_run, render_run_brief


def test_build_agent_run_numbers_acceptance_criteria() -> None:
    run = build_agent_run(
        task="Ordenar agentes.",
        acceptance_criteria=["Existe catalogo.", "Existe orquestador."],
        scope=["agents/"],
    )

    assert run.phase == Phase.ANALYZE
    assert [criterion.id for criterion in run.acceptance_criteria] == ["AC1", "AC2"]
    assert run.scope == ["agents/"]


def test_render_run_brief_includes_next_agent_and_skill() -> None:
    run = build_agent_run(task="Preparar brief.", scope=["agents/"])

    brief = render_run_brief(run)

    assert "Agent Run Brief" in brief
    assert "Software Engineering Agent" in brief
    assert "Repository Inspection" in brief
    assert "`agents/`" in brief

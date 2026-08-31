from agents import (
    AcceptanceCriterion,
    AgentRun,
    ChangeTrace,
    Decision,
    TestSummary,
    ValidationCheck,
    ValidationStatus,
)


def test_decide_done_when_all_acceptance_criteria_are_verified() -> None:
    run = AgentRun(
        task="Agregar documentacion agentica.",
        acceptance_criteria=[
            AcceptanceCriterion("AC1", "Existe una guia operativa."),
        ],
    )

    run.record_change(
        ChangeTrace(
            id="CHG-001",
            requirement="AC1",
            file="agents/software-engineering-loop.md",
            change="Documenta el ciclo agentico.",
            validation="revision de archivo",
            result=ValidationStatus.PASS,
        )
    )
    run.record_validation(
        ValidationCheck(
            name="revision de archivo",
            result=ValidationStatus.PASS,
            evidence="archivo presente",
        )
    )

    assert run.decide() == Decision.DONE


def test_decide_continue_when_acceptance_criterion_is_missing() -> None:
    run = AgentRun(
        task="Agregar pruebas del ciclo.",
        acceptance_criteria=[
            AcceptanceCriterion("AC1", "Existe implementacion."),
            AcceptanceCriterion("AC2", "Existe validacion."),
        ],
    )
    run.record_change(
        ChangeTrace(
            id="CHG-001",
            requirement="AC1",
            file="agents/agentic_loop.py",
            change="Agrega estructuras base.",
            validation="pytest agents/tests",
            result=ValidationStatus.PASS,
        )
    )

    assert run.decide() == Decision.CONTINUE
    assert [criterion.id for criterion in run.missing_requirements()] == ["AC2"]


def test_render_final_report_includes_traceability_and_pending() -> None:
    run = AgentRun(task="Crear loop agentico ejecutable.")
    run.pending.append("Validacion manual pendiente.")
    run.set_test_summary(passed=3)

    report = run.render_final_report(Decision.CONTINUE)

    assert "## Status" in report
    assert "PARTIAL" in report
    assert "Crear loop agentico ejecutable." in report
    assert "Validacion manual pendiente." in report
    assert "Passed: 3" in report


def test_test_summary_defaults_to_zero() -> None:
    assert TestSummary() == TestSummary(passed=0, failed=0, skipped=0)

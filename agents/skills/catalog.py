"""Catalog of reusable skills for the agentic development loop."""

from dataclasses import dataclass

from agents.core import Phase


@dataclass(frozen=True)
class SkillDefinition:
    """Reusable capability that can be assigned to one or more loop phases."""

    id: str
    name: str
    phases: tuple[Phase, ...]
    description: str
    evidence: str


DEFAULT_SKILLS: dict[str, SkillDefinition] = {
    "repository_inspection": SkillDefinition(
        id="repository_inspection",
        name="Repository Inspection",
        phases=(Phase.ANALYZE,),
        description="Localiza documentacion, tests, contratos y codigo relevante.",
        evidence="Archivos inspeccionados y alcance identificado.",
    ),
    "implementation": SkillDefinition(
        id="implementation",
        name="Minimal Implementation",
        phases=(Phase.IMPLEMENT,),
        description="Aplica el cambio mas pequeno que satisface el requerimiento.",
        evidence="Diff acotado a los archivos necesarios.",
    ),
    "validation": SkillDefinition(
        id="validation",
        name="Validation",
        phases=(Phase.VERIFY,),
        description="Ejecuta tests, compilacion, lint o inspeccion verificable.",
        evidence="Comandos ejecutados y resultados.",
    ),
    "diff_review": SkillDefinition(
        id="diff_review",
        name="Diff Review",
        phases=(Phase.REVIEW,),
        description="Revisa cambios accidentales, secretos, regresiones y consistencia.",
        evidence="Diff revisado antes del cierre.",
    ),
    "reporting": SkillDefinition(
        id="reporting",
        name="Final Reporting",
        phases=(Phase.DECIDE,),
        description="Resume estado, cambios, trazabilidad, validacion y pendientes.",
        evidence="Reporte final compacto.",
    ),
}


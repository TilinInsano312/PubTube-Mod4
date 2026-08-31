"""Catalog of agent profiles used by the orchestrator."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    """Role definition for one specialized agent profile."""

    id: str
    name: str
    responsibility: str
    default_output: str


DEFAULT_AGENT_PROFILES: dict[str, AgentProfile] = {
    "software_engineer": AgentProfile(
        id="software_engineer",
        name="Software Engineering Agent",
        responsibility="Analiza, implementa y mantiene cambios de codigo.",
        default_output="Cambio minimo validado con evidencia.",
    ),
    "reviewer": AgentProfile(
        id="reviewer",
        name="Code Review Agent",
        responsibility="Revisa diffs, riesgos, regresiones y coherencia tecnica.",
        default_output="Hallazgos priorizados o confirmacion sin hallazgos.",
    ),
    "qa_validator": AgentProfile(
        id="qa_validator",
        name="QA Validation Agent",
        responsibility="Selecciona y ejecuta verificaciones proporcionales al cambio.",
        default_output="Resultado de tests, compilacion, lint o inspeccion.",
    ),
    "documentation_curator": AgentProfile(
        id="documentation_curator",
        name="Documentation Agent",
        responsibility="Mantiene plantillas, reportes, ADRs y documentacion tecnica.",
        default_output="Documentacion actualizada y consistente.",
    ),
}


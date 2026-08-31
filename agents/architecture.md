# Agents Architecture

## Structure

```text
agents/
├── core/             # Estado, fases, decisiones, validaciones y reporte.
├── profiles/         # Perfiles de agentes especializados.
├── skills/           # Capacidades reutilizables por fase.
├── orchestrator/     # Asignacion de fase -> agente -> skill.
├── harness/          # Utilidades para iniciar y reportar ejecuciones.
├── templates/        # Plantillas Markdown para tareas y reportes.
└── tests/            # Tests del loop, orquestador y arnes.
```

## Responsibilities

| Area | Responsibility |
| --- | --- |
| `core` | Define el modelo del ciclo `ANALYZE -> PLAN -> IMPLEMENT -> VERIFY -> REVIEW -> DECIDE`. |
| `profiles` | Declara los agentes disponibles: engineering, review, QA y documentacion. |
| `skills` | Declara capacidades reutilizables: inspeccion, implementacion, validacion, revision y reporte. |
| `orchestrator` | Determina que agente y skill corresponden a cada fase. |
| `harness` | Prepara una ejecucion inicial, carga contexto desde `docs/` y genera briefs o reportes desde Python. |
| `templates` | Entrega formatos Markdown para uso manual por el equipo. |

## Default Flow

| Phase | Agent | Skill |
| --- | --- | --- |
| `ANALYZE` | Software Engineering Agent | Repository Inspection |
| `PLAN` | Software Engineering Agent | Repository Inspection |
| `IMPLEMENT` | Software Engineering Agent | Minimal Implementation |
| `VERIFY` | QA Validation Agent | Validation |
| `REVIEW` | Code Review Agent | Diff Review |
| `DECIDE` | Documentation Agent | Final Reporting |

## Extension Rules

- Agregar nuevos perfiles en `profiles/catalog.py` y documentarlos en `profiles/*.md`.
- Agregar nuevas skills en `skills/catalog.py` y documentarlas en `skills/*.md`.
- Cambiar el orden o asignacion de fases solo en `orchestrator/orchestrator.py`.
- Mantener `agentic_loop.py` como compatibilidad para imports simples.
- Mantener la carga de documentacion del proyecto en `harness/document_context.py`.

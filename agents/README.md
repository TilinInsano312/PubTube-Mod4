# Agents

Esta carpeta contiene instrucciones operativas para trabajar con agentes de software dentro de PubTube Modulo 4.

## Proposito

Estandarizar como un agente debe analizar, implementar, verificar y reportar cambios en este repositorio, manteniendo:

- cambios minimos;
- trazabilidad;
- validacion automatica;
- compatibilidad con FastAPI, observabilidad y contratos del modulo;
- cuidado de secretos y configuracion.

## Guia disponible

- [architecture.md](architecture.md): mapa de agentes, skills, orquestador, arnes y plantillas.
- [software-engineering-loop.md](software-engineering-loop.md): ciclo agentico recomendado para tareas de desarrollo, pruebas, documentacion tecnica y revision de cambios.
- [core/loop.py](core/loop.py): estructuras Python para representar fases, criterios de aceptacion, validaciones, trazabilidad y reporte final.
- [profiles/](profiles/): perfiles de agentes especializados.
- [skills/](skills/): catalogo de capacidades reutilizables por fase.
- [orchestrator/](orchestrator/): asignacion de fase, agente y skill.
- [harness/](harness/): utilidades para preparar briefs y reportes desde Python.
- [templates/task-template.md](templates/task-template.md): plantilla para preparar una tarea antes de implementarla.
- [templates/agent-report-template.md](templates/agent-report-template.md): plantilla de reporte compacto posterior a la ejecucion.

## Uso recomendado

Antes de modificar el repositorio, el agente debe:

1. Leer la solicitud actual.
2. Revisar la documentacion relevante en `README.md`, `ROLES.md`, `docs/` y archivos del area afectada.
3. Aplicar el ciclo `ANALYZE -> PLAN -> IMPLEMENT -> VERIFY -> REVIEW -> DECIDE`.
4. Ejecutar la validacion mas barata que demuestre el cambio.
5. Registrar cambios y limitaciones solo cuando aporten evidencia util.

Para automatizar o estandarizar reportes, usar `AgentRun` desde `core/loop.py`.

Para cambios que afecten contratos, eventos, observabilidad, documentacion de codigo o stack tecnologico, revisar tambien:

- `docs/observability-plan-v01.md`
- `docs/adr/*.md`

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

- [software-engineering-loop.md](software-engineering-loop.md): ciclo agentico recomendado para tareas de desarrollo, pruebas, documentacion tecnica y revision de cambios.

## Uso recomendado

Antes de modificar el repositorio, el agente debe:

1. Leer la solicitud actual.
2. Revisar la documentacion relevante en `README.md`, `ROLES.md`, `docs/` y archivos del area afectada.
3. Aplicar el ciclo `ANALYZE -> PLAN -> IMPLEMENT -> VERIFY -> REVIEW -> DECIDE`.
4. Ejecutar la validacion mas barata que demuestre el cambio.
5. Registrar cambios y limitaciones solo cuando aporten evidencia util.

Para cambios que afecten contratos, eventos, observabilidad, documentacion de codigo o stack tecnologico, revisar tambien:

- `docs/observability-plan-v01.md`
- `docs/adr/*.md`

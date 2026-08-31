# Skill: Repository Inspection

## Purpose

Encontrar el contexto minimo necesario antes de modificar archivos.

## Inputs

- Solicitud actual.
- Criterios de aceptacion.
- Documentacion en `README.md`, `docs/` y `docs/adr/*.md`.
- Tests y archivos del area afectada.

El arnes Python carga automaticamente los Markdown de `docs/` y `docs/adr/` en el brief inicial, salvo que se use `--no-docs`.

## Output

```text
TASK: ...
SCOPE:
- ...
AC:
- ...
RISKS:
- ...
```

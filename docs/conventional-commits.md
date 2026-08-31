# Conventional Commits para agentes

Guía operativa basada en la especificación [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/). Su objetivo es que los agentes creen mensajes de commit legibles por personas y herramientas automáticas.

Este documento está escrito en español para facilitar su lectura, pero todos los mensajes de commit deben escribirse en inglés. La especificación no impone un idioma; el inglés es la convención establecida para este proyecto. Esto incluye el tipo, el alcance cuando sea una palabra descriptiva, la descripción, el cuerpo y los valores de los trailers. Los identificadores propios del código, como nombres de claves, módulos o APIs, deben conservarse tal como existen en el repositorio.

## Regla principal

Todo commit debe seguir esta estructura:

```text
<type>[<scope>][!]: <description>

[optional body]

[optional footer(s)]
```

Ejemplos mínimos:

```text
fix: correct the total calculation
feat(parser): support nested arrays
```

El `!` es opcional y señala que el commit introduce un cambio incompatible:

```text
feat(api)!: change the response format
```

## Componentes del mensaje

### Tipo

El tipo es un sustantivo que comunica la intención principal del commit.

- `feat`: debe usarse cuando se añade una funcionalidad nueva.
- `fix`: debe usarse cuando se corrige un error.

También pueden usarse otros tipos. La especificación no fija una lista cerrada ni atribuye significado semántico automático a esos tipos. Un conjunto habitual es:

```text
build, chore, ci, docs, style, refactor, perf, test
```

Usar tipos adicionales no produce por sí mismo una versión mayor, menor o de parche; solo un `BREAKING CHANGE` tiene ese efecto de compatibilidad.

### Alcance

El alcance es opcional y aporta contexto sobre la parte del código afectada. Debe ser un sustantivo entre paréntesis:

```text
fix(parser): accept multiple spaces
docs(api): update the reference
```

El alcance debe describir una sección reconocible del código base. Si el repositorio define nombres de módulos o áreas, el agente debe reutilizarlos.

### Descripción

La descripción debe aparecer inmediatamente después de `: ` y resumir brevemente el cambio:

```text
fix: prevent duplicate requests
```

Se recomienda mantener una convención de mayúsculas coherente en todos los commits. La especificación permite cualquier combinación de mayúsculas y minúsculas, pero la consistencia es preferible.

### Cuerpo

El cuerpo es opcional y debe comenzar después de una línea en blanco. Puede contener uno o varios párrafos separados por saltos de línea. Úsalo cuando la descripción breve no explique suficientemente:

- por qué se hizo el cambio;
- qué comportamiento relevante se modificó;
- qué decisión técnica debe conocer quien revise el historial.

```text
fix: prevent request race conditions

Add a request ID and keep only the response corresponding to the latest
request.

Remove the timeouts that were used as a mitigation.
```

### Trailers o pies

Los trailers son opcionales y aparecen después de una línea en blanco posterior al cuerpo. Cada uno debe tener un token y un valor, usando uno de estos separadores:

```text
Token: value
Token #value
```

Los tokens deben usar guiones en lugar de espacios, salvo la excepción `BREAKING CHANGE`.

```text
Reviewed-by: Z
Refs: #123
```

El valor de un trailer puede contener espacios y saltos de línea. El siguiente trailer válido marca el final del valor anterior.

## Breaking changes

Un cambio incompatible con consumidores existentes debe indicarse de una de estas formas:

1. Añadiendo `!` inmediatamente antes de `:` en el encabezado.
2. Añadiendo un trailer `BREAKING CHANGE: ` en mayúsculas.

Ejemplos:

```text
feat!: drop support for Node 6
```

```text
feat(config): change configuration precedence

BREAKING CHANGE: environment variables now take precedence over
configuration files.
```

El footer `BREAKING-CHANGE:` es equivalente a `BREAKING CHANGE:`. La especificación exige que `BREAKING CHANGE` esté en mayúsculas. Un breaking change puede acompañar a cualquier tipo, no únicamente a `feat`.

Si se usa `!`, el trailer `BREAKING CHANGE:` puede omitirse, siempre que la descripción del commit explique el cambio incompatible.

## Relación con SemVer

La interpretación habitual es:

| Commit | Incremento de versión |
|---|---|
| `fix` | `PATCH` |
| `feat` | `MINOR` |
| Cualquier tipo con `BREAKING CHANGE` o `!` | `MAJOR` |

Los tipos distintos de `feat` y `fix` no tienen un efecto implícito sobre SemVer.

## Procedimiento para un agente

Antes de crear un commit, el agente debe:

1. Identificar la intención dominante del cambio.
2. Elegir `feat` si añade una funcionalidad o `fix` si corrige un error.
3. Elegir otro tipo permitido por el repositorio si el cambio es de documentación, pruebas, CI, dependencias, refactorización, rendimiento, estilos, etc.
4. Añadir un alcance solo si identifica claramente el área afectada.
5. Determinar si existe una incompatibilidad para consumidores. Si existe, usar `!`, `BREAKING CHANGE: ` o ambos.
6. Escribir en inglés una descripción breve inmediatamente después de `: `.
7. Añadir cuerpo y trailers únicamente cuando aporten contexto verificable.
8. Revisar que haya una línea en blanco antes del cuerpo y antes de los trailers.
9. Comprobar que no se mezclen intenciones independientes. Siempre que sea posible, dividirlas en commits separados.

## Lista de comprobación

```text
[ ] El commit empieza con un tipo.
[ ] El tipo va seguido, opcionalmente, de alcance y/o !.
[ ] Hay exactamente un cierre ": " antes de la descripción.
[ ] La descripción es breve, explica el cambio y está escrita en inglés.
[ ] El cuerpo y los valores de los trailers, si existen, están escritos en inglés.
[ ] El cuerpo, si existe, empieza tras una línea en blanco.
[ ] Los trailers, si existen, empiezan tras otra línea en blanco.
[ ] Cada trailer usa "Token: valor" o "Token #valor".
[ ] Un cambio incompatible está marcado con ! o BREAKING CHANGE:.
[ ] BREAKING CHANGE está escrito en mayúsculas.
[ ] El commit representa una intención coherente.
```

## Ejemplos de referencia

Commit con descripción y breaking change:

```text
feat: allow one configuration to extend another

BREAKING CHANGE: the `extends` key in the configuration file is now used
to extend other configuration files.
```

Commit con alcance y breaking change:

```text
feat(api)!: send an email when a product is shipped
```

Commit de documentación sin cuerpo:

```text
docs: correct CHANGELOG spelling
```

Commit con varios párrafos y varios trailers:

```text
fix: prevent request race conditions

Add a request ID and a reference to the latest request. Responses from
older requests are discarded.

Reviewed-by: Z
Refs: #123
```

Commit de reversión siguiendo una convención recomendada:

```text
revert: let us never again speak of the noodle incident

Refs: 676104e, a215868
```

La especificación no define un comportamiento obligatorio para los commits de reversión; deja esa lógica a las herramientas. El patrón anterior es una recomendación, no una regla universal.

## Casos especiales

### Fase inicial del proyecto

Incluso durante el desarrollo inicial, conviene actuar como si el producto ya estuviera publicado: otros desarrolladores o usuarios pueden necesitar saber qué se arregló y qué cambió.

### Un cambio parece pertenecer a varios tipos

Siempre que sea posible, dividir el trabajo en varios commits organizados, uno por intención principal.

### Tipo incorrecto antes de integrar o publicar

Si el tipo es válido pero no corresponde (`fix` en lugar de `feat`), corregir el historial antes de integrar o publicar, por ejemplo mediante `git rebase -i`.

Si se usó un tipo no válido (`feet` en lugar de `feat`), el commit puede quedar fuera de las herramientas que procesan Conventional Commits. Debe corregirse cuando el flujo del proyecto lo permita.

### Colaboradores que no usan la convención

No es obligatorio que cada colaborador escriba commits conformes si el proyecto usa un flujo basado en squash. Los mantenedores pueden normalizar el mensaje al integrar el pull request.

## Reglas de interpretación para herramientas

- Los elementos de Conventional Commits no deben tratarse como sensibles a mayúsculas/minúsculas, excepto `BREAKING CHANGE`, que debe estar en mayúsculas.
- `BREAKING-CHANGE` y `BREAKING CHANGE` son tokens equivalentes en un footer.
- Los tipos y trailers adicionales son extensibles; su significado debe definirse en las reglas del repositorio o de la herramienta que los consuma.
- No se debe inferir un incremento de versión solo por un tipo distinto de `feat` o `fix`.
- Un breaking change siempre prevalece sobre el tipo para determinar el impacto semántico.

## Fuente

Conventional Commits 1.0.0: <https://www.conventionalcommits.org/en/v1.0.0/>

Licencia indicada en la página fuente: Creative Commons — CC BY 3.0.

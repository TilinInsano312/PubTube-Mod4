# ADR-0007 — Pipeline de CI/CD con GitHub Actions y publicación en GHCR

- **Estado:** Aceptado
- **Fecha:** 2026-10-07

## Contexto

El Gateway se despliega en una VPS `linux/arm64`, mientras que el desarrollo
ocurre mediante Pull Requests y pushes a las ramas del repositorio. El proyecto
necesita detectar errores antes del despliegue, validar el Compose de producción
y publicar una imagen que pueda ser descargada por la VPS sin almacenar
credenciales ni archivos `.env` en Git.

El Gateway es la imagen que publica este repositorio. M1 y M3 conservan sus
propios repositorios y ciclos de publicación, por lo que el pipeline de M4 no
debe intentar construir ni publicar sus imágenes.

## Decisión

Se adopta GitHub Actions como pipeline obligatorio para Pull Requests y para
pushes a `main`, `master` y `develop`, definido en
`.github/workflows/ci.yml`.

El pipeline se divide en tres trabajos:

1. **Lint, test y build de Python**
   - Instala Python 3.12 y las dependencias de desarrollo.
   - Ejecuta Ruff sobre `gateway/app` y `gateway/tests`.
   - Ejecuta la suite de Pytest del Gateway.
   - Compila los fuentes con `compileall`.

2. **Validación de Compose, construcción y smoke tests**
   - Depende del trabajo de Python.
   - Valida el Compose local y una configuración con puerto alternativo.
   - Valida el Compose de producción, incluido el perfil de migración de M1,
     usando valores sintéticos creados dentro del runner.
   - Construye la imagen del Gateway.
   - Ejecuta los smoke tests de observabilidad con los puertos por defecto y
     con un puerto alternativo.

3. **Publicación de `develop`**
   - Solo se ejecuta después de superar los trabajos anteriores y después de
     un push a `develop`; no se publica desde Pull Requests.
   - Construye y publica
     `ghcr.io/tilininsano312/pubtube-mod4:develop` para `linux/amd64` y
     `linux/arm64`.
   - Usa `GITHUB_TOKEN` con permiso `packages: write`.

Los entornos de CI son temporales. Los archivos `.env`, `envsModulos`, las
credenciales de la VPS y los secretos de producción permanecen fuera del
repositorio y no se usan en el pipeline.

## Alternativas consideradas

### Ejecutar solo tests localmente

Se descarta porque no valida el Compose, los puertos alternativos, la imagen
Docker ni el arranque observable del sistema antes de publicar.

### Publicar una sola arquitectura

Se descarta porque la VPS es `arm64` y los colaboradores pueden consumir la
imagen desde `amd64`.

### Publicar en cada Pull Request

Se descarta para evitar tags mutables y paquetes incompletos antes de integrar
el cambio en `develop`.

### Guardar los entornos de la VPS como secretos del repositorio

Se descarta porque convertiría credenciales de infraestructura y variables de
los módulos en parte del flujo de build. Los checks de Compose usan fixtures
sintéticos y no requieren los valores reales.

## Consecuencias

### Positivas

- Los cambios deben pasar lint, tests, validación de Compose y smoke tests antes
  de publicarse.
- La imagen del Gateway está disponible para la VPS y para arquitecturas
  `amd64` y `arm64`.
- El pipeline verifica el mismo perfil de migración que se usa para M1 en la
  VPS.
- Los secretos reales nunca son necesarios para construir o probar el Gateway.
- La publicación queda asociada al commit que pasó todas las validaciones.

### Negativas y límites

- El tag `develop` es mutable y representa el estado de desarrollo, no una
  versión inmutable de producción.
- GitHub Actions consume tiempo adicional al construir dos arquitecturas.
- Publicar la imagen no ejecuta migraciones ni actualiza la VPS por sí mismo;
  esas responsabilidades pertenecen al despliegue con WUD y Compose.
- El pipeline de M4 no valida la implementación interna de M1 o M3; cada módulo
  mantiene sus propios checks.

## Referencias

- [Workflow de CI](../.github/workflows/ci.yml)
- [Smoke tests de observabilidad](../scripts/ci/smoke-observability.sh)
- [ADR-0001 — Selección del stack tecnológico](ADR-0001-stack-tecnologico.md)
- [ADR-0008 — Despliegue productivo en la VPS](ADR-0008-despliegue-vps-compose-wud.md)

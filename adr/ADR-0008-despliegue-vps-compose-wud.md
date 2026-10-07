# ADR-0008 — Despliegue productivo en la VPS con Docker Compose y WUD

- **Estado:** Aceptado
- **Fecha:** 2026-10-07

## Contexto

La integración de M1 y M3 debe ejecutarse en una VPS `linux/arm64` con
persistencia para PostgreSQL y Garage. Las APIs de los módulos deben ser
accesibles desde el Gateway sin publicar sus puertos directamente en Internet.
También se necesita actualizar automáticamente las imágenes públicas que sí
son compatibles con el flujo de `develop`, sin mover los archivos de entorno de
los módulos al repositorio.

M1 publica una imagen pública para `develop`. M3 todavía necesita construirse en
la VPS desde su rama pública porque su imagen no cubre `arm64`. El Gateway de
M4 se publica en GHCR para ambas arquitecturas.

## Decisión

Se utiliza un único Compose de producción en
`/opt/pubtube-mod4/docker-compose.prod.yml`.

### Topología y persistencia

- El Gateway es el único servicio de los módulos que publica el puerto HTTP
  externo (`8000` por defecto).
- M1 y M3 se conectan a `pubtube-network` para recibir tráfico del Gateway,
  pero sus bases de datos permanecen en `module1-internal` y
  `module3-internal`.
- PostgreSQL de M1, PostgreSQL de M3 y Garage usan volúmenes Docker persistentes.
- Las migraciones de M1 se ejecutan mediante el perfil explícito `migrate`.
- M3 ejecuta sus migraciones Alembic al iniciar su API.

### Imágenes y actualización

- Gateway: `ghcr.io/tilininsano312/pubtube-mod4:develop`, publicado para
  `amd64` y `arm64`.
- M1: `ghcr.io/sebasinmas/pubtube-modulo1:develop`, vigilado por WUD.
- M3: imagen local construida en la VPS desde su repositorio público; WUD no la
  actualiza automáticamente.
- WUD vigila el tag `develop` y su digest para Gateway y M1, y ejecuta el
  trigger de Compose local en la VPS.

Las actualizaciones que cambien el esquema de M1 requieren ejecutar la
migración coordinada con la versión correspondiente de la API. Actualizar una
imagen no sustituye ese paso.

### Entornos y secretos

Los valores reales se mantienen fuera de Git:

- `/opt/pubtube-mod4/.env` para variables de Compose y M1.
- `/opt/pubtube-mod4/envsModulos/envmodulo3` para el entorno privado de M3.
- `/opt/pubtube-mod4/secrets/` para secretos de Docker Compose.

Estos archivos deben tener permisos restrictivos, normalmente `600`, y nunca
se copian al repositorio ni se incluyen en una imagen Docker.

### Rutas de prueba

Durante la integración de los módulos, la VPS usa
`GATEWAY_PUBLIC_TEST_ROUTES=true` para permitir pruebas de las rutas de M1 y M3
sin JWT. Antes de considerar el entorno productivo, esa variable debe quedar en
`false` y el Gateway debe recrearse.

## Alternativas consideradas

### Kubernetes

Se descarta para este alcance porque agrega un plano de control, configuración y
operación que no son necesarios para una VPS única con pocos servicios.

### Ejecutar las APIs directamente en el host

Se descarta porque pierde aislamiento, reproducibilidad, redes privadas,
volúmenes declarativos y dependencias controladas.

### Construir y publicar M3 como parte del pipeline de M4

Se descarta porque M3 mantiene su repositorio y actualmente requiere una
construcción `arm64` en la propia VPS. Su ciclo de releases permanece bajo el
control del equipo de M3.

### Actualizar automáticamente todas las imágenes

Se descarta para M3 porque una actualización automática sin una imagen
`arm64` publicada ni una migración coordinada puede dejar el servicio detenido o
con un esquema incompatible.

## Consecuencias

### Positivas

- El entorno completo se levanta y se inspecciona con Docker Compose.
- Los módulos no exponen sus APIs ni bases de datos directamente al host.
- Los datos sobreviven a la recreación de contenedores mediante volúmenes.
- WUD reduce el trabajo manual para Gateway y M1.
- Los secretos de la VPS quedan fuera del historial del repositorio.
- La estrategia funciona con la arquitectura `arm64` disponible en la VPS.

### Negativas y límites

- El despliegue depende de una VPS única y no ofrece alta disponibilidad.
- Las migraciones de M1 con cambios de esquema necesitan coordinación manual.
- M3 requiere reconstrucción manual cuando cambia su código.
- WUD y el flujo de Compose tienen acceso al socket Docker del host; el acceso
  administrativo a la VPS debe estar restringido.
- `GATEWAY_PUBLIC_TEST_ROUTES` debe desactivarse antes de un uso productivo.

## Referencias

- [Compose de producción](../docker-compose.prod.yml)
- [Integración y despliegue de módulos](../docs/module-integration.md)
- [ADR-0007 — Pipeline de CI/CD](ADR-0007-pipeline-github-actions-ghcr.md)
- [ADR-0009 — Acceso filtrado a logs](ADR-0009-acceso-logs-dozzle.md)

# ADR-0003 — NGINX externo y FastAPI como Gateway/BFF

## Estado

Aceptada · 2026-09-03

## Contexto

PubTube necesita un punto de entrada único para el frontend y una capa que
permita incorporar posteriormente autenticación JWT, routing controlado,
agregación de respuestas y normalización de contratos.

El repositorio ya utiliza FastAPI para el backend del módulo y cuenta con un
gateway mínimo, healthcheck y propagación de `X-Correlation-Id`. También se
requiere una capa externa de infraestructura capaz de recibir tráfico HTTP y
preparar soporte para cargas grandes y conexiones HTTP/1.1.

## Alternativas consideradas

1. NGINX como único gateway: resuelve proxy y entrada HTTP, pero no es la capa
   adecuada para la lógica BFF ni para validar por sí solo todos los claims JWT
   con la distribución OSS utilizada.
2. FastAPI como único gateway: permite lógica de aplicación, pero mezcla las
   responsabilidades de infraestructura y aplicación.
3. NGINX + FastAPI BFF: separa infraestructura de lógica de aplicación y
   conserva FastAPI como framework base del repositorio.
4. Traefik + FastAPI: ofrece una alternativa válida de proxy dinámico, pero no
   aporta una ventaja necesaria para el alcance actual.

## Decisión

Se utilizará NGINX como reverse proxy externo y FastAPI como Gateway/BFF
interno:

```text
Frontend -> NGINX -> FastAPI Gateway/BFF -> módulos internos
```

NGINX gestionará entrada HTTP, headers de proxy, HTTP/1.1, soporte preliminar
para WebSocket/SSE y límites de carga. FastAPI mantendrá el routing controlado,
JWT, autorización, agregación, contratos OpenAPI y el `correlationId` de la
aplicación.

No se agregan rutas hacia M1, M2 o M3 hasta disponer de sus contratos y URLs
definitivas.

## Consecuencias

### Positivas

- Responsabilidades claras entre infraestructura y aplicación.
- FastAPI puede evolucionar como BFF sin reemplazarlo por configuración NGINX.
- NGINX puede manejar conexiones externas, uploads y upgrades HTTP/1.1.
- La configuración de upstreams permanece parametrizada.

### Negativas

- Se agrega una capa y configuración adicional al despliegue.
- Docker debe conectar NGINX con FastAPI en la misma red.
- La observabilidad de NGINX requerirá una tarea posterior de logs/exporter.
- El flujo de desarrollo local deberá definir cómo se ejecuta NGINX antes del
  Gateway FastAPI.

## Dependencias para Docker

La integración de Docker debe montar `nginx/templates` en el directorio de
plantillas de la imagen oficial NGINX, definir `GATEWAY_UPSTREAM` como
`host:puerto`, conectar ambos servicios a la red compartida y publicar el
puerto externo en NGINX. Esta tarea no modifica `docker-compose.yml`, Dockerfiles,
redes, servicios ni volúmenes.

## Fuera de alcance

JWT completo, RBAC, rate limiting, métricas Prometheus, OpenTelemetry, TLS,
WAF, caching, balanceo múltiple e integración real con módulos internos.

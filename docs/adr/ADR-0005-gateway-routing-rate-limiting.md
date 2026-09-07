# ADR-0005 — Routing por módulo y rate limiting en el Gateway

- **Estado:** Aceptado
- **Fecha:** 2026-09-07

## Contexto

El ADR-0003 separa NGINX como proxy externo y FastAPI como Gateway/BFF. En ese
momento los contratos y las URLs de los módulos todavía no estaban disponibles,
por lo que el routing de M1, M2 y M3 y el rate limiting quedaron fuera de
alcance.

La tarea `US-D1.T3` completa esa capacidad con los contratos públicos definidos
para PubTube y con las URLs configurables que ya existen en `Settings`.

## Decisión

### Routing

FastAPI mantiene el routing por módulo mediante routers explícitos. NGINX solo
reenvía el tráfico externo hacia el Gateway y no duplica esta lógica.

| Ruta pública | Módulo responsable | Comportamiento |
| --- | --- | --- |
| `POST /api/content` | M1 | Reenvía método, body y query string |
| `PUT /api/content/{id}/metadata` | M1 | Conserva el parámetro `id` |
| `GET /api/content...` | M1 | Conserva rutas anidadas y query string |
| `GET /api/events/{correlationId}` | M2 | Conserva el parámetro y query string |
| `POST /api/publish/schedule` | M3 | Reenvía el body original |
| `POST /api/publish/{id}/now` | M3 | Conserva el parámetro `id` |
| `GET /api/publish/{id}/status` | M3 | Conserva el parámetro `id` y query string |
| `GET /api/health` | M4/Gateway | Se resuelve localmente |

Las rutas de dashboard y notificaciones no se implementan en esta tarea: el
repositorio no contiene handlers o contratos de respuesta para ellas y su
desarrollo pertenece a las historias funcionales de M4.

Las URLs base se seleccionan desde `MODULE1_URL`, `MODULE2_URL` y
`MODULE3_URL`. Los parámetros de ruta se codifican antes de construir la URL
interna, y los parámetros de consulta se envían como pares para conservar
valores repetidos.

Las respuestas 2xx, 3xx y 4xx/5xx del upstream se devuelven al cliente con su
status, body y headers de extremo a extremo. Los errores de conexión se
normalizan como `502`, los timeouts como `504` y no se exponen excepciones
internas.

### Rate limiting

El límite se aplica en el middleware del Gateway, después de la correlación y
antes de la autenticación JWT. Se usa una ventana fija en memoria por proceso,
sin agregar Redis u otra infraestructura.

- `RATE_LIMIT_REQUESTS`: solicitudes permitidas por ventana; default `60`.
- `RATE_LIMIT_WINDOW_SECONDS`: duración de la ventana; default `60`.
- La identidad usa `X-Real-IP` cuando proviene del NGINX confiable y, en su
  ausencia, la IP de conexión observada por FastAPI.
- `/api/health` y `/api/health/` quedan excluidos para mantener disponible el
  healthcheck.
- Las solicitudes aceptadas incluyen `X-RateLimit-Limit` y
  `X-RateLimit-Remaining`.
- Las solicitudes excedidas reciben `429 Too Many Requests`, `Retry-After` y
  el mismo detalle estable en JSON.

El almacenamiento es local al proceso; por ello esta decisión es adecuada para
el despliegue universitario reproducible en un contenedor único. Un despliegue
con múltiples réplicas requerirá una decisión posterior sobre almacenamiento
compartido.

## Consecuencias

### Positivas

- Cada contrato de M1–M3 tiene un propietario explícito y auditable.
- NGINX y FastAPI mantienen responsabilidades separadas.
- La autenticación JWT sigue siendo global y las rutas nuevas quedan protegidas
  por defecto.
- El límite se puede ajustar en Docker sin cambiar código.
- Los tests pueden usar dobles HTTP y un reloj controlado sin depender de
  módulos reales.

### Negativas y límites

- El rate limiting no se comparte entre réplicas del Gateway.
- Los contratos de dashboard y notificaciones requieren handlers propios antes
  de exponerse desde el Gateway.
- El proxy carga la respuesta del upstream en memoria antes de devolverla.

## Configuración y contratos

Las nuevas variables están documentadas en `gateway/.env.example` y se
inyectan desde `docker-compose.yml`. No se cambia el formato de los contratos
de los módulos; se agregan sus rutas al Gateway y FastAPI las refleja
automáticamente en `/openapi.json`.

## Referencias

- [ADR-0003 — NGINX externo y FastAPI como Gateway/BFF](ADR-0003-nginx-fastapi-gateway.md)
- [ADR-0004 — Validación de JWT mediante middleware](ADR-0004-validacion-jwt-middleware-auth.md)
- [`RateLimitMiddleware`](../../gateway/app/middleware/rate_limit.py)
- [Pruebas de routing](../../gateway/tests/test_module_routing.py)
- [Pruebas de rate limiting](../../gateway/tests/test_rate_limit.py)

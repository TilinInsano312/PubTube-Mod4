# API del dashboard

`GET /api/dashboard` devuelve los conteos de publicaciones programadas,
publicadas y fallidas dentro de un rango temporal opcional. Es una ruta pública:
no requiere JWT, incluso si llega una cabecera Authorization inválida. El
Gateway conserva rate limiting y reenvía la consulta al servicio independiente
`dashboard-api`, definido por `DASHBOARD_URL`. Las demás rutas mantienen su
autenticación. El contrato aparece en `/docs` y `/openapi.json` sin esquema Bearer.

## Filtros

| Parámetro | Requerido | Formato |
| --- | --- | --- |
| `from` | No | `YYYY-MM-DD` o timestamp ISO con zona, por ejemplo `2026-10-01T00:00:00Z` |
| `to` | No | `YYYY-MM-DD` o timestamp ISO con zona, por ejemplo `2026-10-05T18:00:00-03:00` |

Ambos límites son inclusivos. Una fecha sin hora representa el inicio del día
UTC para `from` y el final del día UTC para `to` (23:59:59.999999). Los timestamps
se convierten a UTC. Un límite omitido queda abierto; sin filtros se consulta
todo el rango disponible. `from` no puede ser posterior a `to`.

Se rechazan fechas inexistentes, valores vacíos, timestamps sin zona y valores
numéricos. Los offsets positivos deben codificarse en la URL (`%2B` para `+`).

Ejemplo: `GET /api/dashboard?from=2026-10-01&to=2026-10-05` con
sin cabecera Authorization.

## Respuestas

Ejemplo de respuesta 200:

```json
{"status":"ok","data":{"scheduled":3,"published":5,"failed":1}}
```

Los conteos son enteros no negativos. Solo el agregador puede confirmar un
resultado vacío con tres ceros; una dependencia ausente nunca se trata como
un dashboard vacío.

Los errores conservan `X-Correlation-Id` y usan:

```json
{"status":"error","code":"INVALID_DATE_RANGE","message":"Use valid ISO dates or timestamps with timezone, with from <= to"}
```

| HTTP | Código | Causa |
| --- | --- | --- |
| 422 | `INVALID_DATE_RANGE` | Fecha o rango inválido |
| 429 | `RATE_LIMIT_EXCEEDED` | Límite D1 excedido; conserva `Retry-After` y headers de límite |
| 500 | `DASHBOARD_ERROR` | Fallo del agregador o conteos que incumplen el contrato |
| 503 | `DASHBOARD_UNAVAILABLE` | Agregador sin registrar o servicio Dashboard inaccesible |
| 504 | `DASHBOARD_TIMEOUT` | Timeout de la fuente de publicaciones o de la conexión al Dashboard |

La normalización de 429 se aplica a esta ruta para conservar el contrato público.
Los mensajes no exponen excepciones internas. Un error HTTP emitido por el
Dashboard conserva su cuerpo y código al pasar por el Gateway.

## Integración de la agregación

El agregador de dominio `PublicationDashboardService` vive en
`dashboard-api/dashboard_app/services/publication_dashboard.py`. La integración
se realiza registrando `app.state.dashboard_aggregator` en la aplicación del
Dashboard, no en la del Gateway. Puede ser ese servicio o una implementación
del contrato asíncrono del Dashboard:

```python
async def aggregate(*, from_: datetime | None, to: datetime | None) -> DashboardCounts:
    ...
```

`PublicationDashboardAdapter` convierte los filtros a `from_at`/`to_at` y los
conteos de cada bucket a `DashboardCounts`. El servicio filtra por `schedule_at`
con límites inclusivos. Un timeout HTTP de la fuente se traduce a 504; los demás
fallos se propagan al manejo de errores del endpoint. Sigue pendiente una fuente
productiva `PublicationSource` con el contrato acordado de M3; no se inventa un
endpoint de colección ni se accede directamente a su base de datos.

Hasta completar ese registro, una solicitud válida devuelve 503 sin requerir JWT.
Las pruebas unitarias y de integración cubren estados individuales y combinados,
filtros, fechas inválidas, ausencia de publicaciones, acceso público, OpenAPI y errores de
la fuente M3. La integración usa el agregador y el adaptador reales con una fuente
simulada sin filtrado; no representa una conexión con el servicio M3 desplegado.
CI ejecuta por separado las pruebas de `gateway/tests` y `dashboard-api/tests`,
además de `integration/tests`, en pull requests y pushes a `main`, `master` o
`develop`. Las pruebas de integración atraviesan el proxy y el servicio real
con una fuente M3 simulada; no representan una conexión productiva con M3.

## Ejecución y observabilidad

`docker compose up --build -d` construye y ejecuta ambos servicios. El Gateway
espera el healthcheck interno del Dashboard (`GET /api/health`). `DASHBOARD_PORT`
configura su escucha y los targets de Prometheus, con 8004 como valor por defecto.
El Dashboard no publica un puerto de host en Compose.

Prometheus consulta el job `pubtube-dashboard`. El servicio expone
`pubtube_dashboard_requests_total` y `pubtube_dashboard_request_duration_seconds`
en `/metrics`, con etiquetas de método, ruta normalizada y estado HTTP. Sus logs
son JSON con `correlationId`, `traceId` y `spanId`; las trazas `dashboard.request`
continúan el contexto W3C recibido desde el Gateway y se exportan al collector
cuando `OTEL_TRACES_EXPORTER=otlp`.

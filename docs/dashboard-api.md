# API del dashboard

`GET /api/dashboard` devuelve los conteos de publicaciones programadas,
publicadas y fallidas dentro de un rango temporal opcional. Requiere el JWT
Bearer validado por el middleware D1; no emite tokens ni modifica sus reglas.
El contrato y el esquema Bearer aparecen en `/docs` y `/openapi.json`.

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
`Authorization: Bearer <token>`.

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
| 401 | `UNAUTHORIZED` | JWT ausente, inválido o expirado; conserva `WWW-Authenticate` |
| 422 | `INVALID_DATE_RANGE` | Fecha o rango inválido |
| 429 | `RATE_LIMIT_EXCEEDED` | Límite D1 excedido; conserva `Retry-After` y headers de límite |
| 500 | `DASHBOARD_ERROR` | Fallo del agregador o conteos que incumplen el contrato |
| 503 | `DASHBOARD_UNAVAILABLE` | Agregador sin registrar |
| 504 | `DASHBOARD_TIMEOUT` | El agregador indica un timeout |

La normalización de 401 y 429 se aplica solo a esta ruta para conservar los
contratos existentes del gateway. Los mensajes no exponen excepciones internas.

## Integración de la agregación

El agregador de dominio `PublicationDashboardService` está disponible. La
integración se realiza registrando `app.state.dashboard_aggregator` durante el
ciclo de vida de la aplicación. Puede ser ese servicio o una implementación del
contrato asíncrono del gateway:

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

Hasta completar ese registro, una solicitud autenticada y válida devuelve 503.
Las pruebas unitarias y de integración cubren estados individuales y combinados,
filtros, fechas inválidas, ausencia de publicaciones, JWT, OpenAPI y errores de
la fuente M3. La integración usa el agregador y el adaptador reales con una fuente
simulada sin filtrado; no representa una conexión con el servicio M3 desplegado.
CI descubre todas estas pruebas mediante `pytest -q tests` desde `gateway` en
pull requests y pushes a `main`, `master` o `develop`.

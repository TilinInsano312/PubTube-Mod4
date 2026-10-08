# PubTube Dashboard API

Backend independiente del dashboard de publicaciones del módulo D. Posee el
contrato HTTP, la validación de fechas, la agregación y las pruebas del dominio.
Puede ejecutarse y probarse sin importar código de `gateway`.

## Ejecutar

Desde la raíz del repositorio, con el entorno `.venv` instalado:

```powershell
.\.venv\Scripts\python.exe -m uvicorn dashboard_app.main:app --app-dir dashboard-api --host 127.0.0.1 --port 8004 --no-access-log
```

Swagger: <http://localhost:8004/docs>. Salud: `GET /api/health`.
Métricas: `GET /metrics`. Dashboard: `GET /api/dashboard?from=2026-10-01&to=2026-10-05`.
La consulta no requiere JWT. El Gateway la reexpone en su puerto público y
aplica rate limiting.

En Docker se construye con su propio Dockerfile y se conecta a la red privada
`pubtube-network`. `DASHBOARD_PORT` define el puerto interno (8004 por defecto).
Las variables se describen en `.env.example`.

## Fuente de publicaciones

La fuente productiva de M3 sigue pendiente del contrato acordado entre equipos.
Se integra implementando `PublicationSource` y registrando
`PublicationDashboardService(source)` en `app.state.dashboard_aggregator` de
esta aplicación. Sin ese registro, una consulta válida responde 503. No se
devuelven datos simulados ni se interpreta la falta de integración como cero
publicaciones. Los filtros inválidos responden 422 antes de consultar la fuente.

## Pruebas

Desde este directorio, con dependencias de desarrollo instaladas:

```powershell
..\.venv\Scripts\python.exe -m pytest -q tests
```

Las pruebas cubren agregación, fechas, errores, acceso sin JWT, contrato HTTP,
salud, métricas y contexto de trazas. Las pruebas entre Gateway y Dashboard
están en `../integration/tests` y se ejecutan desde la raíz.

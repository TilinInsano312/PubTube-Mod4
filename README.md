# PubTube-Mod4

## API del dashboard

El backend del dashboard vive en [`dashboard-api/`](dashboard-api/README.md),
como servicio FastAPI independiente. El Gateway reenvía `GET /api/dashboard`
a ese servicio mediante `DASHBOARD_URL`, conservando filtros, errores y trazabilidad.
Esta ruta es pública y no valida JWT; mantiene rate limiting. Las demás rutas
conservan sus reglas de autenticación.

Consulta el [contrato y la integración pendiente con M3](docs/dashboard-api.md).
Sin una fuente de publicaciones registrada, devuelve 503; eso no equivale a un
dashboard vacío.

## Ejecutar y verificar el backend en local

Con Docker Desktop iniciado, ejecutar `docker compose up --build -d`.
Swagger del Gateway está en <http://localhost:8000/docs>, su salud en
<http://localhost:8000/api/health> y la consulta pública del dashboard en
<http://localhost:8000/api/dashboard>. El servicio `dashboard-api` usa el puerto
interno 8004 y no publica un puerto en el host. Este Compose local levanta los
backends del módulo D y observabilidad; M1/M2/M3 se integran mediante sus URLs.

Para ejecutar ambos servicios sin Docker, desde la raíz y con Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r gateway/requirements-dev.txt -r dashboard-api/requirements-dev.txt
```

En dos terminales independientes:

```powershell
.\.venv\Scripts\python.exe -m uvicorn dashboard_app.main:app --app-dir dashboard-api --host 127.0.0.1 --port 8004 --no-access-log
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir gateway --host 127.0.0.1 --port 8000 --no-access-log
```

`DASHBOARD_URL` usa `http://localhost:8004` por defecto fuera de Docker. Las
variables de cada servicio están descritas en su `.env.example`. Desde la raíz,
`.\.venv\Scripts\python.exe -m pytest -q` ejecuta las pruebas de Gateway,
dashboard e integración. El frontend aún no está implementado.

## Prometheus local

Levanta el Gateway y Prometheus con `docker compose up --build -d`. Prometheus queda en <http://localhost:9090> y las metricas del Gateway en <http://localhost:8000/metrics>. Comprueba la salud con `curl -fsS http://localhost:9090/-/healthy` y el scrape en `curl -fsS http://localhost:9090/api/v1/targets` (el job `pubtube-gateway` debe indicar `up`). `GATEWAY_PORT` define el puerto real de escucha del Gateway y se publica en el mismo puerto del host; Prometheus adapta automáticamente su target a ese valor. Por ejemplo, `GATEWAY_PORT=8010 docker compose up --build -d` publica el Gateway en `http://localhost:8010`. El puerto web de Prometheus se puede cambiar con `PROMETHEUS_PORT`.

Los futuros targets de M1/M2/M3 se agregan como jobs en `prometheus/prometheus.yml.template` cuando esos servicios expongan `/metrics`. Mantener labels de baja cardinalidad y no incluir `correlationId`, `eventId`, `userId`, `contentId`, emails ni titulos.

## Despliegue automático de `develop`

Cada push a `develop` ejecuta CI y, si pasa, publica las imágenes
`ghcr.io/tilininsano312/pubtube-mod4:develop` (Gateway) y
`ghcr.io/tilininsano312/pubtube-mod4:dashboard-develop` (Dashboard) con el
`GITHUB_TOKEN` del workflow. La VPS usa [docker-compose.prod.yml](docker-compose.prod.yml)
y WUD para actualizar cada servicio cuando cambia su digest. El secreto JWT
se crea y conserva únicamente en la VPS y solo se monta en el Gateway. La
instalación y los pasos pendientes para M1/M2/M3 están en
[la guía de integración](docs/module-integration.md).

## Integración y despliegue de M1, M2 y M3

M1, M2 y M3 están definidos en el Compose de producción con bases de datos y broker privados. Antes del primer arranque hay que configurar los entornos privados en la VPS, ejecutar la migración Drizzle de M1 y luego levantar el stack. M3 se construye en la VPS porque su imagen pública aún carece de arm64. Los comandos, la topología y las rutas públicas están en [`docs/module-integration.md`](docs/module-integration.md). La plantilla de smoke test es [`examples/module-gateway-ci.yml`](examples/module-gateway-ci.yml).

Durante las pruebas, los Compose permiten acceder a `/api/content/...`, `/api/events/...` y `/api/publish/...` sin JWT mediante `GATEWAY_PUBLIC_TEST_ROUTES=true`. Al terminar, poner esa variable en `false` en el `.env` de la VPS y recrear el Gateway.

Para que M1, M2 y M3 consulten sus logs de la VPS hay un visor Dozzle con cuentas filtradas por módulo. La configuración y el procedimiento de alta están en [`docs/log-access.md`](docs/log-access.md).

Las decisiones de arquitectura vigentes están registradas en [`adr/`](adr/): [pipeline CI/CD](adr/ADR-0007-pipeline-github-actions-ghcr.md), [despliegue en la VPS](adr/ADR-0008-despliegue-vps-compose-wud.md) y [acceso filtrado a logs](adr/ADR-0009-acceso-logs-dozzle.md).

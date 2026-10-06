# PubTube-Mod4

## API del dashboard

`GET /api/dashboard` acepta filtros opcionales `from` y `to`, valida fechas y
requiere JWT. Consulta el [contrato y la integración pendiente del agregador](docs/dashboard-api.md).

## Prometheus local

Levanta el Gateway y Prometheus con `docker compose up --build -d`. Prometheus queda en <http://localhost:9090> y las metricas del Gateway en <http://localhost:8000/metrics>. Comprueba la salud con `curl -fsS http://localhost:9090/-/healthy` y el scrape en `curl -fsS http://localhost:9090/api/v1/targets` (el job `pubtube-gateway` debe indicar `up`). `GATEWAY_PORT` define el puerto real de escucha del Gateway y se publica en el mismo puerto del host; Prometheus adapta automáticamente su target a ese valor. Por ejemplo, `GATEWAY_PORT=8010 docker compose up --build -d` publica el Gateway en `http://localhost:8010`. El puerto web de Prometheus se puede cambiar con `PROMETHEUS_PORT`.

Los futuros targets de M1/M2/M3 se agregan como jobs en `prometheus/prometheus.yml.template` cuando esos servicios expongan `/metrics`. Mantener labels de baja cardinalidad y no incluir `correlationId`, `eventId`, `userId`, `contentId`, emails ni titulos.

## Despliegue automático de `develop`

Cada push a `develop` ejecuta CI y, si pasa, publica `ghcr.io/tilininsano312/pubtube-mod4:develop` con el `GITHUB_TOKEN` del workflow. La VPS usa [docker-compose.prod.yml](docker-compose.prod.yml) y WUD para actualizar el Gateway cuando cambia el digest de la imagen. El secreto JWT se crea y conserva únicamente en la VPS. La instalación y los pasos pendientes para M1/M2/M3 están en [la guía de integración](docs/module-integration.md).

## Integración y despliegue de M1, M2 y M3

La topología, las rutas públicas, el estado actual de cada repositorio y las instrucciones para sus GitHub Actions están en [`docs/module-integration.md`](docs/module-integration.md). La plantilla de smoke test es [`examples/module-gateway-ci.yml`](examples/module-gateway-ci.yml).

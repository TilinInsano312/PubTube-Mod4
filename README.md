# PubTube-Mod4

## Prometheus local

Levanta el Gateway y Prometheus con `docker compose up --build -d`. Prometheus queda en <http://localhost:9090> y las metricas del Gateway en <http://localhost:8000/metrics>. Comprueba la salud con `curl -fsS http://localhost:9090/-/healthy` y el scrape en `curl -fsS http://localhost:9090/api/v1/targets` (el job `pubtube-gateway` debe indicar `up`). Los puertos se pueden cambiar con `PROMETHEUS_PORT` y `GATEWAY_PORT`.

Los futuros targets de M1/M2/M3 se agregan como jobs en `prometheus/prometheus.yml` cuando esos servicios expongan `/metrics`. Mantener labels de baja cardinalidad y no incluir `correlationId`, `eventId`, `userId`, `contentId`, emails ni titulos.

# PubTube-Mod4

## Prometheus local

Levanta el Gateway y Prometheus con `docker compose up --build -d`. Prometheus queda en <http://localhost:9090> y las metricas del Gateway en <http://localhost:8000/metrics>. Comprueba la salud con `curl -fsS http://localhost:9090/-/healthy` y el scrape en `curl -fsS http://localhost:9090/api/v1/targets` (el job `pubtube-gateway` debe indicar `up`). `GATEWAY_PORT` define el puerto real de escucha del Gateway y se publica en el mismo puerto del host; Prometheus adapta automáticamente su target a ese valor. Por ejemplo, `GATEWAY_PORT=8010 docker compose up --build -d` publica el Gateway en `http://localhost:8010`. El puerto web de Prometheus se puede cambiar con `PROMETHEUS_PORT`.

Los futuros targets de M1/M2/M3 se agregan como jobs en `prometheus/prometheus.yml.template` cuando esos servicios expongan `/metrics`. Mantener labels de baja cardinalidad y no incluir `correlationId`, `eventId`, `userId`, `contentId`, emails ni titulos.

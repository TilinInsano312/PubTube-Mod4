# ADR-0006 - OpenTelemetry tracing del Gateway

- **Estado:** Aceptado
- **Fecha:** 2026-09-28

## Contexto

US-D7-T3 necesita que las requests del Gateway puedan seguirse como trazas,
sin perder el `correlationId` que ya usan los logs y los contratos internos.
El entorno de desarrollo debe poder visualizar una traza sin depender de un
servicio SaaS ni de los otros modulos de PubTube.

## Decision

El Gateway instrumenta manualmente dos spans:

- `gateway.request`, de tipo SERVER, para cada request HTTP.
- `gateway.upstream`, de tipo CLIENT, para cada llamada HTTP a un modulo.

El contexto se extrae e inyecta usando W3C Trace Context (`traceparent` y
`tracestate`). Los headers W3C recibidos no se reenvian directamente: se
eliminan y se inyecta el contexto activo para evitar propagar un contexto no
validado. `X-Correlation-Id` se conserva como identificador de negocio y se
registra como atributo `correlation_id`; no se sustituye por `traceId`.

El proveedor se configura mediante variables `OTEL_*`. Fuera de Compose el
exportador es `none` por defecto. Compose levanta un OpenTelemetry Collector y
Jaeger All-in-One: el Gateway envia OTLP/HTTP al collector y Jaeger ofrece la
interfaz local en `http://localhost:${JAEGER_UI_PORT:-16686}`.

## Consecuencias

- Los logs JSON incluyen `traceId` y `spanId` cuando existe un span activo,
  además de `correlationId`.
- Los tests pueden usar un `TracerProvider` en memoria sin llamar a la red.
- La configuracion local agrega dos contenedores y puertos OTLP, pero mantiene
  la exportacion desactivada para ejecuciones unitarias fuera de Docker.
- RabbitMQ, notificaciones y el panel quedan para la instrumentacion de las
  historias posteriores; este ADR cubre el limite del Gateway de M4.

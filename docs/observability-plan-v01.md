# Plan de Observabilidad - PubTube Modulo 4

**Equipo:** Equipo D - Modulo 4 Notificaciones, Panel y API Gateway  
**Responsabilidad:** integrar la experiencia observable del sistema PubTube: gateway, notificaciones, panel en tiempo real, metricas, logs y trazas.  
**Stack aprobado:** Prometheus + Grafana, logs estructurados, OpenTelemetry y propagacion de `correlationId`, segun ADR-0001.

## 1. Base del plan

Este plan se construye a partir de los documentos del proyecto en la documentación del curso y del ADR del modulo. Los requisitos que condicionan la observabilidad son:

- PubTube es una arquitectura distribuida, orientada a eventos, con comunicacion principal por RabbitMQ y consultas REST cuando corresponda.
- El flujo editorial debe ser trazable extremo a extremo: carga, metadata, programacion, publicacion, notificacion y visualizacion.
- Todos los eventos usan envelope versionado con `id`, `type`, `version`, `timestamp`, `correlationId`, `causationId`, `source` y `payload`.
- Los endpoints internos reciben `X-Correlation-Id`; el gateway valida JWT y reexpone la API.
- La Definition of Done exige observabilidad minima: logs con `correlationId` y metricas del componente.
- Para nivel excelente en la rubrica se espera observabilidad en vivo, metricas y trazas OpenTelemetry end-to-end.

## 2. Objetivos

1. Permitir diagnosticar un flujo editorial completo por `correlationId`.
2. Detectar fallas en gateway, notificaciones, consumidores, broker y publicacion antes de la demo.
3. Mostrar en Grafana y en el panel del Modulo 4 el estado operacional relevante para el usuario.
4. Estandarizar logs, metricas y trazas para que los cuatro equipos integren sin formatos incompatibles.
5. Proveer evidencia verificable para Sprint Reviews, informe final y defensa tecnica.

## 3. Alcance del Equipo D

El Equipo D debe implementar y coordinar:

- API Gateway/BFF con autenticacion JWT, rate limiting, ruteo y endpoint `/api/health`.
- Notificaciones in-app, email y webhook sobre eventos `notify.*` y `publish.*`.
- Panel en tiempo real via WebSocket o SSE con timeline de eventos por `correlationId`.
- Dashboard de estados de publicacion: programadas, publicadas y fallidas.
- Exposicion de metricas `/metrics` en servicios propios y convenciones para los demas modulos.
- Dashboards Grafana para salud del sistema, flujo de publicacion, broker, gateway y notificaciones.
- Propagacion de `correlationId` en REST, eventos, logs y trazas.
- Instrumentacion OpenTelemetry para trazas end-to-end en Sprint 4.

Nota documental: `US-D6` aparece en la matriz de release de Sprint 4, pero no esta detallada como historia en el backlog extraido. En este plan se trata como "integracion total via gateway y demo integrada".

## 4. Estandares comunes

### 4.1 Correlation ID

Reglas:

- Toda request externa que entra por gateway debe tener un `correlationId`.
- Si el cliente envia `X-Correlation-Id`, el gateway lo valida y lo reutiliza.
- Si no existe, el gateway genera un UUID v4.
- Toda llamada REST interna debe reenviar `X-Correlation-Id`.
- Todo evento publicado debe incluir el mismo `correlationId` del flujo.
- `causationId` debe apuntar al evento o request que origino la accion.
- El panel, logs y trazas deben permitir buscar por `correlationId`.

### 4.2 Logs estructurados

Todos los servicios deben escribir logs JSON a stdout. Campos minimos:

```json
{
  "timestamp": "2026-09-01T14:03:00Z",
  "level": "INFO",
  "service": "module4-gateway",
  "environment": "local",
  "correlationId": "uuid",
  "causationId": "uuid|null",
  "eventId": "uuid|null",
  "message": "request completed",
  "route": "GET /api/dashboard",
  "method": "GET",
  "statusCode": 200,
  "durationMs": 42
}
```

Campos adicionales recomendados:

- Gateway: `userId`, `clientIp`, `rateLimitDecision`, `upstreamService`, `upstreamStatusCode`.
- Consumidores: `queue`, `routingKey`, `deliveryTag`, `retryAttempt`, `ackStatus`.
- Notificaciones: `channel`, `recipientHash`, `provider`, `deliveryStatus`, `retryAttempt`.
- Errores: `errorCode`, `errorType`, `stack` solo en entorno local/desarrollo.

No se deben registrar secretos, tokens OAuth, JWT completos, refresh tokens, passwords ni URLs firmadas sensibles.

### 4.3 Metricas Prometheus

Cada servicio backend debe exponer `/metrics`. Las metricas deben usar nombres estables, labels de baja cardinalidad y unidades explicitas.

Labels permitidos:

- `service`
- `route` normalizada, por ejemplo `/api/content/{id}`
- `method`
- `status_class`, por ejemplo `2xx`, `4xx`, `5xx`
- `event_type`
- `queue`
- `channel`
- `result`, por ejemplo `success`, `failure`, `retry`, `dlq`

Evitar labels con `contentId`, `userId`, `correlationId`, `eventId`, emails o titulos de videos.

### 4.4 Trazas OpenTelemetry

Convencion de spans:

- `gateway.request`: request externa recibida por el gateway.
- `gateway.upstream`: llamada del gateway hacia modulo interno.
- `event.publish`: publicacion de evento a RabbitMQ.
- `event.consume`: consumo de evento desde RabbitMQ.
- `notification.dispatch`: preparacion y envio de notificacion.
- `dashboard.stream`: emision de evento hacia WebSocket/SSE.

Atributos minimos:

- `service.name`
- `correlation_id`
- `event.type`
- `messaging.system = rabbitmq`
- `messaging.destination`
- `http.route`
- `http.status_code`

El `traceId` de OpenTelemetry no reemplaza al `correlationId`; ambos deben coexistir.

## 5. Catalogo de metricas

### Gateway

| Metrica | Tipo | Labels | Uso |
|---|---|---|---|
| `pubtube_gateway_requests_total` | counter | `method`, `route`, `status_class` | Trafico y errores por endpoint |
| `pubtube_gateway_request_duration_seconds` | histogram | `method`, `route` | p50/p95/p99 del gateway |
| `pubtube_gateway_upstream_requests_total` | counter | `upstreamService`, `status_class` | Salud de integraciones internas |
| `pubtube_gateway_upstream_duration_seconds` | histogram | `upstreamService`, `route` | Latencia hacia modulos |
| `pubtube_gateway_rate_limited_total` | counter | `route` | Rechazos por rate limiting |
| `pubtube_gateway_auth_failures_total` | counter | `reason` | Fallas JWT/autorizacion |

Objetivo no funcional: p95 de endpoints de consulta del gateway menor a 300 ms.

### Notificaciones

| Metrica | Tipo | Labels | Uso |
|---|---|---|---|
| `pubtube_notifications_created_total` | counter | `event_type`, `channel` | Volumen de notificaciones generadas |
| `pubtube_notifications_sent_total` | counter | `channel`, `result` | Exito/fallo por canal |
| `pubtube_notification_delivery_duration_seconds` | histogram | `channel` | Latencia de envio |
| `pubtube_notification_retries_total` | counter | `channel` | Reintentos por fallos transitorios |
| `pubtube_notification_dlq_total` | counter | `channel`, `event_type` | Mensajes derivados a DLQ |

### Panel y tiempo real

| Metrica | Tipo | Labels | Uso |
|---|---|---|---|
| `pubtube_dashboard_active_connections` | gauge | `transport` | Conexiones WebSocket/SSE activas |
| `pubtube_dashboard_events_streamed_total` | counter | `event_type` | Eventos emitidos al frontend |
| `pubtube_dashboard_stream_errors_total` | counter | `transport` | Cortes o errores del stream |
| `pubtube_dashboard_event_lag_seconds` | histogram | `event_type` | Diferencia entre `timestamp` del evento y render en panel |

### Broker y eventos

Estas metricas pueden venir de RabbitMQ exporter o del Modulo 2, pero el Equipo D debe integrarlas en Grafana:

| Metrica | Tipo | Uso |
|---|---|---|
| `rabbitmq_queue_messages_ready` | gauge | Backlog por cola |
| `rabbitmq_queue_messages_unacked` | gauge | Mensajes entregados no confirmados |
| `rabbitmq_queue_messages_published_total` | counter | Throughput de publicacion |
| `rabbitmq_queue_messages_delivered_total` | counter | Throughput de consumo |
| `pubtube_events_consumed_total` | counter | Eventos procesados por servicio |
| `pubtube_events_failed_total` | counter | Fallas de consumidores |
| `pubtube_event_processing_duration_seconds` | histogram | Latencia de procesamiento |
| `pubtube_dlq_messages_total` | counter/gauge | Tamano o ingresos a DLQ |

### Publicacion editorial

Estas metricas son compartidas con Modulo 3 y se visualizan en el dashboard:

| Metrica | Tipo | Uso |
|---|---|---|
| `pubtube_publications_scheduled_total` | counter | Publicaciones programadas |
| `pubtube_publications_completed_total` | counter | Publicaciones exitosas |
| `pubtube_publications_failed_total` | counter | Publicaciones fallidas |
| `pubtube_publication_duration_seconds` | histogram | Tiempo desde programacion hasta resultado |
| `pubtube_youtube_api_errors_total` | counter | Errores por cuota/OAuth/API externa |

## 6. Dashboards Grafana

### Dashboard 1 - Salud general PubTube

Objetivo: vista ejecutiva para Sprint Review.

Paneles:

- Estado de servicios: gateway, modulo1, modulo2, modulo3, modulo4, RabbitMQ, PostgreSQL, MinIO.
- Requests por minuto del gateway.
- Tasa de errores 4xx/5xx.
- p95 de latencia del gateway.
- Eventos publicados/consumidos por minuto.
- DLQ actual y variacion en los ultimos 15 minutos.
- Publicaciones programadas, publicadas y fallidas.

### Dashboard 2 - Flujo editorial end-to-end

Objetivo: diagnosticar un flujo por `correlationId`.

Paneles:

- Timeline de eventos por tipo: `video.uploaded`, `metadata.updated`, `publish.scheduled`, `publish.completed`, `publish.failed`, `notify.team`.
- Latencia por etapa: gateway, broker, publicacion, notificacion, render en panel.
- Tasa de exito/fallo de publicacion.
- Ultimos errores agrupados por `errorCode`.
- Tabla de busqueda por `correlationId` enlazada al panel de eventos.

### Dashboard 3 - Gateway y seguridad

Paneles:

- Top endpoints por volumen.
- p95/p99 por ruta.
- Errores por servicio upstream.
- Fallas de autenticacion por razon.
- Requests bloqueadas por rate limiting.
- Healthcheck del gateway y dependencias.

### Dashboard 4 - Notificaciones

Paneles:

- Notificaciones creadas por evento.
- Entregas por canal: in-app, email, webhook.
- Fallas y reintentos por canal.
- Latencia p95 de envio.
- Mensajes en DLQ de notificaciones.

### Dashboard 5 - Broker y resiliencia

Paneles:

- Colas con mensajes ready/unacked.
- Throughput publish/deliver/ack.
- Consumidores activos por cola.
- DLQ por cola.
- Reintentos.
- Resultado de prueba de resiliencia: caida de consumidor, recuperacion y no perdida de eventos.

## 7. Alertas minimas

Para el curso las alertas pueden ser visuales en Grafana, sin requerir integracion externa obligatoria.

| Alerta | Condicion sugerida | Severidad | Accion |
|---|---|---|---|
| Gateway caido | `/api/health` no responde por 1 min | Critica | Revisar contenedor y logs |
| p95 gateway alto | p95 > 300 ms por 5 min | Media | Revisar endpoints lentos/upstream |
| Error rate alto | 5xx > 5% por 5 min | Alta | Revisar logs por `correlationId` |
| DLQ con mensajes | DLQ > 0 por 2 min | Alta | Inspeccionar evento, causa y retry |
| Consumidor detenido | cola sin consumidores por 2 min | Alta | Reiniciar consumidor, revisar excepcion |
| Notificaciones fallando | `result=failure` > 10% por 10 min | Media | Revisar SMTP/webhook/reintentos |
| Lag del panel | p95 lag > 5 s por 5 min | Media | Revisar stream, broker y frontend |
| YouTube/OAuth fallando | errores OAuth/cuota > 0 en 10 min | Alta | Revisar credenciales/mock/cuotas |

## 8. Integracion con el panel del Modulo 4

El panel funcional no debe duplicar Grafana. Debe mostrar informacion orientada al usuario:

- Estado de publicaciones: programadas, publicadas, fallidas.
- Timeline en vivo de eventos por `correlationId`.
- Filtros por tipo de evento, contenido y rango de fechas.
- Notificaciones in-app no leidas.
- Estado resumido del sistema: operativo/degradado/con errores.

Grafana queda para diagnostico tecnico:

- Latencias, throughput, errores, DLQ, reintentos y salud de infraestructura.
- Evidencia para Sprint Review y defensa tecnica.

## 9. Plan por sprint

### Sprint 0 - Base observable

Entregables:

- Plan de observabilidad versionado.
- ADR de stack aprobado con Prometheus + Grafana.
- `docker-compose.yml` con servicios reservados para `prometheus` y `grafana`.
- Convencion documentada de logs JSON y `correlationId`.
- Definicion inicial de metricas obligatorias por servicio.

Criterios de aceptacion:

- El equipo puede explicar como se propagara `correlationId`.
- Existe una lista inicial de dashboards y metricas.
- El gateway tiene esqueleto de `/api/health`.

### Sprint 1 - Gateway y logs minimos

Historias relacionadas: `US-D1`, `US-D2`.

Entregables:

- Middleware del gateway para generar/propagar `X-Correlation-Id`.
- Logs JSON del gateway con `correlationId`, ruta, status y duracion.
- Primeras metricas de gateway: requests, latencia, auth failures y rate limit.
- Healthcheck del gateway y dependencias basicas.
- Notificaciones in-app con logs de creacion.

Criterios de aceptacion:

- Una request al gateway puede encontrarse en logs por `correlationId`.
- `/metrics` del gateway es recolectable por Prometheus.
- La demo muestra al menos logs correlacionados y metricas basicas.

### Sprint 2 - Eventos, timeline y broker

Historias relacionadas: `US-D4`, `US-D2`.

Entregables:

- Timeline en vivo por WebSocket/SSE.
- Logs de consumo de eventos con `eventId`, `event_type`, `correlationId` y `causationId`.
- Metricas de eventos consumidos, fallidos y latencia de procesamiento.
- Dashboard Grafana inicial de broker/eventos.
- Visualizacion de DLQ si el Modulo 2 ya la expone.

Criterios de aceptacion:

- Un evento `publish.*` aparece en el panel y en Grafana.
- Se puede filtrar el timeline por `correlationId`.
- Fallas de consumo quedan visibles en logs y metricas.

### Sprint 3 - Notificaciones externas y dashboard editorial

Historias relacionadas: `US-D3`, `US-D5`.

Entregables:

- Metricas de notificaciones por canal, resultado y reintentos.
- Dashboard de estados de publicacion con filtros por fecha.
- Panel Grafana de notificaciones.
- Alertas visuales para fallas de entrega y errores del gateway.
- Logs sin datos sensibles para email/webhook.

Criterios de aceptacion:

- Una publicacion fallida genera evento, notificacion y metrica.
- Las fallas transitorias de email/webhook incrementan reintentos.
- El dashboard muestra programadas, publicadas y fallidas.

### Sprint 4 - Observabilidad end-to-end

Historias relacionadas: `US-D6`, `US-D7`, integracion final.

Entregables:

- OpenTelemetry instrumentado en gateway, consumidores y notificaciones.
- Propagacion de contexto REST + RabbitMQ.
- Dashboard final de salud general, gateway, broker, notificaciones y flujo editorial.
- Demo guiada por `correlationId`: request inicial -> eventos -> publicacion -> notificacion -> panel.
- Pruebas de resiliencia/carga coordinadas con Equipo B y Equipo C.

Criterios de aceptacion:

- Un `correlationId` permite reconstruir el flujo completo en logs, eventos, metricas y trazas.
- La demo muestra observabilidad en vivo.
- La DLQ y reintentos son visibles.
- El sistema cumple p95 < 300 ms para endpoints de consulta del gateway bajo carga razonable de curso.

## 10. Definition of Done observable

Una historia del Equipo D no debe darse por terminada si no cumple:

- Logs JSON con `service`, `level`, `timestamp`, `message` y `correlationId`.
- Errores con `errorCode` y causa accionable.
- Metricas Prometheus para volumen, errores y latencia cuando aplique.
- Pruebas que validen propagacion de `X-Correlation-Id`.
- Sin secretos en logs, repo ni `.env.example`.
- Si toca contratos, OpenAPI/catalogo de eventos actualizado.
- Si toca eventos, `correlationId` y `causationId` propagados.
- Si toca frontend en vivo, evento visible en timeline o estado observable.

## 11. Pruebas de observabilidad

Pruebas minimas:

- Unitarias: middleware de correlation ID, formato de logs, clasificacion de errores.
- Integracion: gateway reenvia `X-Correlation-Id` a modulos internos.
- Integracion RabbitMQ: consumidor registra `eventId`, `correlationId` y ack/nack.
- Contrato: eventos cumplen envelope versionado.
- E2E: flujo mock carga -> metadata -> programacion -> publicacion -> notificacion -> panel.
- Resiliencia: detener consumidor, enviar evento, reactivar consumidor y verificar procesamiento o DLQ.
- Carga: k6 sobre `/api/dashboard` y endpoints de gateway; validar p95.

## 12. Runbook inicial

### Buscar un flujo por correlationId

1. Copiar el `correlationId` desde el panel o respuesta del gateway.
2. Buscarlo en logs del gateway.
3. Consultar eventos asociados en `GET /events/{correlationId}`.
4. Revisar spans OTel con atributo `correlation_id`.
5. Verificar metricas del periodo en Grafana: errores, latencia, DLQ y notificaciones.

### Investigar mensaje en DLQ

1. Identificar `queue`, `event_type`, `eventId` y `correlationId`.
2. Revisar logs del consumidor por `eventId`.
3. Confirmar cantidad de reintentos.
4. Validar si el payload rompe contrato.
5. Corregir consumidor o contrato.
6. Reprocesar solo si la operacion es idempotente.

### Investigar gateway lento

1. Confirmar p95 por ruta en Grafana.
2. Revisar si la latencia viene del gateway o de `upstreamService`.
3. Buscar errores 5xx/timeout por la misma ruta.
4. Revisar rate limiting y autenticacion.
5. Ejecutar prueba k6 acotada si el problema no es reproducible.

## 13. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigacion |
|---|---|---|
| Cada modulo loguea con formato distinto | No hay trazabilidad real | Definir formato comun desde Sprint 0 y revisarlo en PR |
| `correlationId` se pierde al publicar eventos | No se puede reconstruir el flujo | Tests de contrato del envelope y pruebas de integracion |
| Cardinalidad alta en Prometheus | Prometheus lento o inutilizable | Prohibir IDs de negocio como labels |
| Grafana queda como decoracion sin datos utiles | Demo debil | Definir dashboards desde casos de diagnostico reales |
| Notificaciones filtran datos sensibles | Riesgo de seguridad | Sanitizar logs y no registrar tokens/JWT completos |
| OTel se deja para el final sin base previa | Integracion Sprint 4 riesgosa | Empezar con `correlationId` y spans basicos desde Sprint 2 |
| `US-D6` no esta detallada | Ambiguedad de alcance | Refinarla en Sprint Planning como integracion total y demo observable |

## 14. Evidencia para Sprint Review final

La demo final debe mostrar:

1. Request inicial al gateway con `X-Correlation-Id`.
2. Eventos del flujo en el timeline del panel.
3. Notificacion in-app y, si esta habilitado, email/webhook.
4. Grafana con latencia del gateway, throughput de eventos y estado de DLQ.
5. Traza OpenTelemetry del flujo completo.
6. Caso de fallo controlado: publicacion fallida o consumidor caido, con retry/DLQ visible.

La evidencia debe estar respaldada por logs, metricas, trazas y pruebas automatizadas, no solo por capturas manuales.

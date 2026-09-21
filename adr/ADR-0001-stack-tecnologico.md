# ADR-0001 — Selección del stack tecnológico

- **Estado:** Aceptado
- **Fecha:** 2026-08-29

## Contexto

PubTube requiere una arquitectura distribuida, orientada a eventos y ejecutable localmente mediante contenedores.

El proyecto debe utilizar tecnologías gratuitas y open source, permitir la integración entre los distintos módulos y facilitar el desarrollo, pruebas, observabilidad y despliegue del sistema.

Durante el Sprint 0 se debe definir y documentar el stack tecnológico que será utilizado durante el desarrollo del proyecto.

Los principales requisitos considerados para la selección son:

- Compatibilidad con una arquitectura orientada a eventos.
- Integración mediante APIs REST y mensajería asíncrona.
- Ejecución local mediante Docker Compose.
- Facilidad de desarrollo y mantenimiento.
- Disponibilidad de herramientas gratuitas y open source.
- Soporte para pruebas automatizadas y CI.
- Observabilidad mediante logs y métricas.
- Documentación de contratos mediante OpenAPI.
- Facilidad de integración entre los distintos módulos de PubTube.

## Decisión

Se adopta el siguiente stack tecnológico:

| Capa | Tecnología seleccionada |
|---|---|
| Backend / API | Python + FastAPI |
| Mensajería Pub/Sub | RabbitMQ |
| Base de datos | PostgreSQL |
| Object Storage | MinIO |
| Frontend | React + Vite |
| Scheduler | APScheduler |
| Autenticación | OAuth 2.0 + JWT (PyJWT) |
| Observabilidad | Prometheus + Grafana |
| CI/CD | GitHub Actions |
| Contenedores | Docker + Docker Compose |
| Gestión de proyecto | Trello |
| Documentación API | OpenAPI |

## Justificación de las decisiones

### Backend — Python + FastAPI

Se utilizará **Python con FastAPI** para la construcción de APIs y servicios backend.

Se selecciona debido a:

- Sintaxis simple y mantenible.
- Buen rendimiento para APIs REST.
- Soporte nativo para programación asíncrona.
- Integración directa con OpenAPI.
- Ecosistema amplio para PostgreSQL, RabbitMQ y observabilidad.
- Facilidad para implementar pruebas automatizadas.

### Mensajería — RabbitMQ

Se utilizará **RabbitMQ** como backbone de mensajería publish-subscribe.

Permite implementar los requisitos de PubTube relacionados con:

- Topic exchanges.
- Routing keys.
- Colas independientes por consumidor.
- Dead Letter Queues.
- Reintentos.
- Comunicación asíncrona entre módulos.

RabbitMQ será ejecutado mediante Docker.

### Base de datos — PostgreSQL

Se utilizará **PostgreSQL** como base de datos relacional.

Se selecciona por:

- Consistencia transaccional.
- Soporte para relaciones e índices.
- Soporte para JSON/JSONB cuando sea necesario.
- Amplio soporte desde Python.
- Ejecución sencilla mediante Docker.
- Persistencia mediante volúmenes.

### Object Storage — MinIO

Se utilizará **MinIO** como almacenamiento de objetos compatible con S3.

Permitirá almacenar archivos audiovisuales y otros recursos sin depender de servicios cloud de pago.

Sus principales ventajas son:

- Compatibilidad con la API S3.
- Ejecución local.
- Open source.
- Integración sencilla mediante Docker Compose.

### Frontend — React + Vite

Se utilizará **React** para la interfaz web y **Vite** como herramienta de desarrollo y construcción.

Esta combinación permite:

- Desarrollo rápido de interfaces.
- Arquitectura basada en componentes.
- Integración con APIs REST.
- Integración futura con WebSocket o Server-Sent Events.
- Build optimizado para producción.

### Scheduler — APScheduler

Se utilizará **APScheduler** para las tareas programadas.

Se selecciona por su integración directa con Python y por permitir implementar procesos programados con persistencia y control de ejecución.

### Autenticación — OAuth 2.0 + JWT

La autenticación utilizará:

- **OAuth 2.0** para integraciones que requieran autorización externa.
- **JWT** para autenticación y autorización de solicitudes a través del API Gateway.
- **PyJWT** para creación y validación de tokens JWT en Python.

Los secretos, tokens y credenciales nunca serán almacenados en el repositorio.

### Observabilidad — Prometheus + Grafana

Se utilizará:

- **Prometheus** para recolectar métricas.
- **Grafana** para visualizar métricas y construir dashboards.

Los servicios deberán exponer métricas que permitan observar el comportamiento y estado del sistema.

La observabilidad se complementará posteriormente con logs estructurados y propagación de `correlationId`.

### CI/CD — GitHub Actions

Se utilizará **GitHub Actions** para la integración continua.

El pipeline deberá evolucionar para ejecutar automáticamente:

1. Lint.
2. Tests.
3. Build.
4. Validación del proyecto.
5. Build de imágenes Docker cuando corresponda.

Los Pull Requests deberán pasar los checks definidos antes de integrarse a la rama principal.

### Contenedores — Docker + Docker Compose

Todos los servicios deberán poder ejecutarse mediante **Docker**.

**Docker Compose** será utilizado para levantar el entorno completo y administrar:

- Servicios.
- Redes.
- Variables de entorno.
- Volúmenes persistentes.
- Dependencias entre contenedores.

El objetivo es que el entorno pueda levantarse mediante:

```bash
docker compose up
````

### Gestión del proyecto — Trello

Se utilizará **Trello** como herramienta de gestión del Product Backlog y Sprint Backlog.

El tablero seguirá inicialmente el flujo:

```text
Product Backlog
→ Ready
→ In Progress
→ Code Review
→ Testing
→ Done
```

Las tarjetas deberán identificar como mínimo:

* User Story relacionada.
* Sprint.
* Prioridad.
* Responsable.
* Story Points.
* Dependencias.
* Criterios de aceptación.

### Documentación — OpenAPI

Los contratos REST serán documentados utilizando **OpenAPI**.

OpenAPI será la especificación utilizada como fuente de verdad para documentar:

* Endpoints.
* Métodos HTTP.
* Parámetros.
* Request bodies.
* Responses.
* Códigos de error.
* Esquemas de datos.

Los cambios que afecten contratos entre módulos deberán reflejarse en la documentación OpenAPI correspondiente.

## Alternativas consideradas

### Backend

* Node.js + NestJS.
* Go + Gin.

Se seleccionó Python + FastAPI por su simplicidad, velocidad de desarrollo y facilidad de integración con el resto de las herramientas seleccionadas.

### Mensajería

* NATS.
* Google Cloud Pub/Sub.

Se seleccionó RabbitMQ debido a su soporte directo para exchanges, routing keys, DLQ y reintentos, además de poder ejecutarse completamente en local.

### Base de datos

* MongoDB.
* SQLite.

Se seleccionó PostgreSQL debido a sus capacidades transaccionales, persistencia y adecuación al modelo de datos del proyecto.

### Frontend

* Vue.
* HTML + JavaScript.

Se seleccionó React + Vite debido a su ecosistema, arquitectura basada en componentes y facilidad para implementar interfaces dinámicas en tiempo real.

### Gestión del proyecto

* GitHub Projects.
* Jira.

Se seleccionó Trello debido a que el equipo ya lo utiliza como tablero Kanban y permite administrar de forma simple el Product Backlog y Sprint Backlog.

## Consecuencias

### Positivas

* Todo el stack puede ejecutarse de forma local.
* No se requieren licencias de pago.
* Las tecnologías poseen amplia documentación y comunidad.
* La arquitectura puede ejecutarse mediante Docker Compose.
* Existe buena compatibilidad entre Python, RabbitMQ y PostgreSQL.
* FastAPI facilita la generación y mantenimiento de contratos OpenAPI.
* GitHub Actions permite automatizar el proceso de validación.
* Prometheus y Grafana permiten incorporar observabilidad progresivamente.
* Trello permite centralizar la gestión Scrum del equipo.

### Negativas

* El equipo deberá mantener varios servicios y contenedores.
* RabbitMQ agrega complejidad operacional frente a una arquitectura puramente REST.
* La observabilidad requiere configurar componentes adicionales.
* Será necesario coordinar cuidadosamente los contratos entre módulos.
* Docker Compose deberá mantenerse sincronizado a medida que se incorporen nuevos servicios.

## Restricciones

Las siguientes reglas aplican a todas las tecnologías seleccionadas:

* No se almacenarán secretos ni credenciales en Git.
* Las configuraciones variables deberán utilizar variables de entorno.
* Se mantendrá un archivo `.env.example` sin información sensible.
* Los servicios deberán poder ejecutarse mediante Docker.
* Los datos persistentes utilizarán volúmenes.
* Los contratos REST deberán mantenerse actualizados en OpenAPI.
* Los cambios de arquitectura relevantes deberán documentarse mediante nuevos ADR.
* Un cambio al stack aprobado requerirá un nuevo ADR que justifique la modificación.

## Resultado

El stack definido en este ADR será utilizado como base tecnológica para el desarrollo de PubTube.

Cualquier modificación significativa de estas decisiones deberá documentarse mediante un nuevo Architecture Decision Record que reemplace o complemente este ADR.

# ADR-0010 — Backend del Dashboard separado del Gateway

## Estado

Implementada, pendiente de revisión del equipo.

## Contexto

El Gateway alojaba la validación de filtros, modelos y agregación de estados
de publicación. Eso acoplaba la evolución del dashboard a su código, pruebas
y despliegue. Se solicitó extraer el backend a un directorio propio y permitir
consultar `/api/dashboard` sin JWT mientras M3 no provee esa integración.

## Alternativas consideradas

1. Mantener la agregación en el Gateway: evita un servicio adicional, pero
   mantiene el acoplamiento que motivó la solicitud.
2. Extraer un paquete importado por el Gateway: separa archivos, aunque conserva
   el mismo proceso y despliegue.
3. Crear un servicio FastAPI independiente: separa aplicación y despliegue,
   agregando una llamada HTTP interna y un contenedor.

## Decisión

Se implementa la tercera alternativa en `dashboard-api`, con el paquete Python
`dashboard_app` para evitar colisiones con `gateway/app` durante integración.
El Gateway conserva únicamente el contrato público y el proxy, incluyendo
rate limiting y propagación de contexto. `DASHBOARD_URL` define el destino.

La ruta exacta `/api/dashboard` y su variante con barra final quedan exentas
de JWT por solicitud expresa. Otras rutas conservan sus reglas de autenticación.
OpenAPI refleja el acceso público. En Docker el servicio no publica un puerto
de host y recibe las consultas a través del Gateway.

## Consecuencias

El Dashboard tiene configuración, Dockerfile, salud, métricas, trazas y pruebas
propias. CI valida ambos servicios y su integración; las imágenes se publican
con tags separados y WUD las actualiza por separado.

La operación necesita ambos servicios. Si el Dashboard no responde, el Gateway
devuelve 503; si excede su timeout, devuelve 504. La fuente productiva de M3 sigue
pendiente y la ausencia del agregador devuelve 503. Los datos simulados se usan
solo en pruebas. Esta extracción no implementa el frontend ni cambia contratos
de M1/M2/M3.

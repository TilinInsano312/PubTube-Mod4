# NGINX edge gateway

Esta configuración implementa la capa externa de la arquitectura:

```text
Frontend -> NGINX -> FastAPI Gateway/BFF -> módulos internos
```

La plantilla `templates/default.conf.template` espera que el entorno de NGINX
defina `GATEWAY_UPSTREAM` como `host:puerto`, por ejemplo
`gateway-interno:8000`. La plantilla está pensada para la sustitución de
variables del entrypoint oficial de la imagen NGINX.

## Responsabilidad de esta capa

- Recibir tráfico HTTP externo.
- Reenviar `/api/...` al Gateway FastAPI.
- Preservar headers de proxy y `X-Correlation-Id` cuando exista.
- Preparar HTTP/1.1, WebSocket/SSE y cargas grandes.
- Mantener rutas no declaradas fuera del backend con respuesta 404.

La generación del UUID v4 de dominio, JWT, autorización, agregación de
respuestas, métricas y contratos BFF continúan siendo responsabilidad de
FastAPI o de subtareas posteriores.

## Integración pendiente de Docker

El responsable de Docker deberá, sin cambiar esta plantilla:

1. Agregar el servicio NGINX y montar `./nginx/templates` en
   `/etc/nginx/templates` como solo lectura.
2. Definir `GATEWAY_UPSTREAM` con el host y puerto reales del servicio FastAPI.
3. Conectar NGINX y FastAPI a la misma red Docker.
4. Publicar hacia el host únicamente el puerto de NGINX y mantener FastAPI
   interno, si esa es la política del despliegue.
5. Configurar `depends_on`/healthcheck según el nombre final del servicio.
6. Acordar con los equipos los nombres, puertos y límites de los módulos antes
   de incorporar rutas upstream reales.

No se asumen nombres Docker para M1, M2 o M3 en esta tarea.

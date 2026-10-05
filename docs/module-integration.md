# Integración y despliegue con GHCR y WUD

Cada push a `develop` ejecuta las pruebas del módulo, construye su imagen, comprueba una petición a través de la imagen publicada del Gateway y, si todo pasa, publica `ghcr.io/<owner>/<repo>:develop`. La VPS ejecuta [docker-compose.prod.yml](../docker-compose.prod.yml); WUD detecta el digest nuevo y actualiza el servicio. Los repositorios de los módulos no necesitan SSH ni secretos de producción.

| Servicio | Imagen GHCR | Puerto interno | Salud en Gateway |
| --- | --- | --- | --- |
| Gateway | `ghcr.io/tilininsano312/pubtube-mod4:develop` | 8000 | `/api/health` |
| M1 | `ghcr.io/sebasinmas/pubtube-modulo1:develop` | 8000 | `/api/content/health` |
| M2 | `ghcr.io/carloscienfuegos1/pubtube-modulo2:develop` | 8002 | `/api/events/health` |
| M3 | `ghcr.io/nahuelcatrileo/dpmod3-2026:develop` | 8003 | `/api/publish/health` |

Para que Actions de los módulos descargue el Gateway y la VPS descargue las cuatro imágenes sin un PAT compartido, los propietarios deben cambiar a **público** cada paquete GHCR después de su primera publicación. GitHub crea paquetes privados por defecto. Si alguna imagen debe ser privada, se necesita acceso de lectura al paquete desde el workflow consumidor y autenticación GHCR de solo lectura en la VPS; los equipos siguen sin recibir credenciales SSH.

## Instrucciones para los tres equipos

1. Implementar una API HTTP en `0.0.0.0` con `GET /health` (2xx). Mantener sus pruebas y dependencias efímeras de CI.
2. Copiar [la plantilla de Actions](../examples/module-gateway-ci.yml) a `.github/workflows/gateway-integration.yml`. Adaptar el arranque del módulo y su smoke test. La plantilla descarga la imagen del Gateway, usa un JWT ficticio de CI y publica con `GITHUB_TOKEN`/`packages: write` solo tras pasar la integración en un push a `develop`.
3. Configurar estas variables de Actions:

| Variable | M1 | M2 | M3 |
| --- | --- | --- | --- |
| `MODULE_SLOT` | `1` | `2` | `3` |
| `MODULE_PORT` | `8000` | `8002` | `8003` |
| `GATEWAY_SMOKE_PATH` | `/api/content/health` | `/api/events/health` | `/api/publish/health` |

No configuren `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`, `GATEWAY_REPO_TOKEN`, `JWT_SECRET` ni contraseñas reales en Actions. `GITHUB_TOKEN` lo entrega GitHub automáticamente. La plantilla usa `docker run` para una API autónoma: M1 necesita levantar PostgreSQL y Garage efímeros; M2 necesita RabbitMQ para las pruebas que lo requieran. Esos servicios son parte del CI del módulo y no usan datos de producción.

## Contrato HTTP

- M1: `POST /api/content/init`, `GET /api/content/{sessionId}/part/{partNumber}`, `GET /api/content/upload/{sessionId}/status` y `POST /api/content/upload/{sessionId}/complete`, publicados bajo `/api/content/...`.
- M2: `GET /events/{correlation_id}`, publicado como `GET /api/events/{correlation_id}`. RabbitMQ por sí solo no satisface esta API HTTP.
- M3: `POST /publish/schedule`, `POST /publish/{publication_id}/now` y `GET /publish/{publication_id}/status`, publicados bajo `/api/publish/...`.
- Todos: `GET /health` devuelve 2xx y la API propaga `X-Correlation-Id`.

En producción el Gateway usa `http://module1-api:8000`, `http://module2-api:8002` y `http://module3-api:8003`. Solo el Gateway valida el JWT y recibe la clave de firma; los módulos no publican puertos al host. Si un módulo también necesita validar JWT, el equipo debe acordar una firma asimétrica y distribución de la clave pública.

## Estado de los repositorios revisados

| Repositorio | Estado en `main` | Pendiente |
| --- | --- | --- |
| [M1](https://github.com/sebasinmas/pubtube-modulo1) | API NestJS, Dockerfile y Compose con PostgreSQL/Garage; puerto interno 8000. | Añadir `/health`, probar API y dependencias en Actions, publicar `:develop`. En producción debe quitar la publicación del puerto 8000 de la API. |
| [M2](https://github.com/CarlosCienfuegos1/PubTube-Modulo2) | Envelope/eventos Python y Compose de RabbitMQ; sin API HTTP ni Dockerfile. | Implementar `/health` y `GET /events/{correlation_id}`, Dockerfile y pruebas; publicar `:develop`. |
| [M3](https://github.com/NahuelCatrileo/DPMod3-2026) | Documentación y Compose de marcador; sin aplicación ni Dockerfile. | Implementar API, `/health`, rutas de publicación, Dockerfile y pruebas; publicar `:develop`. |

Las ramas por defecto son `main`: cada equipo debe usar `develop` para activar la publicación. Hasta que existan las imágenes y APIs de M1/M2/M3, no se pueden iniciar esos servicios en la VPS.

## VPS

Instalar [docker-compose.prod.yml](../docker-compose.prod.yml) en `/opt/pubtube-mod4` junto con los archivos de observabilidad. Crear `/opt/pubtube-mod4/secrets/jwt_secret` con una clave aleatoria y permisos restringidos antes del primer arranque. El Gateway lee `/run/secrets/jwt_secret` mediante `JWT_SECRET_FILE`; `secrets/` está ignorado por Git.

WUD monta `/opt/pubtube-mod4` en la misma ruta para que el trigger de Compose encuentre el archivo Compose, los archivos de observabilidad y los secretos cuando recrea los servicios. Tiene acceso al socket Docker; solo el administrador de la VPS debe poder modificar ese Compose. `wud.watch.digest=true` permite detectar cambios del tag fijo `develop`.

Cuando cada módulo publique una imagen funcional, el administrador agrega su API al **mismo Compose** con la imagen de la tabla, alias `moduleN-api` en `pubtube-network`, `restart: unless-stopped` y etiquetas `wud.watch: "true"`, `wud.watch.digest: "true"`, `wud.tag.include: "^develop$"`, `wud.trigger.include: dockercompose.local`. PostgreSQL, Garage y RabbitMQ se definen con volúmenes persistentes y redes privadas. Solo las APIs se conectan a `pubtube-network`; las bases de datos y el broker quedan en una red interna.

Los secretos de cada módulo se crean bajo `/opt/pubtube-mod4/secrets/` y se asignan solo al servicio que los necesita. Docker los monta en `/run/secrets/<nombre>`, pero la aplicación debe leer el archivo o una variable `*_FILE` que apunte a él. M1 actualmente construye `DATABASE_URL` desde variables de entorno, así que su equipo debe adaptar ese punto o se debe suministrar un `.env` privado en la VPS. Ningún secreto de JWT, DB, Garage o RabbitMQ entra a la imagen o al workflow.

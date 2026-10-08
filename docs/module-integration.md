# Integración y despliegue con GHCR y WUD

Cada push a `develop` ejecuta las pruebas del módulo, construye su imagen, comprueba una petición a través de la imagen publicada del Gateway y, si todo pasa, publica `ghcr.io/<owner>/<repo>:develop`. La VPS ejecuta [docker-compose.prod.yml](../docker-compose.prod.yml); WUD detecta el digest nuevo y actualiza el servicio. Los repositorios de los módulos no necesitan SSH ni secretos de producción.

La VPS usa `linux/arm64`. La plantilla publica manifiestos para `linux/amd64` y `linux/arm64`; ambos deben estar presentes en cada imagen que se despliegue aquí.

| Servicio | Imagen GHCR | Puerto interno | Salud en Gateway |
| --- | --- | --- | --- |
| Gateway | `ghcr.io/tilininsano312/pubtube-mod4:develop` | 8000 | `/api/health` |
| M1 | `ghcr.io/sebasinmas/pubtube-modulo1:develop` | 8000 | `/api/content/health` |
| M2 | `ghcr.io/carloscienfuegos1/pubtube-modulo2:develop` | 8002 | `/api/events/health` |
| M3 | `pubtube-module3:local` (construida de `develop` en la VPS) | 8000 | `/api/publish/health` |

Para que Actions de los módulos descargue el Gateway y la VPS descargue las imágenes disponibles sin un PAT compartido, los propietarios deben cambiar a **público** cada paquete GHCR después de su primera publicación. GitHub crea paquetes privados por defecto. M3 publica `:develop` solo para amd64, mientras la VPS usa arm64; por ahora se construye desde la rama pública `develop` directamente en la VPS y WUD no lo actualiza. Cuando M3 publique arm64, podrá usar su paquete GHCR y WUD.

## Instrucciones para los tres equipos

1. Implementar una API HTTP en `0.0.0.0` con `GET /health` (2xx). Mantener sus pruebas y dependencias efímeras de CI.
2. Copiar [la plantilla de Actions](../examples/module-gateway-ci.yml) a `.github/workflows/gateway-integration.yml`. Adaptar el arranque del módulo y su smoke test. La plantilla descarga la imagen del Gateway, usa un JWT ficticio de CI y publica con `GITHUB_TOKEN`/`packages: write` solo tras pasar la integración en un push a `develop`.
3. Configurar estas variables de Actions:

| Variable | M1 | M2 | M3 |
| --- | --- | --- | --- |
| `MODULE_SLOT` | `1` | `2` | `3` |
| `MODULE_PORT` | `8000` | `8002` | `8000` |
| `GATEWAY_SMOKE_PATH` | `/api/content/health` | `/api/events/health` | `/api/publish/health` |

No configuren `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`, `GATEWAY_REPO_TOKEN`, `JWT_SECRET` ni contraseñas reales en Actions. `GITHUB_TOKEN` lo entrega GitHub automáticamente. La plantilla usa `docker run` para una API autónoma: M1 necesita levantar PostgreSQL y Garage efímeros; M2 necesita RabbitMQ para las pruebas que lo requieran. Esos servicios son parte del CI del módulo y no usan datos de producción.

## Contrato HTTP

- M1: `POST /api/content/init`, `GET /api/content/{sessionId}/part/{partNumber}`, `GET /api/content/upload/{sessionId}/status` y `POST /api/content/upload/{sessionId}/complete`, publicados bajo `/api/content/...`.
- M2: `GET /events/{correlation_id}`, publicado como `GET /api/events/{correlation_id}`. RabbitMQ por sí solo no satisface esta API HTTP.
- M3: `POST /api/publish/schedule` y `GET /api/publish/{publication_id}/status` en el servicio, publicados bajo las mismas rutas del Gateway. `POST /api/publish/{publication_id}/now` aún no está implementado por M3.
- Todos: `GET /health` devuelve 2xx y la API propaga `X-Correlation-Id`.

En producción el Gateway usa `http://module1-api:8000`, `http://module2-api:8002` y `http://module3-api:8000`. Los módulos no publican puertos al host. El Gateway conserva la validación JWT para las rutas protegidas; el acceso temporal de pruebas de M1, M2 y M3 se controla con `GATEWAY_PUBLIC_TEST_ROUTES`.

### Pruebas sin login

Los Compose activan `GATEWAY_PUBLIC_TEST_ROUTES=true` mientras se prueba la integración. Así se pueden llamar sin JWT las rutas bajo `/api/content` (M1), `/api/events` (M2) y `/api/publish` (M3), incluidas las operaciones que crean o modifican datos. Para volver a proteger las rutas de los tres módulos, poner `GATEWAY_PUBLIC_TEST_ROUTES=false` en `/opt/pubtube-mod4/.env` y recrear el Gateway con `docker compose -f docker-compose.prod.yml up -d gateway`. No se elimina la validación ni el secreto JWT.

```sh
curl -fsS http://localhost:8000/api/health
curl -fsS http://localhost:8000/api/content/health
curl -fsS http://localhost:8000/api/events/health
curl -fsS http://localhost:8000/api/publish/health
```

## Estado de los repositorios revisados

| Repositorio | Estado verificado | Pendiente |
| --- | --- | --- |
| [M1](https://github.com/sebasinmas/pubtube-modulo1) | API NestJS, `/health`, pipeline e imagen pública `:develop`. | Integrado en el Compose de producción; aplicar migraciones antes del primer arranque y de cambios de esquema. |
| [M2](https://github.com/CarlosCienfuegos1/PubTube-Modulo2) | API FastAPI, Event Store PostgreSQL, consumidor RabbitMQ, pipeline e imagen pública multi-arquitectura `:develop`. | Integrado en el Compose de producción; mantener sus credenciales y volúmenes privados. |
| [M3](https://github.com/NahuelCatrileo/DPMod3-2026) | API FastAPI, `/health`, programación, estado, PostgreSQL y Dockerfile; imagen `:develop` solo amd64. | Publicar arm64 y completar `/now`, YouTube real y transporte de eventos si se requieren. |

Las ramas por defecto son `main`: cada equipo debe usar `develop` para activar la publicación. WUD actualiza M1, M2 y el Gateway cuando cambia el digest de sus imágenes `:develop`; M3 continúa construyéndose localmente en la VPS.

## Servicio Dashboard del módulo D

El Dashboard se construye y publica por separado del Gateway con el tag
`ghcr.io/tilininsano312/pubtube-mod4:dashboard-develop`. El Compose de producción
lo conecta a la misma red privada y WUD vigila su digest de forma independiente.
El puerto `DASHBOARD_PORT` (8004 por defecto) no se publica en el host; el
Gateway usa `DASHBOARD_URL=http://dashboard-api:<puerto>`.

`GET /api/dashboard` es público y mantiene rate limiting, independientemente
de `GATEWAY_PUBLIC_TEST_ROUTES`. M1/M2/M3 conservan sus reglas existentes. El
Dashboard no monta secretos JWT. Una consulta válida devuelve 503 mientras
no se registre una fuente de publicaciones de M3 según el contrato acordado.
El contrato y los pasos de integración están en [dashboard-api.md](dashboard-api.md).

## VPS

Instalar [docker-compose.prod.yml](../docker-compose.prod.yml) en `/opt/pubtube-mod4` junto con los archivos de observabilidad. Crear `/opt/pubtube-mod4/secrets/jwt_secret` y `/opt/pubtube-mod4/secrets/wud_admin_password` con valores aleatorios y permisos restringidos antes del primer arranque. El Gateway lee `/run/secrets/jwt_secret` mediante `JWT_SECRET_FILE`; WUD usa el segundo archivo para crear su administrador inicial. `secrets/` está ignorado por Git.

WUD monta `/opt/pubtube-mod4` en la misma ruta para que el trigger de Compose encuentre el archivo Compose, los archivos de observabilidad y los secretos cuando recrea los servicios. Tiene acceso al socket Docker; solo el administrador de la VPS debe poder modificar ese Compose. `wud.watch.digest=true` permite detectar cambios del tag fijo `develop`.

M1, M2 y M3 están en el mismo Compose. Sus APIs usan `module1-api`,
`module2-api` y `module3-api` en `pubtube-network`; sus bases, Garage y
RabbitMQ están en redes internas y volúmenes independientes. Ninguna API de
módulo publica puertos al host. M3 aplica sus propias migraciones Alembic al
arrancar. M2 arranca un consumidor separado con la misma imagen para declarar
la topología de RabbitMQ y persistir los eventos en su PostgreSQL.

El visor de logs para los equipos está documentado en [`docs/log-access.md`](log-access.md). Cada cuenta de Dozzle queda filtrada por la etiqueta de su módulo y solo tiene permisos de lectura de logs.

M1 requiere variables de entorno para PostgreSQL y Garage. Crear `/opt/pubtube-mod4/.env` con `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `GARAGE_RPC_SECRET` y `GARAGE_ADMIN_TOKEN`; restringirlo con `chmod 600`. Las credenciales facilitadas para desarrollo se guardaron solo en el `.env` local ignorado por Git; para producción deben sustituirse por valores nuevos. `DATABASE_URL` se construye dentro del Compose con el host privado `db:5432`. Los secretos JWT y WUD siguen en archivos bajo `secrets/`.

El primer despliegue requiere las migraciones Drizzle: la imagen pública `:develop` de M1 solo contiene las dependencias de producción y no incluye `drizzle-kit`. El perfil `migrate` construye temporalmente la etapa `builder` desde la rama `develop` pública de M1. Ejecutar desde `/opt/pubtube-mod4`:

```sh
docker compose -f docker-compose.prod.yml up -d db garage
docker compose -f docker-compose.prod.yml --profile migrate run --rm --build module1-migrate
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec gateway python -c "import urllib.request; print(urllib.request.urlopen('http://module1-api:8000/health').read().decode())"
```

El último comando comprueba la conectividad interna. Con el modo de pruebas activo también se puede usar `/api/content/health` sin JWT. Repetir la migración antes de actualizar a una versión de M1 que cambie el esquema. Este mecanismo toma `develop` al construir, por lo que la imagen de migración y la de API deben corresponder al mismo commit; antes de una actualización con migraciones, coordinar una versión fijada con el equipo de M1. WUD puede actualizar la API automáticamente pero no ejecuta migraciones: hasta que M1 publique una imagen de migración ligada a la misma versión, las actualizaciones con cambio de esquema requieren coordinación manual.

Garage usa `module1/garage.toml` y el aprovisionador de buckets de M1 copiado en `module1/garage-setup.sh`; el Compose crea `videos`, `thumbnails` y la regla de limpieza de cargas multipart. El S3 interno está en `garage:3900`. Las URLs prefirmadas que genera actualmente M1 contienen ese nombre interno, por lo que un cliente externo no podrá subir partes hasta que M1 admita una URL pública de S3 con firma coherente y se configure una ruta pública hacia Garage.

### Configuración de M2

Crear `/opt/pubtube-mod4/envsModulos/envmodulo2` en la VPS con permisos `600`.
El archivo es privado y debe contener al menos `RABBITMQ_USER`, `RABBITMQ_PASS`,
`POSTGRES_DB`, `POSTGRES_USER` y `POSTGRES_PASSWORD`. RabbitMQ, la API y el
consumidor leen las credenciales de ese mismo archivo. Compose reemplaza los
hosts y puertos locales por `rabbitmq:5672` y `module2-db:5432`, y no publica
ninguno de esos servicios al host.

Levantar los servicios de M2 y comprobarlos con:

```sh
docker compose -f docker-compose.prod.yml up -d rabbitmq module2-db module2-api module2-event-store
docker compose -f docker-compose.prod.yml ps rabbitmq module2-db module2-api module2-event-store
docker compose -f docker-compose.prod.yml exec gateway python -c "import urllib.request; print(urllib.request.urlopen('http://module2-api:8002/health').read().decode())"
```

`module2-event-store` declara la topología de RabbitMQ al iniciar y mantiene el
consumidor que persiste eventos. La ruta pública `/api/events/health` y las
consultas `/api/events/{correlation_id}` quedan disponibles sin JWT mientras
`GATEWAY_PUBLIC_TEST_ROUTES=true`.

### Configuración de M3

Crear `/opt/pubtube-mod4/envsModulos/envmodulo3` en la VPS con los valores privados de M3. El archivo real está ignorado por Git y debe tener permisos `600`. Añadir `M3_POSTGRES_USER`, `M3_POSTGRES_PASSWORD` y `M3_POSTGRES_DB` a `/opt/pubtube-mod4/.env`; deben coincidir con `POSTGRES_*` y con las credenciales de `DATABASE_URL` del archivo de M3. La URL debe usar el host `postgres:5432`, alias privado de `module3-db`.

El entorno recibido está en `PUBLISHER_MODE=mock` y `EVENT_TRANSPORT=log`: la programación y el scheduler funcionan, pero no publica en YouTube ni entrega eventos a RabbitMQ. Compose fuerza `APP_ENV=prod` al arrancar M3. Las rutas OAuth necesitan un dominio público, credenciales de Google y rutas expuestas por el Gateway antes de habilitar `PUBLISHER_MODE=youtube`.

Después de `docker compose -f docker-compose.prod.yml up -d --build`, comprobar `docker compose -f docker-compose.prod.yml ps module3-api module3-db` y consultar `/api/publish/health` sin JWT mientras dure el modo de pruebas. La imagen local de M3 se reconstruye con `docker compose -f docker-compose.prod.yml build module3-api` al actualizar su rama `develop`; WUD no actualiza esta imagen local. El Gateway requiere publicar la versión de este repositorio que corrige el puerto y las rutas de M3.

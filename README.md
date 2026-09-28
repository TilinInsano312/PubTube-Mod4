# PubTube-Mod4

## Prometheus local

Levanta el Gateway y Prometheus con `docker compose up --build -d`. Prometheus queda en <http://localhost:9090> y las metricas del Gateway en <http://localhost:8000/metrics>. Comprueba la salud con `curl -fsS http://localhost:9090/-/healthy` y el scrape en `curl -fsS http://localhost:9090/api/v1/targets` (el job `pubtube-gateway` debe indicar `up`). `GATEWAY_PORT` define el puerto real de escucha del Gateway y se publica en el mismo puerto del host; Prometheus adapta automáticamente su target a ese valor. Por ejemplo, `GATEWAY_PORT=8010 docker compose up --build -d` publica el Gateway en `http://localhost:8010`. El puerto web de Prometheus se puede cambiar con `PROMETHEUS_PORT`.

Los futuros targets de M1/M2/M3 se agregan como jobs en `prometheus/prometheus.yml.template` cuando esos servicios expongan `/metrics`. Mantener labels de baja cardinalidad y no incluir `correlationId`, `eventId`, `userId`, `contentId`, emails ni titulos.

## Despliegue automático de `develop`

Cada push a `develop` ejecuta primero el CI. Si termina correctamente, GitHub Actions copia al servidor el commit exacto y ejecuta `docker compose up --detach --build --force-recreate --remove-orphans --wait --wait-timeout 120`, reconstruyendo y levantando todos los servicios definidos en `docker-compose.yml`.

Configura estos secretos en **Settings → Secrets and variables → Actions**:

- `DEPLOY_HOST`: hostname o dirección IPv4 del servidor.
- `DEPLOY_USER`: usuario SSH con permiso para ejecutar Docker Compose y escribir en el directorio de despliegue.
- `DEPLOY_SSH_KEY`: clave privada SSH cuya clave pública esté en `authorized_keys` de ese usuario.
- `DEPLOY_KNOWN_HOSTS`: línea de `known_hosts` del servidor, obtenida y verificada de forma confiable.

Las variables de repositorio `DEPLOY_PATH` y `DEPLOY_PORT` son opcionales; sus valores por defecto son `/opt/pubtube-mod4` y `22`. Si usas un puerto SSH distinto de `22`, configura `DEPLOY_KNOWN_HOSTS` con la entrada correspondiente a `[host]:puerto`. El servidor debe tener Docker Engine y una versión reciente del plugin `docker compose` que admita `up --wait`. La pipeline conserva archivos locales no versionados como `.env`; crea ese archivo en el directorio de despliegue antes del primer push si necesitas valores de entorno propios del servidor.

## Pipeline de integración para otros módulos

El archivo [`examples/module-gateway-ci.yml`](examples/module-gateway-ci.yml) es una plantilla para copiar al repositorio de cada módulo como `.github/workflows/gateway-integration.yml`. La pipeline construye la imagen del módulo, levanta el Gateway y el módulo en una red Docker temporal y prueba una ruta pública del Gateway con JWT de prueba. Los pasos de lint y pruebas propias del módulo deben agregarse antes del build de su imagen.

Configura estas variables en el repositorio del módulo:

- `MODULE_SLOT`: `1`, `2` o `3`, según `MODULE1_URL`, `MODULE2_URL` o `MODULE3_URL`.
- `MODULE_PORT`: puerto donde escucha el contenedor del módulo; por defecto `8001`.
- `MODULE_HEALTH_PATH`: endpoint de salud público del módulo; por defecto `/health`.
- `GATEWAY_SMOKE_PATH`: ruta GET pública que debe comprobarse a través del Gateway. Si se omite, la plantilla usa `/api/content` para M1, `/api/events/ci-correlation-id` para M2 o `/api/publish/ci-publication/status` para M3.
- `GATEWAY_REF`: rama del Gateway contra la que se valida; por defecto `develop`.

El contenedor del módulo debe tener un `Dockerfile`, escuchar en `0.0.0.0` y aceptar `PORT`; adapta el paso `Start module container` si usa otra configuración o requiere variables/dependencias adicionales. Si el repositorio del Gateway es privado, crea el secreto `GATEWAY_REPO_TOKEN` con acceso de solo lectura a ese repositorio. La plantilla reenvía un JWT de prueba firmado con una clave exclusiva de CI, por lo que los módulos que validen claims adicionales deben adaptar esa fixture.

# ADR-0009 — Acceso filtrado a logs con Dozzle y Docker Socket Proxy

- **Estado:** Aceptado
- **Fecha:** 2026-10-07

## Contexto

Los equipos de M1, M2 y M3 necesitan revisar los logs de sus APIs y del Gateway
directamente en la VPS para diagnosticar y correlacionar errores. Darles acceso
SSH con permisos Docker o montar `/var/run/docker.sock` en una interfaz web les
permitiría inspeccionar o modificar todos los contenedores del host.

La solución debe permitir lectura en vivo, separar la visibilidad por módulo,
mantener los secretos fuera del repositorio y funcionar sin añadir un sistema
de almacenamiento de logs distribuido para esta etapa.

## Decisión

Se adopta Dozzle `v11.3.0` como visor web de logs y
`tecnativa/docker-socket-proxy:v0.5.0` como intermediario entre Dozzle y Docker.

### Aislamiento del socket

Dozzle no monta el socket Docker directamente. Se conecta a
`docker-socket-proxy` mediante `DOZZLE_REMOTE_HOST` en una red interna.
El proxy habilita únicamente:

- `CONTAINERS=1` para listar contenedores y leer sus logs.
- `EVENTS=1` para recibir cambios y logs en vivo.
- `INFO=1` para la información básica del daemon.
- `POST=0` para bloquear operaciones de escritura.

El puerto `2375` del proxy no se publica en el host.

### Autenticación y filtros

Dozzle usa autenticación simple con un archivo Docker secret creado solo en la
VPS. Cada cuenta usa un filtro por etiqueta:

| Cuenta | Filtro | Visibilidad actual |
|---|---|---|
| `modulo1` | `label=pubtube.logs.module1` | `module1-api`, `gateway` |
| `modulo2` | `label=pubtube.logs.module2` | `module2-api`, `module2-event-store`, `gateway` |
| `modulo3` | `label=pubtube.logs.module3` | `module3-api`, `gateway` |

Las cuentas tienen `roles: none`, por lo que pueden consultar logs sin iniciar,
detener, eliminar contenedores ni abrir una shell. Las acciones, shell y MCP de
Dozzle también están deshabilitados mediante variables de entorno.

Las etiquetas de acceso se declaran en el Compose de producción y no en
archivos de entorno. Cada servicio de módulo tiene una etiqueta correspondiente
a su cuenta; el Gateway compartido lleva las tres:

```yaml
labels:
  pubtube.logs.module1: "true"
  pubtube.logs.module2: "true"
  pubtube.logs.module3: "true"
```

Las cuentas de M1, M2 y M3 ven los metadatos de solicitudes que aparecen en los
logs del Gateway para todos los módulos. El Gateway registra método, ruta,
estado, duración e identificadores de correlación/traza; no registra headers,
query strings ni cuerpos de solicitud. La ruta puede incluir identificadores de
recursos, por lo que las cuentas pueden inferir metadatos de tráfico de los
demás módulos. Los servicios de base de datos, mensajería, almacenamiento,
Dashboard y administración no llevan estas etiquetas de acceso.

### Exposición de red

Dozzle escucha en `127.0.0.1:8080` en la VPS. Los equipos acceden con un túnel
SSH:

```bash
ssh -N -L 8080:127.0.0.1:8080 modulo1-logs@IP_DE_LA_VPS
```

Después abren `http://localhost:8080`. No se publica el visor directamente en
Internet; una exposición externa requiere un reverse proxy HTTPS y una política
de firewall aprobada.

La VPS tiene tres cuentas dedicadas para ese túnel: `modulo1-logs`,
`modulo2-logs` y `modulo3-logs`. Sus bloques `Match` de OpenSSH habilitan autenticación por
contraseña solo para esas cuentas, `AllowTcpForwarding local`,
`PermitOpen 127.0.0.1:8080`, y deshabilitan shell, TTY, X11, agent forwarding y
túneles. Las cuentas no pertenecen a `docker` ni a `sudo` y usan
`ForceCommand /bin/false` para impedir comandos remotos.

### Credenciales y datos sensibles

El hash de usuarios se mantiene en
`/opt/pubtube-mod4/secrets/dozzle_users.yml` y las credenciales iniciales se
entregan fuera de Git. Las credenciales SSH de las cuentas restringidas se
mantienen en `/opt/pubtube-mod4/secrets/log_ssh_credentials.txt`; las de Dozzle
se mantienen en `/opt/pubtube-mod4/secrets/dozzle_credentials.txt`. Todos los
archivos tienen permisos `600`. No se registran contraseñas, tokens JWT, URLs
con credenciales ni contenido sensible.

Para correlacionar una solicitud entre Gateway y módulo, los equipos deben
compartir el mismo `X-Correlation-Id` y la hora UTC de la prueba.

## Alternativas consideradas

### Montar `/var/run/docker.sock` directamente en Dozzle

Se descarta porque el socket Docker concede un nivel de control equivalente al
host y una vulnerabilidad de la interfaz web ampliaría el impacto.

### Entregar acceso SSH con permisos Docker

Se descarta porque permitiría que un módulo inspeccione, ejecute o modifique
contenedores fuera de su ámbito.

### Loki y Grafana como primera implementación

Se reserva para una fase posterior. Aporta retención, búsquedas y agregación
distribuida, pero requiere más infraestructura y configuración para resolver la
necesidad inmediata de logs en vivo de una VPS.

### Publicar Dozzle en un puerto externo sin túnel

Se descarta como valor por defecto porque expone una superficie administrativa
adicional. Si se necesita acceso remoto directo, debe hacerse detrás de HTTPS,
autenticación y firewall.

## Consecuencias

### Positivas

- M1, M2 y M3 pueden ver los logs en vivo de su API y del Gateway sin acceso
  Docker global.
- El filtrado por etiquetas evita que una cuenta vea los contenedores de otro
  módulo.
- El socket proxy reduce las operaciones Docker disponibles para el visor.
- El acceso funciona sin introducir un backend de logs persistente.
- La configuración y los usuarios pueden recrearse desde el Compose y la
  plantilla sin guardar contraseñas en Git.

### Negativas y límites

- La retención queda limitada a los logs disponibles en Docker y al ciclo de
  vida de cada contenedor.
- Los equipos necesitan una de las cuentas SSH restringidas o un acceso VPN
  para abrir el túnel.
- Los logs del Gateway exponen a todos los módulos metadatos de tráfico de todos
  los módulos, y sus rutas pueden incluir identificadores; no incluyen headers,
  query strings ni cuerpos de solicitud.
- El filtrado no cubre los logs de PostgreSQL, Garage, RabbitMQ, Dashboard, WUD
  ni el socket proxy.
- El proxy Docker sigue siendo un componente privilegiado de infraestructura y
  debe mantenerse en una red no publicada.

## Referencias

- [Configuración del visor](../docs/log-access.md)
- [Plantilla de usuarios](../docs/dozzle-users.yml.example)
- [Compose de producción](../docker-compose.prod.yml)
- [Dozzle — autenticación simple](https://dozzle.dev/guide/authentication/simple)
- [Docker Socket Proxy](https://github.com/Tecnativa/docker-socket-proxy)

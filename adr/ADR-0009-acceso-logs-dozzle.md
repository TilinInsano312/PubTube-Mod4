# ADR-0009 — Acceso filtrado a logs con Dozzle y Docker Socket Proxy

- **Estado:** Aceptado
- **Fecha:** 2026-10-07

## Contexto

Los equipos de M1 y M3 necesitan revisar los logs de sus APIs directamente en
la VPS para diagnosticar errores. Darles acceso SSH con permisos Docker o
montar `/var/run/docker.sock` en una interfaz web les permitiría inspeccionar o
modificar todos los contenedores del host.

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
| `modulo1` | `label=pubtube.logs.module=module1` | `module1-api` |
| `modulo3` | `label=pubtube.logs.module=module3` | `module3-api` |

Las cuentas tienen `roles: none`, por lo que pueden consultar logs sin iniciar,
detener, eliminar contenedores ni abrir una shell. Las acciones, shell y MCP de
Dozzle también están deshabilitados mediante variables de entorno.

Las etiquetas se declaran en el Compose de producción y no en archivos de
entorno:

```yaml
labels:
  pubtube.logs.module: "module1"
```

El mismo patrón se usa para M3.

### Exposición de red

Dozzle escucha en `127.0.0.1:8080` en la VPS. Los equipos acceden con un túnel
SSH:

```bash
ssh -N -L 8080:127.0.0.1:8080 modulo1-logs@IP_DE_LA_VPS
```

Después abren `http://localhost:8080`. No se publica el visor directamente en
Internet; una exposición externa requiere un reverse proxy HTTPS y una política
de firewall aprobada.

La VPS tiene dos cuentas dedicadas para ese túnel: `modulo1-logs` y
`modulo3-logs`. Sus bloques `Match` de OpenSSH habilitan autenticación por
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

Los usuarios de módulo ven actualmente solo los contenedores de sus APIs. Las
bases de datos, Garage, Gateway, WUD y el socket proxy quedan fuera de sus
filtros.

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

- M1 y M3 pueden ver sus logs en vivo sin acceso Docker global.
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
- El filtrado actual cubre las APIs, no los logs de PostgreSQL, Garage o Gateway.
- El proxy Docker sigue siendo un componente privilegiado de infraestructura y
  debe mantenerse en una red no publicada.

## Referencias

- [Configuración del visor](../docs/log-access.md)
- [Plantilla de usuarios](../docs/dozzle-users.yml.example)
- [Compose de producción](../docker-compose.prod.yml)
- [Dozzle — autenticación simple](https://dozzle.dev/guide/authentication/simple)
- [Docker Socket Proxy](https://github.com/Tecnativa/docker-socket-proxy)

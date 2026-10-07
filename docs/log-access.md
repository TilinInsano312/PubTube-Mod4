# Acceso de equipos a logs de la VPS

El Compose de producción incluye Dozzle para que cada equipo consulte en vivo
los logs de su API. Dozzle no recibe el socket Docker directamente: se conecta
a `docker-socket-proxy`, que solo permite listar contenedores, leer logs,
recibir eventos y consultar información del daemon. Las acciones y la shell de
Dozzle están deshabilitadas.

## Preparación en la VPS

Crear el archivo de usuarios fuera de Git:

```sh
cd /opt/pubtube-mod4
install -d -m 700 secrets
docker run --rm -it amir20/dozzle:v11.3.0 generate modulo1 \
  --name "Equipo M1" \
  --user-filter "label=pubtube.logs.module=module1" \
  --user-roles none > /tmp/dozzle-m1.yml
docker run --rm -it amir20/dozzle:v11.3.0 generate modulo2 \
  --name "Equipo M2" \
  --user-filter "label=pubtube.logs.module=module2" \
  --user-roles none > /tmp/dozzle-m2.yml
docker run --rm -it amir20/dozzle:v11.3.0 generate modulo3 \
  --name "Equipo M3" \
  --user-filter "label=pubtube.logs.module=module3" \
  --user-roles none > /tmp/dozzle-m3.yml
```

Cada comando pide una contraseña. Combinar los tres usuarios bajo una sola
clave `users:` en `secrets/dozzle_users.yml`, usando la plantilla
[`dozzle-users.yml.example`](dozzle-users.yml.example), y eliminar los
temporales. El archivo debe quedar así protegido:

```sh
chmod 600 /opt/pubtube-mod4/secrets/dozzle_users.yml
```

El `filter` de cada usuario es el límite de visibilidad. M1, M2 y M3 solo
verán los contenedores etiquetados con su propio valor de
`pubtube.logs.module`; M2 incluye su API y su consumidor de Event Store. Las
bases, RabbitMQ, Garage, Gateway, WUD y el proxy del socket no aparecen para
esas cuentas.

## Arranque

Por seguridad, el puerto queda ligado a `127.0.0.1` por defecto. Para usarlo
desde el equipo administrador mediante un túnel SSH:

```sh
ssh -N -L 8080:127.0.0.1:8080 modulo1-logs@IP_DE_LA_VPS
```

Luego abrir `http://localhost:8080`. Si ya existe un reverse proxy HTTPS y una
red privada, se puede publicar el puerto en la interfaz adecuada definiendo
`DOZZLE_BIND_ADDRESS` en `.env`; no expongas el puerto sin HTTPS y autenticación.

El túnel SSH y el login de Dozzle son credenciales distintas. Las cuentas
dedicadas son `modulo1-logs`, `modulo2-logs` y `modulo3-logs`; deben aceptar
contraseña únicamente dentro de su bloque `Match` de SSH y no tener shell,
`sudo`, acceso al socket Docker ni permisos para reenviar otros destinos. Solo
pueden abrir el destino `127.0.0.1:8080`.

Las contraseñas SSH iniciales están en
`/opt/pubtube-mod4/secrets/log_ssh_credentials.txt`, fuera de Git y con permisos
`600`. Las contraseñas de Dozzle están en
`/opt/pubtube-mod4/secrets/dozzle_credentials.txt`; no son intercambiables.
El error `Permission denied (publickey)` aparece cuando se intenta usar una
clave con una de estas cuentas restringidas: se debe usar la contraseña SSH
correspondiente.

Si se prefiere autenticación por clave, cada equipo puede generar su propio par
y entregar únicamente el archivo `.pub` al administrador:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/pubtube-modulo1-logs -C "modulo1-logs"
cat ~/.ssh/pubtube-modulo1-logs.pub
```

Para M3 se puede usar otro nombre, por ejemplo
`~/.ssh/pubtube-modulo3-logs`. La clave privada debe permanecer en el equipo
que la generó y nunca debe enviarse por chat. No se debe compartir una clave
privada del usuario `ubuntu`, porque ese usuario tiene permisos administrativos
y acceso al socket Docker.

Para M2, usar por ejemplo
`~/.ssh/pubtube-modulo2-logs` y la cuenta SSH `modulo2-logs`.

Cuando la clave ya esté autorizada, el equipo usa su archivo privado así:

```sh
ssh -i ~/.ssh/pubtube-modulo1-logs \
  -N -L 8080:127.0.0.1:8080 usuario-logs@IP_DE_LA_VPS
```

Levantar el visor:

```sh
docker compose -f docker-compose.prod.yml up -d docker-socket-proxy dozzle
docker compose -f docker-compose.prod.yml ps docker-socket-proxy dozzle
```

Tras una actualización del Compose, comprobar que el servicio sigue usando
`DOZZLE_REMOTE_HOST=tcp://docker-socket-proxy:2375|pubtube-vps` y que el proxy
no publica el puerto 2375 al host.

## Correlación de errores

Los equipos deben enviar un `X-Correlation-Id` al probar el Gateway y compartir
ese valor junto con la hora UTC. Así pueden buscar la misma solicitud en los
logs del Gateway y del módulo. No registrar tokens JWT, contraseñas, URLs con
credenciales ni contenido sensible en las aplicaciones.

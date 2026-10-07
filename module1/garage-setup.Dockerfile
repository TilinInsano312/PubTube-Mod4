# Imagen para el contenedor one-shot garage-setup (ver scripts/garage-setup.sh).
# La imagen oficial de Garage es distroless, así que el aprovisionamiento corre
# en Alpine con curl + jq, instalados una sola vez al construir la imagen.
FROM alpine:3.21
RUN apk add --no-cache curl jq
COPY garage-setup.sh /garage-setup.sh
ENTRYPOINT ["/bin/sh", "/garage-setup.sh"]

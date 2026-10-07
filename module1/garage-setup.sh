#!/bin/sh
# garage-setup.sh
# Provisiona los buckets de un nodo Garage single-node y concede permisos a la
# access key. El layout y la key los crea el propio servidor al arrancar con
# `server --single-node --default-bucket`.
#
# Corre en la imagen garage-setup (Alpine + curl + jq) definida en los
# docker-compose. Es idempotente: puede ejecutarse en cada `up`.
#
# Variables de entorno requeridas:
#   GARAGE_ADMIN_URL   — ej: http://garage:3903
#   GARAGE_ADMIN_TOKEN — mismo token con el que arranca el servidor
#   MINIO_ACCESS_KEY   — access key S3 que recibe los permisos
#   MINIO_BUCKET_CONTENT    — nombre del bucket de contenido
#   MINIO_BUCKET_THUMBNAILS — nombre del bucket de miniaturas
#   GARAGE_S3_URL      — API S3 de Garage, ej: http://garage:3900
#   MINIO_SECRET_KEY   — secret de la access key (firma SigV4 del lifecycle)
# Opcional:
#   GARAGE_SETUP_TIMEOUT — segundos máximos esperando la Admin API (default 60)
#   GARAGE_S3_REGION     — s3_region de garage.toml (default us-east-1)
#   GARAGE_MULTIPART_ABORT_DAYS — días tras los que Garage aborta multipart
#                                 incompletos del bucket de contenido (default 7)

set -eu

ADMIN="${GARAGE_ADMIN_URL:?GARAGE_ADMIN_URL es requerida}"
TOKEN="${GARAGE_ADMIN_TOKEN:?GARAGE_ADMIN_TOKEN es requerida}"
KEY="${MINIO_ACCESS_KEY:?MINIO_ACCESS_KEY es requerida}"
TIMEOUT="${GARAGE_SETUP_TIMEOUT:-60}"
S3="${GARAGE_S3_URL:?GARAGE_S3_URL es requerida}"
SECRET="${MINIO_SECRET_KEY:?MINIO_SECRET_KEY es requerida}"
REGION="${GARAGE_S3_REGION:-us-east-1}"
ABORT_DAYS="${GARAGE_MULTIPART_ABORT_DAYS:-7}"
case "${ABORT_DAYS}" in
  '' | *[!0-9]* | 0)
    echo "✗ GARAGE_MULTIPART_ABORT_DAYS debe ser un entero positivo (recibido: '${ABORT_DAYS}')." >&2
    exit 1
    ;;
esac

admin_get() {
  curl -sf -H "Authorization: Bearer ${TOKEN}" "${ADMIN}$1"
}

admin_post() {
  curl -sf -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    --data-raw "$2" \
    "${ADMIN}$1"
}

# ── 1. Esperar a que la Admin API responda (con límite de tiempo) ────────────
echo "→ Esperando a que Garage acepte conexiones en ${ADMIN} (máx. ${TIMEOUT}s)..."
ELAPSED=0
until admin_get "/v2/GetClusterHealth" >/dev/null 2>&1; do
  if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "✗ Garage no respondió en ${TIMEOUT}s (¿token o URL incorrectos?)." >&2
    exit 1
  fi
  sleep 1
  ELAPSED=$((ELAPSED + 1))
done
echo "✓ Garage listo."

# ── 2. Asegurar existencia de buckets y permisos ─────────────────────────────
for BUCKET in "${MINIO_BUCKET_CONTENT:-}" "${MINIO_BUCKET_THUMBNAILS:-}"; do
  [ -z "${BUCKET}" ] && continue

  # GetBucketInfo responde 404 si el bucket no existe; no es un error.
  BUCKET_ID=$(admin_get "/v2/GetBucketInfo?globalAlias=${BUCKET}" 2>/dev/null \
    | jq -r '.id // empty' || true)

  if [ -z "${BUCKET_ID}" ]; then
    echo "→ Creando bucket '${BUCKET}'..."
    RESPONSE=$(admin_post "/v2/CreateBucket" \
      "$(jq -nc --arg alias "${BUCKET}" '{globalAlias: $alias}')")
    BUCKET_ID=$(printf '%s' "${RESPONSE}" | jq -r '.id // empty')
    if [ -z "${BUCKET_ID}" ]; then
      echo "✗ No se pudo crear el bucket '${BUCKET}': ${RESPONSE}" >&2
      exit 1
    fi
  else
    echo "✓ Bucket '${BUCKET}' ya existe (ID: ${BUCKET_ID})."
  fi

  echo "→ Concediendo permisos a '${KEY}' en bucket '${BUCKET}'..."
  admin_post "/v2/AllowBucketKey" "$(jq -nc \
    --arg bid "${BUCKET_ID}" \
    --arg kid "${KEY}" \
    '{bucketId: $bid, accessKeyId: $kid, permissions: {read: true, write: true, owner: true}}')" \
    >/dev/null
  echo "✓ Permisos listos para '${BUCKET}'."
done

# ── 3. Lifecycle: abortar multipart incompletos del bucket de contenido ─────
# Las cargas resumibles abandonadas dejan partes ocupando disco. Garage soporta
# de la API de lifecycle solo AbortIncompleteMultipartUpload y Expiration
# (docs: reference-manual/s3-compatibility). Es una API S3, no de admin, así
# que se firma con SigV4. PUT reemplaza la configuración: es idempotente.
if [ -n "${MINIO_BUCKET_CONTENT:-}" ]; then
  echo "→ Configurando lifecycle de '${MINIO_BUCKET_CONTENT}': abortar multipart incompletos tras ${ABORT_DAYS} días..."
  LIFECYCLE="<LifecycleConfiguration><Rule><ID>abortar-multipart-incompletos</ID><Status>Enabled</Status><Filter></Filter><AbortIncompleteMultipartUpload><DaysAfterInitiation>${ABORT_DAYS}</DaysAfterInitiation></AbortIncompleteMultipartUpload></Rule></LifecycleConfiguration>"
  MD5=$(printf '%s' "${LIFECYCLE}" | md5sum | cut -d' ' -f1 | xxd -r -p | base64)

  # Las credenciales van por stdin (-K -) para no exponerlas en la lista de
  # procesos ni en los logs.
  s3_curl() {
    printf 'user = "%s:%s"\n' "${KEY}" "${SECRET}" \
      | curl -sf -K - --aws-sigv4 "aws:amz:${REGION}:s3" "$@"
  }

  s3_curl -X PUT \
    -H "Content-MD5: ${MD5}" \
    -H "Content-Type: application/xml" \
    --data-raw "${LIFECYCLE}" \
    "${S3}/${MINIO_BUCKET_CONTENT}?lifecycle" >/dev/null || {
    echo "✗ Garage rechazó PutBucketLifecycleConfiguration en '${MINIO_BUCKET_CONTENT}'." >&2
    exit 1
  }

  if ! s3_curl "${S3}/${MINIO_BUCKET_CONTENT}?lifecycle" \
    | grep -q "<DaysAfterInitiation>${ABORT_DAYS}</DaysAfterInitiation>"; then
    echo "✗ Garage no devolvió la regla de lifecycle esperada." >&2
    exit 1
  fi
  echo "✓ Lifecycle listo para '${MINIO_BUCKET_CONTENT}'."
fi

echo ""
echo "✅ Aprovisionamiento de Garage completo."

#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

export GATEWAY_PORT="${GATEWAY_PORT:-8000}"
export JWT_SECRET="${JWT_SECRET:-demo-secret-for-local-testing-only}"
export JWT_ALGORITHM="${JWT_ALGORITHM:-HS256}"

echo "Levantando el Gateway..."
if ! docker compose up -d --build gateway >/dev/null 2>&1; then
    echo "No se pudo levantar el Gateway." >&2
    docker compose logs --tail=50 gateway >&2
    exit 1
fi

for attempt in {1..30}; do
    if curl -fsS "http://127.0.0.1:${GATEWAY_PORT}/api/health" >/dev/null 2>&1; then
        break
    fi

    if [[ "${attempt}" -eq 30 ]]; then
        echo "El Gateway no estuvo disponible a tiempo." >&2
        docker compose logs --tail=50 gateway >&2
        exit 1
    fi

    sleep 1
done

TOKEN="$(
    docker compose exec -T gateway python <<'PY'
import os
import time

import jwt


secret = os.environ["JWT_SECRET"]
algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
payload = {
    "sub": "user-123",
    "user_id": "account-456",
    "role": "editor",
    "exp": int(time.time()) + 300,
}
print(jwt.encode(payload, secret, algorithm=algorithm))
PY
)"

if [[ -z "${TOKEN}" ]]; then
    echo "No se pudo generar el JWT de demostración." >&2
    exit 1
fi

echo
echo "=== Ruta pública: /api/health (esperado: 200) ==="
curl -sS -i "http://127.0.0.1:${GATEWAY_PORT}/api/health"

echo
echo "=== Sin JWT (esperado: 401) ==="
curl -sS -i "http://127.0.0.1:${GATEWAY_PORT}/api/demo/protected"

echo
echo "=== JWT inválido (esperado: 401) ==="
curl -sS -i \
    -H "Authorization: Bearer token-invalido" \
    "http://127.0.0.1:${GATEWAY_PORT}/api/demo/protected"

echo
echo "=== JWT válido (esperado: 200) ==="
curl -sS -i \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Correlation-Id: demo-presentacion" \
    "http://127.0.0.1:${GATEWAY_PORT}/api/demo/protected"

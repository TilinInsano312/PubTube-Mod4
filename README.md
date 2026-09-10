# PubTube-Mod4

## Endpoint demo de autenticación JWT

El Gateway incluye una ruta falsa para demostrar el flujo completo de autenticación:

```text
GET /api/demo/protected
```

La ruta está protegida automáticamente por `JWTAuthenticationMiddleware`. Sin token,
responde `401 Unauthorized`; con un JWT válido, devuelve `200` y muestra los claims
que el middleware dejó disponibles para la ruta.

Para probarla localmente, configura un secreto compartido:

```bash
export JWT_SECRET='demo-secret-for-local-testing-only'
docker compose up --build gateway
```

Genera un token de prueba usando el mismo secreto y algoritmo:

```bash
TOKEN=$(docker run --rm pubtube-mod4-gateway:latest python -c "from datetime import datetime, timedelta, timezone; import jwt; print(jwt.encode({'sub':'user-123','user_id':'account-456','role':'editor','exp':datetime.now(timezone.utc)+timedelta(minutes=5)}, 'demo-secret-for-local-testing-only', algorithm='HS256'))")
```

Luego compara ambas respuestas:

```bash
curl -i http://localhost:8000/api/demo/protected
curl -i -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/demo/protected
```

El endpoint es únicamente de demostración y no debe mantenerse como una ruta de negocio
en un despliegue productivo.

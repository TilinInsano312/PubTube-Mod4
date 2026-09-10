# PubTube-Mod4

## Endpoint demo de autenticación JWT

El Gateway incluye una ruta falsa para demostrar el flujo completo de autenticación:

```text
GET /api/demo/protected
```

La ruta está protegida automáticamente por `JWTAuthenticationMiddleware`. Sin token,
responde `401 Unauthorized`; con un JWT válido, devuelve `200` y muestra los claims
que el middleware dejó disponibles para la ruta.

La demostración completa se puede ejecutar con un solo comando desde la raíz del
repositorio:

```bash
bash scripts/demo-auth.sh
```

El script levanta el Gateway, genera un JWT efímero dentro del contenedor y muestra
automáticamente los casos de ruta pública, solicitud sin token, token inválido y token
válido. También acepta un secreto propio si se desea:

```bash
JWT_SECRET='mi-secreto-local' bash scripts/demo-auth.sh
```

El endpoint es únicamente de demostración y no debe mantenerse como una ruta de negocio
en un despliegue productivo.

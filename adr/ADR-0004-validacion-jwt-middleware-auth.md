# ADR-0004 — Validación de JWT mediante middleware de autenticación

- **Estado:** Aceptado
- **Fecha:** 2026-09-03

## Contexto

El API Gateway es el punto de entrada para las solicitudes HTTP de PubTube. Las rutas protegidas deben validar la identidad de quien realiza la solicitud antes de que esta llegue al enrutamiento o a los módulos downstream.

El ADR-0001 establece el uso de OAuth 2.0 + JWT y PyJWT para la autenticación. La implementación del Gateway necesita una decisión adicional sobre el lugar y la forma en que se validarán los tokens, cómo se identificarán las rutas públicas y cómo se entregarán los claims a los componentes posteriores.

También es necesario que los fallos de autenticación mantengan el `X-Correlation-Id`, para poder rastrearlos sin registrar tokens ni otros secretos.

## Decisión

Se adopta un middleware global de autenticación (`JWTAuthenticationMiddleware`) en el API Gateway.

### Aplicación global y rutas públicas

El middleware se registra en la aplicación principal y protege todas las rutas por defecto. Solo se omite la autenticación para la siguiente lista explícita de rutas públicas:

- `/api/health`
- `/api/health/`
- `/docs`
- `/docs/oauth2-redirect`
- `/redoc`
- `/openapi.json`

Las nuevas rutas se considerarán protegidas automáticamente y solo serán públicas si se agregan de forma explícita a esta lista.

### Extracción y validación del token

El cliente debe enviar el token mediante el encabezado:

```http
Authorization: Bearer <jwt>
```

El esquema `Bearer` se acepta sin distinguir mayúsculas y minúsculas, pero el encabezado debe contener exactamente el esquema y un token. Los encabezados ausentes o malformados se rechazan con `401 Unauthorized`.

PyJWT valida el token usando:

- `JWT_SECRET`, cargado desde la configuración del entorno y compartido con el emisor confiable.
- `JWT_ALGORITHM`, configurable por entorno y con valor predeterminado `HS256`.
- La firma del token.
- El claim `exp`, que es obligatorio.
- La fecha de expiración del token.

Si falta el secreto o el algoritmo configurado, las rutas protegidas se rechazan. Los claims decodificados deben ser un objeto tipo diccionario; cualquier token inválido, alterado, expirado o incompatible se trata de la misma manera.

### Propagación de identidad

Después de una validación exitosa, los claims se almacenan en `request.state` para que las rutas y los componentes downstream puedan utilizarlos:

- `request.state.jwt_claims`: conjunto completo de claims.
- `request.state.user`: alias de compatibilidad para los claims.
- `request.state.user_id`: valor de `user_id` o, como fallback, `sub`.
- `request.state.role`: valor de `role`, si está presente.

El middleware no decide permisos por rol. La autorización específica de cada operación queda fuera de esta decisión y deberá implementarse cuando existan rutas que la requieran.

### Respuesta ante fallos y orden del middleware

Todos los fallos de autenticación responden con el mismo contrato:

```json
{
  "detail": "Invalid authentication credentials"
}
```

La respuesta tiene código `401` y el encabezado `WWW-Authenticate: Bearer`. No se devuelven detalles que permitan distinguir si falló el formato, la firma, la configuración o la expiración, y no se registran JWT completos, tokens ni secretos.

El middleware de `X-Correlation-Id` envuelve al middleware JWT en la aplicación principal. Así, las respuestas de autenticación fallida también reciben un identificador de correlación.

## Alternativas consideradas

### Dependencias de FastAPI por ruta

Usar `Depends` u otra dependencia de autenticación en cada endpoint permitiría declarar la seguridad junto a cada ruta. Se descarta como mecanismo principal porque una ruta nueva podría omitir accidentalmente la dependencia y quedar expuesta.

### Validación en cada módulo downstream

Validar el JWT en cada módulo distribuiría la responsabilidad y duplicaría la lógica. Se descarta porque el Gateway debe establecer la primera frontera de autenticación y evitar que solicitudes inválidas avancen en la arquitectura.

### Introspección remota o un servicio externo de identidad

Una introspección remota permitiría centralizar revocación y políticas, pero agrega una dependencia de red, latencia y configuración que no forman parte del alcance actual del Gateway. Podrá evaluarse cuando se requiera gestión centralizada del ciclo de vida de tokens.

### Validación únicamente en un proxy de infraestructura

Delegar la validación al reverse proxy reduciría lógica en la aplicación, pero introduciría una dependencia específica del despliegue y no resolvería por sí solo la propagación de claims al código de FastAPI.

## Consecuencias

### Positivas

- Todas las rutas nuevas quedan protegidas por defecto.
- La validación se implementa en un único punto del Gateway.
- Las rutas públicas quedan identificadas de manera explícita y revisable.
- Las rutas autenticadas reciben una identidad común mediante `request.state`.
- Los clientes reciben un contrato HTTP consistente para fallos de autenticación.
- Los errores de autenticación conservan `X-Correlation-Id` para su trazabilidad.

### Negativas y límites

- La lista de rutas públicas debe mantenerse cuando se agreguen endpoints técnicos o de documentación.
- El secreto simétrico debe distribuirse y rotarse de forma segura fuera del repositorio; el Gateway confía en el emisor que utiliza ese secreto.
- La implementación actual valida firma y expiración, pero no exige ni valida `iss`, `aud` o `nbf`.
- El middleware no emite, renueva ni revoca tokens.
- La autenticación y la autorización permanecen separadas: disponer de un claim `role` no concede permisos por sí mismo.
- Mientras `JWT_SECRET` no esté configurado, las rutas protegidas responderán `401`; las rutas públicas seguirán disponibles.

## Referencias

- [ADR-0001 — Selección del stack tecnológico](ADR-0001-stack-tecnologico.md)
- [`JWTAuthenticationMiddleware`](../../gateway/app/middleware/jwt_auth.py)
- [Pruebas de autenticación JWT](../../gateway/tests/test_jwt_auth.py)

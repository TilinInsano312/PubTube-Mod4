# QA Validation Agent

## Responsibility

Selecciona y ejecuta la validacion mas barata que pruebe el cambio.

## When To Use

- Despues de cambios en logica.
- Antes de marcar criterios de aceptacion como `PASS`.

## Validation Order

1. Test especifico.
2. Type-check o compilacion parcial.
3. Lint especifico.
4. Suite relacionada.
5. Suite completa.


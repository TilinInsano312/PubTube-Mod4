# ADR-0004 — Uso de Google Style Docstrings

## Estado

Aceptada · 2026-08-31

## Contexto

El proyecto requiere mantener una documentación clara, consistente y fácil de consultar dentro del código fuente.

Python permite utilizar docstrings para documentar módulos, clases, métodos y funciones. Sin embargo, existen distintos formatos para estructurar esta documentación, como Sphinx/reStructuredText, NumPy Style y Google Style.

Es necesario adoptar un único estándar para evitar diferencias de formato entre desarrolladores y facilitar tanto la lectura del código como una eventual generación automática de documentación.

## Alternativas consideradas

1. **Sphinx/reStructuredText** — ofrece una integración directa con Sphinx y permite documentación detallada, pero utiliza etiquetas como `:param:`, `:return:` y `:raises:`, haciendo los docstrings menos naturales de leer directamente desde el código.

2. **NumPy Style** — posee una estructura clara y completa, especialmente apropiada para proyectos científicos, matemáticos o de análisis de datos, pero puede resultar más extensa de lo necesario para este proyecto.

3. **Google Style Docstrings** — utiliza una estructura simple mediante secciones como `Args`, `Returns` y `Raises`. Es fácil de leer directamente desde el código y compatible con herramientas de generación automática de documentación.

## Decisión

Se adopta **Google Style Docstrings** como estándar oficial para la documentación del código Python del proyecto.

Los docstrings deberán utilizar este formato de manera consistente en módulos, clases, métodos y funciones que requieran documentación.

Cuando corresponda, se utilizarán las siguientes secciones:

* `Args:` para describir los parámetros recibidos.
* `Returns:` para describir el valor retornado.
* `Raises:` para documentar las excepciones relevantes.
* `Attributes:` para describir atributos importantes de una clase.

Ejemplo:

```python
def calcular_riesgo(datos: dict, historial: list) -> float:
    """Calcula el nivel de riesgo a partir de los datos disponibles.

    Args:
        datos: Datos actuales utilizados para realizar el cálculo.
        historial: Registros históricos asociados al usuario.

    Returns:
        Nivel de riesgo calculado entre 0.0 y 1.0.

    Raises:
        ValueError: Si los datos necesarios para realizar el cálculo
            no están disponibles.
    """
```

En funciones simples se permitirá utilizar un docstring de una sola línea cuando sea suficiente para describir su propósito:

```python
def obtener_usuario(usuario_id: int) -> Usuario:
    """Obtiene un usuario a partir de su identificador."""
```

Se priorizarán los docstrings en:

* Clases y métodos públicos.
* Servicios.
* Repositorios.
* Endpoints.
* Funciones de lógica de negocio.
* Funciones cuyo comportamiento no sea evidente únicamente leyendo el código.

No será obligatorio agregar docstrings extensos a funciones privadas o auxiliares triviales cuando su propósito sea evidente.

## Consecuencias

El proyecto contará con un formato uniforme para la documentación del código, facilitando su lectura, mantenimiento y revisión por distintos integrantes del equipo.

Google Style permite mantener los docstrings relativamente limpios y legibles sin agregar una sintaxis excesivamente compleja.

Además, será posible utilizar estos docstrings posteriormente para generar documentación automática mediante herramientas compatibles, como Sphinx con Napoleon o MkDocs.

Como costo, los desarrolladores deberán mantener los docstrings actualizados cuando cambien los parámetros, valores de retorno, excepciones o comportamiento de las funciones.

Durante las revisiones de código también deberá verificarse que los nuevos componentes respeten el formato Google Style definido en este ADR.


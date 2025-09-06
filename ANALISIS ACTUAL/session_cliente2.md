## Análisis del Archivo: `session_cliente2.py` (06/09/2025)

1) Propósito

- Variante del Cliente con “automatización guiada (Paso 1)”: además de inyectar cookie y abrir sesión, intenta localizar y abrir el menú “Respuesta Glosas” con esperas explícitas (By/EC/WebDriverWait) y ventana maximizada.

2) Diferencias respecto a `session_cliente.py`

- Añade `--start-maximized` y esperas hasta 20s para elementos clave.
- Implementa `Paso 1`: clic en `a[href="#respuestaGlo"]` con manejo de `TimeoutException`.
- Sigue usando `detach=True` para dejar el navegador abierto.

3) Estado

- Experimental; útil para diagnóstico GUI del sitio y primeros pasos guiados.

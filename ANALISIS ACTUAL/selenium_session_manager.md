## Análisis del Archivo: `server_logic/selenium_session_manager.py` (06/09/2025)

1) Propósito

- Iniciar sesión en `https://vco.ctamedicas.com` en modo headless, capturar la cookie `PHPSESSID`, sincronizarla en Notion (borrando bloque previo), crear señal `.sync_success.flag` y mantener la sesión viva con refrescos periódicos durante varias horas.

2) Flujo principal (`capture_sync_and_refresh_session(base_path) -> webdriver`)

- Carga `config.ini` desde `base_path`; arma headers Notion.
- Verifica `chrome-win64/chrome.exe` y `chromedriver.exe` en `base_path`.
- Lanza Chrome headless con tamaño fijo y extensiones deshabilitadas.
- Login: completa usuario/clave, envía el formulario y valida “Bienvenido”.
- Obtiene `PHPSESSID` y lo publica en Notion como `Session PHPSESSID: <value> | LastUpdate: <iso>`.
- Crea `.sync_success.flag` en `base_path` para “handshake” con `main_gui.py`.
- Bucle de refresco: cada N minutos hace `driver.refresh()` y actualiza Notion con misma cookie.
- Devuelve el `driver` abierto; el cierre se maneja externamente (p. ej., `tray_app` al salir).

3) CLI de prueba

- `python server_logic/selenium_session_manager.py --base-path=...`

4) Consideraciones

- Seguridad: mover credenciales (USERNAME, PASSWORD) fuera del código a `config.ini`/secreto.
- Robustez: envolver refrescos con reintentos limitados; cortar limpio al fallar red prolongada.
- Señalización: `.sync_success.flag` se usa por GUI para confirmar login inicial.

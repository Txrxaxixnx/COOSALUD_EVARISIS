## Análisis del Archivo: `selenium_session_manager.py` (16/09/2025)

1) Propósito

- Iniciar sesión en `https://vco.ctamedicas.com` en modo headless, capturar la cookie `PHPSESSID`, sincronizarla en Notion incluyendo quién activó el servidor, crear la señal `.sync_success.flag` y mantener la sesión viva con refrescos periódicos.

2) Flujo principal (`capture_sync_and_refresh_session(base_path, username) -> webdriver`)

- Carga `config.ini` desde `base_path` para obtener `ApiKey` y `NOTION_SESSION_PAGE_ID`; arma los headers de la API de Notion.
- Valida que `chrome-win64/chromedriver.exe` y `chrome-win64/chrome.exe` existan en la instalación.
- Inicializa Chrome headless (`--headless=new`, `--window-size=1920,1080`, extensiones deshabilitadas) y navega al login.
- Realiza el inicio de sesión (`usuarioIngreso` + `contraseniaIngreso`), valida el mensaje “Bienvenido” y obtiene la cookie `PHPSESSID`.
- Sincronización inicial: `sincronizar_cookie_con_notion(headers, page_id, cookie_value, username, initial_sync=True)` elimina párrafos previos y publica `Session PHPSESSID: ... | LastUpdate: ... | User: <username>`.
- Escribe `.sync_success.flag` en la raíz para que la GUI detecte el éxito inicial.
- Bucle de refresco: cada `REFRESH_INTERVAL_SECONDS` hace `driver.refresh()` y vuelve a invocar `sincronizar_cookie_con_notion(..., initial_sync=False)` con el mismo `username`.
- Retorna el `webdriver` abierto; su ciclo de vida se controla externamente (`tray_app` o la GUI).

3) CLI de prueba

- `python selenium_session_manager.py --base-path=... --usuario=Operador`

4) Consideraciones

- Seguridad: mover `USERNAME`/`PASSWORD` a configuración segura (o variables de entorno).
- Robustez: envolver el bucle de refresco con reintentos controlados y cierre limpio si falla la red.
- Parámetro `username`: llega desde `tray_app` o desde la GUI (`--usuario`) y se replica tal cual en Notion para trazabilidad.

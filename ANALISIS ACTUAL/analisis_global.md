## Análisis Global y Estado del Proyecto (06/09/2025)

1) Arquitectura general

- Patrón cliente-servidor desacoplado coordinado por Notion.
  - Servidor: mantiene sesión activa en el sitio (Chrome headless), publica cookie en Notion y la refresca periódicamente.
  - Cliente: consume la cookie publicada para abrir navegador visible ya autenticado y/o automatizar flujos (glosas).
- GUI central (main_gui.py): orquesta estados, lanza roles y ejecuta flujo de Glosas integrado con Selenium como librería.

2) Mapa de módulos

- `main_gui.py`: ventana y orquestación; estado de sesión (Notion); flujo de Glosas (búsqueda, paginación, descargas, consolidación, informe ejecutivo); cierre ordenado.
- `glosas_downloader.py`: API Selenium reusable: `get_session_cookie`, `setup_driver`, `fase_buscar`, `extraer_datos_tabla_actual`, `navegar_pagina`, `cambiar_numero_entradas`, `establecer_contexto_busqueda`, `descargar_item_especifico`.
- `tray_app.py`: app de bandeja que ejecuta la lógica de servidor en un hilo y mantiene vivo el proceso hasta finalizar o salir.
- `server_logic/selenium_session_manager.py`: login headless, captura de cookie, sincronización con Notion, señal `.sync_success.flag`, bucle de refresco.
- `session_cliente.py`: abre Chrome visible e inyecta cookie para sesión manual del usuario.
- `session_cliente2.py`: variante de cliente con pasos guiados (experimental).
- `notion_control_interno.py`: registra usos diarios por usuario en Notion.
- `calendario.py`: selector de fechas con festivos y locales.

3) Flujo de datos clave

- Cookie PHPSESSID: capturada por el servidor → publicada en Notion con timestamp (LastUpdate) → consumida por cliente/automatizaciones → la GUI monitorea su vigencia por timestamp.
- Descargas de Glosas: archivos .xls/.xlsx en `~/Downloads/Glosas_Coosalud` → se organizan en carpeta “Reporte de Glosas YYYY-MM-DD” → consolidado y reporte Excel generados en esa carpeta.

4) Modos de ejecución

- GUI (seguro): `python main_gui.py --lanzado-por-evarisis [--nombre ... --cargo ... --tema ...]`
- Servidor: `python main_gui.py --run-server --base-path=...` (lanza `tray_app.main`)
- Cliente: `python main_gui.py --run-client --base-path=...` (lanza `session_cliente.run_client_logic`)
- Glosas (CLI): `python glosas_downloader.py --fase [buscar|descargar] --fecha-ini ... --fecha-fin ... [--items JSON]`

5) Requisitos y configuración

- Chrome/Chromedriver en `chrome-win64/` relativos a `base_path`.
- `config.ini` con `[Notion] ApiKey`, `NOTION_SESSION_PAGE_ID`, `PageId`.
- Librerías: `ttkbootstrap`, `selenium`, `requests`, `Pillow`, `pystray`, `pandas`, `openpyxl`, `Babel`, `holidays`, `xlrd` (para .xls).

6) Estado actual (06/09/2025)

- Glosas integrado en `main_gui.py` usando `glosas_downloader` como librería: búsqueda, paginación (entradas/Anterior/Siguiente), descargas en cadena, organización de archivos, consolidación e Informe Ejecutivo con KPIs y gráficos.
- Servidor estable: login headless, sincronización en Notion, señal `.sync_success.flag`, refresco periódico.
- Cliente estable: apertura de Chrome visible con cookie inyectada.
- Registro de uso Notion operativo.

7) Pendiente / recomendaciones

- Seguridad: mover credenciales de `selenium_session_manager.py` a `config.ini`/secreto seguro; evitar credenciales hardcodeadas.
- Resiliencia de descargas: ampliar verificación de integridad de archivos (tamaño > 0, lectura válida) y reintentos.
- Telemetría y errores: estandarizar logs y añadir métricas básicas (duración, tasas de éxito) en GUI.
- Empaquetado: validar rutas y recursos en modo PyInstaller (onefile/onedir) y documentar.

8) Anexos

- Ver documentos por módulo en esta carpeta para API detallada y notas específicas.

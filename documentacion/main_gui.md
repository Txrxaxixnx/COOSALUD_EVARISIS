### Actualización (sept 2025)

- La cabecera y el menú lateral integran los datos del operador (nombre, cargo) y una foto opcional tomada de `--foto`; se muestra en el header y en el panel de estado.
- Glosas ahora está integrado en la propia GUI: ya no se crea `glosas_results.json` ni se lanza un subproceso para buscar. Se importa `glosas_downloader` y se usa su API desde hilos para mantener la UI fluida.
- Se añadieron paginación (entradas/Anterior/Siguiente) y un botón “Iniciar Automatización” para descargar en cadena lo visible, organizar descargas, consolidar y generar informe ejecutivo.

### Análisis del Archivo: `main_gui.py`

1) Propósito

- GUI principal de EVARISIS Gestor Coosalud. Presenta dashboard y consola, verifica estado de sesión (Notion), lanza servidor/cliente y ejecuta el flujo de glosas (buscar, paginar, descargar, consolidar, informe) en el mismo proceso.

2) Componentes clave

- `get_base_path()`: Resuelve rutas tanto en script como empaquetado (PyInstaller), priorizando `_MEIPASS` y `_internal`.
- `CoosaludApp(ttk.Window)`:
  - Estado de sesión: `comprobar_estado_servidor()` consulta Notion y decide “Activa/Expirada/Inactiva”. `_actualizar_ui_estado()` habilita/deshabilita botones.
  - Identidad visual: `self.current_user` almacena nombre/cargo y `_cargar_foto_usuario()` genera versiones para cabecera (60x60) y barra lateral (48x48). Si hay imagen se muestra junto al estado del servidor.
  - Paneles: bienvenida, dashboard y configuración (con consola de logs `scrolledtext`).
  - Glosas (integrado):
    - `iniciar_proceso_glosas()` → pide rango de fechas con `CalendarioInteligente`.
    - `_tarea_buscar_glosas()` → inicializa o reutiliza `driver_glosas` via `glosas_downloader.setup_driver(...)`, inyecta cookie (`get_session_cookie`) y ejecuta `fase_buscar(...)` para obtener `resultados` y `estado_paginacion`.
    - `_actualizar_ui_resultados(...)` → dibuja `Treeview` y la barra de paginación con: entradas (20/50/100/500/Todos), Anterior/Siguiente y “Iniciar Automatización”. Usa `glosas_downloader.cambiar_numero_entradas(...)`, `navegar_pagina(...)` y `extraer_datos_tabla_actual(...)`.
    - `iniciar_proceso_automatizacion_integrada()` → solicita cantidad a procesar, descarga cada ítem con `descargar_item_especifico(...)`, reubica archivos, consolida Excel(s) y genera un informe ejecutivo profesional.
    - Organización y Excel:
      - `_organizar_archivos_reporte(...)` → crea “Reporte de Glosas YYYY-MM-DD” y mueve allí los archivos nuevos (evita colisiones con versionado).
      - `_consolidar_archivos_excel_desde_carpeta(...)` + `_guardar_consolidado_estetico(...)` → normalización y formato: encabezados, moneda, fechas, autofiltro, anchos.
      - `_crear_informe_ejecutivo(...)` → KPIs, top-10 por valor glosado (gráfico barras), serie temporal diaria (línea), detalle y hoja de “Calidad de Datos”.
  - Cierre ordenado: Termina el proceso servidor si fue lanzado y cierra `driver_glosas` si existe.

3) Despachador (CLI)

- `--run-server`: llama `tray_app.main(base_path, args.usuario)` para lanzar el servidor (ícono de bandeja + Selenium headless) y propaga el nombre del operador hacia Notion.
- `--run-client`: llama `session_cliente.run_client_logic(base_path)` para abrir Chrome visible con cookie inyectada.
- En modo GUI, `--nombre`, `--cargo`, `--foto` y `--tema` personalizan la cabecera y tema visual; `--foto` es opcional (si se omite, se muestra únicamente el nombre/cargo).
- Sin banderas: Modo GUI. Requiere `--lanzado-por-evarisis` por seguridad.

4) Dependencias

- Internas: `glosas_downloader`, `calendario.CalendarioInteligente`, `notion_control_interno`.
- Externas: Notion API (estado sesión), Selenium/Chrome, pandas/openpyxl (consolidación e informe), Pillow (imágenes), ttkbootstrap (GUI), requests.

5) Consideraciones

- Requiere `config.ini` con `ApiKey`, `NOTION_SESSION_PAGE_ID`, y `PageId` (registro de uso) bajo `[Notion]`.
- Chrome y Chromedriver deben existir en `chrome-win64/` dentro de la ruta base.
- La automatización usa hilos para no bloquear la UI; se usa `glosas_thread_lock` para serializar tareas.

### Bases de datos (sept 2025)

- Se a�adi� un panel dedicado que reutiliza el driver Selenium activo para mapear todas las facturas de un rango, pedir la cantidad a procesar y delegar en `db_manager.procesar_cuentas_en_lote`.
- Nuevas utilidades: `_tarea_buscar_para_db` (mapeo en hilo), `_preguntar_y_lanzar_procesamiento_db` (di�logo interactivo), `_preparar_ui_para_carga_db` y `_actualizar_progreso_db` (feedback en �rbol y barra), `_tarea_procesamiento_lote_db` (descarga + persistencia) y `_finalizar_carga_db`.
- El flujo genera descargas en `Documents/Glosas_Coosalud_EVARISIS`, conserva los archivos y vuelca la informaci�n normalizada a `glosas_coosalud.db`. Todos los logs se reflejan en la consola integrada.

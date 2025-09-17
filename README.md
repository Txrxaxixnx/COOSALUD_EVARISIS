# COOSALUD_EVARISIS

Resumen

- Gestor de automatización para EVARISIS/Coosalud con GUI moderna (ttkbootstrap), que orquesta dos roles: Servidor (mantiene sesión) y Cliente (usa sesión). Sincroniza la cookie de sesión PHPSESSID en Notion para compartirla entre procesos. Incluye un flujo para búsqueda, descarga y consolidación de glosas con generación de informe ejecutivo en Excel. Además, la GUI identifica en cabecera quién abrió la sesión (nombre, cargo y foto opcional) y etiqueta la cookie compartida en Notion con esa persona.

Arquitectura

- Servidor: `tray_app.py` lanza `selenium_session_manager.py` (ahora en la raíz) en Chrome headless para iniciar sesión, capturar la cookie `PHPSESSID`, publicarla en Notion con el usuario que activó el servidor y refrescar la sesión periódicamente. Señaliza éxito con `.sync_success.flag`.
- Cliente: `session_cliente.py` abre Chrome visible e inyecta la cookie leída desde Notion para entrar sin credenciales.
- GUI: `main_gui.py` muestra estado de sesión, lanza servidor/cliente y ejecuta la automatización de glosas en el mismo proceso (usa funciones de `glosas_downloader.py`), incluyendo paginación y descargas.
- Notion: almacena la cookie activa, anota quién lanzó el servidor y registra usos diarios (`notion_control_interno.py`).

Estructura de carpetas (principal)

- `main_gui.py`: Ventana principal, estado, orquestación y flujos de glosas (búsqueda, paginación, descarga, consolidado, informe).
- `glosas_downloader.py`: Funciones Selenium reutilizables para buscar, paginar y descargar glosas. También se puede invocar por CLI en fases `buscar`/`descargar`.
- `session_cliente.py`: Abre navegador con cookie inyectada desde Notion (rol Cliente).
- `tray_app.py`: Ícono de bandeja que corre la lógica de servidor, pasa el nombre del operador y mantiene activo Selenium (rol Servidor).
- `selenium_session_manager.py`: Login headless, sincronización con Notion (incluye el nombre de quien lanzó el servidor) y refresco periódico.
- `notion_control_interno.py`: Registro de uso diario por usuario en Notion.
- `calendario.py`: Selector de fecha con locales y festivos.
- `ANALISIS ACTUAL/`: Documentación técnica por archivo y análisis global.

Requisitos

- Python 3.9+ recomendado.
- Chrome portable y Chromedriver en `chrome-win64/chrome.exe` y `chrome-win64/chromedriver.exe`.
- `config.ini` en la raíz con sección Notion:
  - `[Notion]`
  - `ApiKey = <token_interno_notion>`
  - `NOTION_SESSION_PAGE_ID = <page_id_para_cookie>`
  - `PageId = <page_id_para_registro_usuarios>`

Instalación

- pip install -r requirements.txt

Ejecución

- Normalmente se lanza desde el dashboard de Evarisis. Para pruebas locales:
  - GUI (requiere bandera de seguridad):
    - `python main_gui.py --lanzado-por-evarisis --nombre="Usuario" --cargo="Cargo" --tema=litera --foto="C:/ruta/foto.jpg"`
    - Omite `--foto` si no cuentas con una imagen; la cabecera mostrará solo nombre y cargo.
  - Servidor (mantener sesión en background):
    - `python main_gui.py --run-server --base-path="%CD%" --usuario="Nombre del operador"`
  - Cliente (abrir navegador con sesión):
    - `python main_gui.py --run-client --base-path="%CD%"`

Uso: Glosas

- En la GUI, ir a Dashboard y pulsar “Buscar Informes de Glosas”.
- Seleccionar rango de fechas en el calendario inteligente.
- Se listan resultados con paginación. Controles disponibles:
  - Cambiar “entradas” (20/50/100/500/Todos), navegar Anterior/Siguiente.
  - Botón “Iniciar Automatización” para descargar en cadena N registros visibles.
- Salida de descargas: carpeta de usuario `Descargas/Glosas_Coosalud`.
- Organización automática: se crea “Reporte de Glosas YYYY-MM-DD” y se mueven allí los archivos nuevos.
- Consolidación y reportes:
  - Consolidado con todas las columnas detectadas, archivo “CONSOLIDADO_DETALLE_GLOSAS_<ini>_a_<fin>.xlsx”.
  - Informe ejecutivo con KPIs, top 10, serie diaria y detalle: “INFORME_GLOSAS_<ini>_a_<fin>.xlsx”.

Notas y seguridad

- Las credenciales de login web del servidor están en `selenium_session_manager.py`. Se recomienda moverlas a configuración segura.
- La cookie se publica en Notion; asegure el acceso a la página y al token.
- Los módulos usan rutas relativas a `--base-path` o al directorio de la app empaquetada.

Seguridad recomendada

- No versiones secretos reales. Usa `config.example.ini` como plantilla:

```
[Notion]
ApiKey = <token_integracion_notion>
PageId = <page_id_registro_usuarios>
NOTION_SESSION_PAGE_ID = <page_id_cookie_sesion>
```

- Copia la plantilla a `config.ini` localmente y rellena tus valores.

Actualizaci�n: Bases de datos (sept 2025)

- Nueva pesta�a "Bases de datos" en la GUI. Permite mapear las glosas del portal, elegir cu�ntas descargar y persistir cada factura en la base SQLite `glosas_coosalud.db`.
- `db_manager.py` inicializa la base, verifica la carpeta `Documents/Glosas_Coosalud_EVARISIS`, reestablece el contexto de b�squeda antes de cada descarga y guarda datos en las tablas `cuentas` y `glosas_detalle`.
- La consola muestra el avance y habilita acciones posteriores (bot�n "Visualizar Base de Datos" en construcci�n). Los Excel originales se conservan como respaldo en la misma carpeta.

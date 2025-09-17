## Nota de Actualización (sept 2025)

- [16/09/2025] La GUI ahora muestra nombre, cargo y foto opcional del operador en la cabecera y barra lateral; el nombre se usa para etiquetar la cookie publicada en Notion.
- [16/09/2025] `selenium_session_manager.py` se movió a la raíz del proyecto y exige que el lanzador (GUI o `tray_app`) envíe el nombre del operador; documentación y comandos fueron ajustados.
- El flujo de Glosas ha sido integrado en la GUI (`main_gui.py`), utilizando `glosas_downloader.py` como librería en el mismo proceso. Los resultados ya no se persisten en `glosas_results.json` por defecto; en su lugar, se manejan en memoria con controles de paginación y un botón de “Iniciar Automatización”.
- Se añadieron utilidades para organizar las descargas en una carpeta por fecha, consolidar todos los Excel descargados y generar un “Informe Ejecutivo” con KPIs, gráficos y verificación de calidad de datos.
- Los análisis de `main_gui.md` y `glosas_downloader.md` han sido actualizados para reflejar estos cambios. El análisis global sigue siendo válido en la arquitectura; tenga en cuenta esta actualización al leerlo.

- [17/09/2025] Se habilit� el flujo "Bases de datos": nueva pesta�a en la GUI, uso de `db_manager.py` para persistir glosas en SQLite (`glosas_coosalud.db`) y reutilizaci�n del driver Selenium existente.

# db_manager.py

## Propósito

Módulo responsable de la persistencia en SQLite (`glosas_coosalud.db`). Inicializa las tablas `cuentas` y `glosas_detalle`, descarga los Excel de glosas y los normaliza antes de guardarlos.

## Flujo principal

1. `inicializar_db(base_path)` crea el archivo y tablas si no existen.
2. `procesar_cuentas_en_lote(...)`
   - Opcionalmente recibe la ruta de descargas; si no, usa `Documents/Glosas_Coosalud_EVARISIS` y la crea.
   - Reestablece el contexto de fechas (`glosas_downloader.establecer_contexto_busqueda`) antes de cada factura.
   - Llama a `descargar_item_especifico` para obtener el Excel, detecta el archivo nuevo y lo lee con `leer_excel_glosa`.
   - Guarda encabezado en `cuentas` y detalle en `glosas_detalle` mediante `guardar_datos_en_db`.
3. Registra mensajes en la consola de la GUI mediante `log_callback` y conserva los archivos para auditoría.

## Manejo de errores

- Excepciones de Selenium/Conexión devuelven `False` al caller para que la GUI muestre "Proceso Interrumpido".
- Errores de SQLite hacen `rollback` de la factura actual y continúan con la siguiente.
- Si no aparece un archivo nuevo o el Excel no puede leerse se registra una advertencia y se omite la factura.

## Directorios

- Descargas: `~/Documents/Glosas_Coosalud_EVARISIS` (se crea automáticamente).
- Base de datos: `glosas_coosalud.db` en la raíz del proyecto.

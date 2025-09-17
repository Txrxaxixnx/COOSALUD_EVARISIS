## Análisis del Archivo: `notion_control_interno.py` (06/09/2025)

1) Propósito

- Registrar en Notion, por usuario del sistema y por día, los intentos de uso de la aplicación (p.ej., aberturas de la GUI). Mantiene un bloque marcado con `===REGISTRO DE USUARIOS===` y agrega líneas "1er/2do/3er Intento: HH:MM:SS".

2) Flujo (`registrar_uso(log_callback, base_path)`)

- Valida `config.ini` y lee `[Notion] ApiKey` y `PageId`.
- Busca/crea en la página el bloque de párrafo que inicia con la marca.
- Lee su contenido actual y lo parsea en grupos por `Usuario: <name> | <YYYY-MM-DD>`.
- Si existe grupo del usuario en la fecha actual, incrementa el ordinal; de lo contrario, crea uno nuevo.
- Publica el texto actualizado en el bloque (PATCH a Notion).
- Devuelve True/False según éxito; usa `log_callback` para informar a la GUI.

3) Consideraciones

- Resiliencia a formatos: las funciones internas parsean y rearman el texto con espacios en blanco controlados.
- Permisos: requiere que el token tenga acceso de escritura en la página.


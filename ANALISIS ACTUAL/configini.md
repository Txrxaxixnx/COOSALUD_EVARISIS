## Análisis del Archivo: `config.ini` (06/09/2025)

1) Propósito

- Centralizar credenciales y parámetros de entorno fuera del código. Evita hardcodeo y permite cambiar valores sin editar scripts.

2) Estructura esperada

```ini
[Notion]
ApiKey = <token_integracion_notion>
NOTION_SESSION_PAGE_ID = <page_id_para_cookie>
PageId = <page_id_para_registro_usuarios>
```

3) Uso por módulos

- `main_gui.py`: lee `ApiKey` y `NOTION_SESSION_PAGE_ID` para monitorear estado de sesión; usa rutas relativas al `base_path`.
- `glosas_downloader.py`: lee `ApiKey` y `NOTION_SESSION_PAGE_ID` para obtener la cookie antes de automatizar.
- `session_cliente.py`: lee la cookie desde Notion con las mismas claves.
- `server_logic/selenium_session_manager.py`: lee `ApiKey` y `NOTION_SESSION_PAGE_ID` para publicar la cookie capturada; puede usar `PageId` para otros registros.
- `notion_control_interno.py`: usa `ApiKey` y `PageId` para registrar usos diarios por usuario.

4) Recomendaciones

- Mantener `config.ini` fuera del control de versiones o encriptar secretos.
- Validar existencia del archivo y claves antes de ejecutar flujos dependientes.
- Considerar variables de entorno como fallback para `ApiKey`.


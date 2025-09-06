## Análisis del Archivo: `tray_app.py` (06/09/2025)

1) Propósito

- Crear un ícono de bandeja del sistema (pystray) para ejecutar la lógica del Servidor en un hilo, mantenerlo activo y permitir salida limpia (“Salir” cierra el driver y la app de bandeja).

2) Flujo

- `main(base_path)`: construye ícono/menú → lanza `run_selenium_logic` en hilo → `icon.run()` bloquea hasta `icon.stop()`.
- `run_selenium_logic(base_path, icon)`: llama `selenium_session_manager.capture_sync_and_refresh_session` y almacena `driver`; al terminar (o fallar) invoca `icon.stop()`.
- `on_quit(...)`: si hay `selenium_driver`, hace `quit()` y detiene el ícono.

3) Integración

- Invocado por `main_gui.py --run-server` como proceso separado. Coopera con `.sync_success.flag` creado por `selenium_session_manager` para que la GUI confirme el éxito inicial.

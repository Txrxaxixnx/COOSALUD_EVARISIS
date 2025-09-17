# tray_app.py
import pystray
from PIL import Image, ImageDraw
import threading
import sys
import argparse
import os

import selenium_session_manager

# Variable global para controlar el hilo de Selenium
selenium_thread = None
selenium_driver = None # Para tener una referencia al driver

def create_image():
    """Crea una imagen simple para el ícono de la bandeja."""
    width = 64
    height = 64
    color1 = "#005A9C" # Azul HUV
    color2 = "white"
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 2, 0, width, height // 2),
        fill=color2)
    dc.rectangle(
        (0, height // 2, width // 2, height),
        fill=color2)
    return image

def run_selenium_logic(base_path, username, icon):
    """Función que se ejecutará en un hilo para manejar Selenium."""
    global selenium_driver
    print(f"[Tray] Hilo de Selenium iniciado por el usuario: {username}.")
    try:
        selenium_driver = selenium_session_manager.capture_sync_and_refresh_session(base_path, username)
    except Exception as e:
        print(f"[Tray] El proceso de Selenium falló: {e}")
    
    # Cuando Selenium termina (sea por error o por tiempo cumplido), detenemos el ícono.
    print("[Tray] El proceso de Selenium ha terminado. Deteniendo el ícono de la bandeja.")
    icon.stop()

def on_quit(icon, item):
    """Función que se llama al hacer clic en 'Salir'."""
    global selenium_driver
    print("[Tray] Se ha solicitado salir desde el menú.")
    if selenium_driver:
        print("[Tray] Cerrando el navegador de Selenium...")
        try:
            selenium_driver.quit()
        except Exception as e:
            print(f"Error al intentar cerrar el driver: {e}")
    icon.stop()

def main(base_path, username):
    """Función principal que crea y ejecuta el ícono de la bandeja."""
    global selenium_thread
    
    image = create_image()
    menu = pystray.Menu(pystray.MenuItem('Salir', on_quit))
    icon = pystray.Icon("EVARISIS_Server", image, "Servidor de Coosalud EVARISIS (Activo)", menu)
    
    selenium_thread = threading.Thread(target=run_selenium_logic, args=(base_path, username, icon), daemon=True)
    selenium_thread.start()
    
    icon.run()
    
    print("[Tray] Aplicación de bandeja finalizada.")
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True)
    parser.add_argument("--usuario", required=True, help="Nombre del usuario que inicia el servidor.")
    args = parser.parse_args()
    main(args.base_path, args.usuario)
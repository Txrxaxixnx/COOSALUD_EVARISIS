# session_cliente2.py (VERSIÓN MODIFICADA PASO 1)

import os
import sys
import requests
import configparser
import time
from selenium import webdriver
from selenium.webdriver.common.by import By # <--- AÑADIDO
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait # <--- AÑADIDO
from selenium.webdriver.support import expected_conditions as EC # <--- AÑADIDO
from selenium.common.exceptions import TimeoutException # <--- AÑADIDO
import argparse
import tkinter as tk
from tkinter import messagebox

def run_client_logic(base_path):
    """Función con la lógica principal, ahora puede ser llamada desde otro script."""
    driver = None
    try:
        print(f"[Cliente] Usando la ruta base proporcionada: {base_path}")
        config = configparser.ConfigParser()
        config.read(os.path.join(base_path, 'config.ini'))
        api_key = config.get('Notion', 'ApiKey')
        page_id = config.get('Notion', 'NOTION_SESSION_PAGE_ID')

        print("[Cliente] Obteniendo cookie de Notion...")
        headers = {"Authorization": f"Bearer {api_key}", "Notion-Version": "2022-06-28"}
        url_notion = f"https://api.notion.com/v1/blocks/{page_id}/children"
        res = requests.get(url_notion, headers=headers, timeout=10)
        res.raise_for_status()
        
        texto_bloque = next(
            (rt['plain_text'] for block in res.json().get("results", [])
             if block.get("type") == "paragraph"
             for rt in block.get("paragraph", {}).get("rich_text", [])
             if rt.get("plain_text", "").startswith("Session PHPSESSID:")),
            None
        )
        if not texto_bloque:
            raise ValueError("No se encontró el bloque de sesión en Notion.")

        cookie_value = texto_bloque.split("|")[0].split(":")[1].strip()
        print(f"[Cliente] Cookie obtenida: ...{cookie_value[-6:]}")

        print("[Cliente] Iniciando navegador Chrome...")
        chromedriver_path = os.path.join(base_path, 'chrome-win64', 'chromedriver.exe')
        chrome_binary_path = os.path.join(base_path, 'chrome-win64', 'chrome.exe')
        
        service = Service(executable_path=chromedriver_path)
        options = webdriver.ChromeOptions()
        options.binary_location = chrome_binary_path
        # --- CAMBIO IMPORTANTE: detach=True para que el navegador no se cierre ---
        options.add_experimental_option("detach", True)
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-setuid-sandbox')
        options.add_argument('--disable-infobars')
        options.add_argument("--start-maximized") # <-- Añadido para mejor visibilidad

        driver = webdriver.Chrome(service=service, options=options)
        
        target_url = 'https://vco.ctamedicas.com'
        
        print(f"[Cliente] Navegando a {target_url}...")
        driver.get(target_url)

        print("[Cliente] Inyectando la cookie...")
        cookie_dict = {'name': 'PHPSESSID', 'value': cookie_value}
        driver.add_cookie(cookie_dict)
        
        print("[Cliente] Refrescando la página para aplicar la sesión...")
        driver.refresh()
        
        print("✅ [Cliente] ¡Sesión iniciada con éxito!")

        # ======================================================================
        # === NUEVO BLOQUE DE CÓDIGO PARA LA AUTOMATIZACIÓN GUIADA (PASO 1) ===
        # ======================================================================
        
        # Aumentamos el tiempo de espera por si la página tarda en cargar todos los scripts
        wait = WebDriverWait(driver, 20) 
        
        print("\n--- INICIO DE AUTOMATIZACIÓN GUIADA ---")
        
        try:
            # Paso 1: Esperar a que el botón del menú "Respuesta Glosas" sea visible y clicable.
            print("[Paso 1] Buscando el botón de menú 'Respuesta Glosas'...")
            
            # Usamos un selector CSS que busca un enlace `<a>` con el atributo `href` exacto.
            respuesta_glosas_selector = (By.CSS_SELECTOR, 'a[href="#respuestaGlo"]')
            
            # `wait.until(...)` esperará hasta 20 segundos a que el elemento cumpla la condición.
            # Si no lo encuentra en ese tiempo, lanzará una `TimeoutException`.
            boton_menu_glosas = wait.until(EC.element_to_be_clickable(respuesta_glosas_selector))
            
            print("[Paso 1] Botón encontrado. Haciendo clic...")
            boton_menu_glosas.click()
            
            print("✅ [Paso 1] Clic en 'Respuesta Glosas' realizado con éxito.")
            print("El submenú debería estar desplegado.")
            
        except TimeoutException:
            print("❌ ERROR: No se encontró el botón de menú 'Respuesta Glosas' después de esperar 20 segundos.")
            print("      Posibles causas: El usuario no tiene permisos para ver esa opción, o la página cambió.")
        except Exception as e:
            print(f"❌ Ocurrió un error inesperado durante el Paso 1: {e}")
            
        # El script terminará aquí, pero el navegador se quedará abierto gracias a `detach=True`
        # para que puedas inspeccionar el resultado.

    except Exception as e:
        print(f" [Cliente] Error: {e}")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error de Cliente", f"No se pudo iniciar la sesión del cliente.\n\nDetalles: {e}")
        root.destroy()
        if driver:
            driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True, help="Ruta base del proyecto.")
    args = parser.parse_args()
    run_client_logic(args.base_path)
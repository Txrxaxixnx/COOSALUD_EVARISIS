# session_cliente.py (VERSIÓN FINAL REFACTORIZADA)

import os
import sys
import requests
import configparser
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import argparse
import tkinter as tk
from tkinter import messagebox

# (La función get_base_path ya no es necesaria aquí, pero no hace daño dejarla)

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
        options.add_experimental_option("detach", True)
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-setuid-sandbox')
        options.add_argument('--disable-infobars')

        driver = webdriver.Chrome(service=service, options=options)
        
        target_url = 'https://vco.ctamedicas.com'
        
        print(f"[Cliente] Navegando a {target_url}...")
        driver.get(target_url)

        print("[Cliente] Inyectando la cookie...")
        cookie_dict = {'name': 'PHPSESSID', 'value': cookie_value}
        driver.add_cookie(cookie_dict)
        
        print("[Cliente] Refrescando la página...")
        driver.refresh()
        
        time.sleep(1)
        print("✅ [Cliente] ¡Sesión iniciada con éxito!")

    except Exception as e:
        print(f" [Cliente] Error: {e}")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error de Cliente", f"No se pudo iniciar la sesión del cliente.\n\nDetalles: {e}")
        root.destroy()
        if driver:
            driver.quit()
        # No usamos sys.exit(1) aquí porque no es el punto de entrada principal

if __name__ == "__main__":
    # Este bloque ahora solo sirve si ejecutas este script directamente para probar
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True, help="Ruta base del proyecto.")
    args = parser.parse_args()
    run_client_logic(args.base_path)
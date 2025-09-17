# selenium_session_manager.py

import os
import sys
import time
from datetime import datetime
import requests
import configparser
import argparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Credenciales y Configuración (sin cambios) ---
USERNAME = '760010379901'
PASSWORD = 'Qm6Fs1Ia2Wx8'
LOGIN_URL = 'https://vco.ctamedicas.com'
REFRESH_INTERVAL_SECONDS = 3 * 60
TOTAL_DURATION_SECONDS = 5 * 60 * 60

# --- Funciones de Ayuda para Notion ---
def borrar_session_blocks(headers, page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        count = 0
        block_ids_to_delete = []
        for block in data.get("results", []):
            if block.get("type") == "paragraph":
                rich_text = block.get("paragraph", {}).get("rich_text", [])
                if rich_text and rich_text[0].get("plain_text", "").startswith("Session PHPSESSID:"):
                    block_ids_to_delete.append(block.get("id"))
        
        for block_id in block_ids_to_delete:
            del_url = f"https://api.notion.com/v1/blocks/{block_id}"
            del_res = requests.delete(del_url, headers=headers, timeout=10)
            if del_res.ok:
                count += 1
        print(f"[Sync] Bloques antiguos borrados: {count}")
    except requests.RequestException as e:
        print(f"[Sync] ❌ Error de red al intentar borrar bloques: {e}")


def sincronizar_cookie_con_notion(headers, page_id, cookie_value, username, initial_sync=True):
    # ... (tu código para esta función está bien, no necesita cambios)
    log_prefix = "[Sync-Init]" if initial_sync else "[Sync-Update]"
    try:
        if initial_sync:
            print(f"{log_prefix} Realizando sincronización inicial con Notion para el usuario: {username}...")
        
        borrar_session_blocks(headers, page_id)
        
        timestamp_actual = datetime.now().isoformat()

        contenido_bloque = f"Session PHPSESSID: {cookie_value} | LastUpdate: {timestamp_actual} | User: {username}"
        
        nuevo_bloque_payload = { "children": [{ "object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": contenido_bloque}}]}}]}
        
        url_update = f"https://api.notion.com/v1/blocks/{page_id}/children"
        response = requests.patch(url_update, headers=headers, json=nuevo_bloque_payload, timeout=15)
        response.raise_for_status()
        
        print(f"{log_prefix} ✅ Sesión actualizada en Notion a las {datetime.now().strftime('%H:%M:%S')}")
        return True
    except Exception as e:
        print(f"{log_prefix} ❌ Error al sincronizar con Notion: {e}")
        return False


# =========================================================================
# === FUNCIÓN PRINCIPAL ===
# =========================================================================

def capture_sync_and_refresh_session(base_path, username):
    config_file_path = os.path.join(base_path, 'config.ini')
    chromedriver_path = os.path.join(base_path, 'chrome-win64', 'chromedriver.exe')
    chrome_binary_path = os.path.join(base_path, 'chrome-win64', 'chrome.exe')
    sync_success_flag_path = os.path.join(base_path, '.sync_success.flag')

    try:
        config = configparser.ConfigParser()
        if not config.read(config_file_path):
            raise FileNotFoundError(f"El archivo de configuración no se encontró en {config_file_path}")
        NOTION_API_KEY = config.get('Notion', 'ApiKey')
        NOTION_SESSION_PAGE_ID = config.get('Notion', 'NOTION_SESSION_PAGE_ID')
        NOTION_HEADERS = {"Authorization": f"Bearer {NOTION_API_KEY}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: No se pudo leer la configuración de Notion: {e}")
        raise
    
    if not os.path.exists(chromedriver_path) or not os.path.exists(chrome_binary_path):
        error_msg = f"❌ ERROR: No se encontró chromedriver.exe o chrome.exe en {os.path.join(base_path, 'chrome-win64')}."
        print(error_msg)
        raise FileNotFoundError(error_msg) # Lanzamos una excepción

    service = Service(executable_path=chromedriver_path)
    options = webdriver.ChromeOptions()
    options.binary_location = chrome_binary_path
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions") 
    
    driver = None
    try:
        print("✅ [Login] Iniciando Selenium...")
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.ID, "usuarioIngreso"))).send_keys(USERNAME)
        driver.find_element(By.ID, "contraseniaIngreso").send_keys(PASSWORD)
        driver.find_element(By.NAME, "validarSesion").click()
        wait.until(EC.visibility_of_element_located((By.XPATH, "//div[@class='card-header-title' and text()='Bienvenido']")))
        print("✅ [Login] ¡Inicio de sesión verificado!")
        session_cookie = next((c for c in driver.get_cookies() if c['name'] == 'PHPSESSID'), None)
        if not session_cookie:
            raise RuntimeError("❌ No se pudo encontrar la cookie PHPSESSID.")
        cookie_value = session_cookie['value']
        print(f"🍪 [Login] Cookie de sesión capturada: ...{cookie_value[-6:]}")
        
        # --- Sincronización INICIAL ---
        sincronizacion_exitosa = sincronizar_cookie_con_notion(NOTION_HEADERS, NOTION_SESSION_PAGE_ID, cookie_value, username, initial_sync=True)
        if not sincronizacion_exitosa:
            raise RuntimeError("Fallo crítico: No se pudo sincronizar la sesión inicial con Notion. Abortando.")

        # --- Crear el archivo de señal ---
        with open(sync_success_flag_path, 'w') as f:
            pass
        print("[Signal] Señal de éxito '.sync_success.flag' creada.")

        # --- Minimizar la ventana ---
        print("[Selenium] Minimizando la ventana del navegador del servidor...")

        
        # --- FASE DE REFRESCO ---
        print("\n" + "="*50)
        print("🔄 [Refresh] Iniciando modo de refresco y actualización...")
        print("="*50 + "\n")
        end_time = time.time() + TOTAL_DURATION_SECONDS
        while time.time() < end_time:
            print(f"Próxima actualización en {REFRESH_INTERVAL_SECONDS / 60:.0f} minutos...")
            time.sleep(REFRESH_INTERVAL_SECONDS)
            try:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Refrescando página en Selenium...")
                driver.refresh()
                sincronizar_cookie_con_notion(NOTION_HEADERS, NOTION_SESSION_PAGE_ID, cookie_value, username, initial_sync=False)
            except Exception as loop_error:
                print(f"ℹ️ [Refresh] Error durante el ciclo de refresco: {loop_error}")
                break # Salimos del bucle si el navegador se cierra o hay un error
        else:
            print("✅ [Refresh] Tiempo de refresco completado.")

    except Exception as e:
        print(f"\n❌ Ocurrió un error crítico durante la ejecución de Selenium: {e}")
        if driver:
            driver.quit()
        raise  
    print("[Selenium Manager] El bucle de refresco ha terminado. El driver sigue activo.")
    return driver

if __name__ == "__main__":
    print("--- MODO DE PRUEBA DIRECTA DE SELENIUM_SESSION_MANAGER ---")
    parser = argparse.ArgumentParser(description="Gestor de sesión de Selenium para Coosalud.")
    parser.add_argument("--base-path", required=True, help="Ruta base del proyecto.")
    parser.add_argument("--usuario", required=True, help="Nombre del usuario que inicia el servidor.")
    args = parser.parse_args()
    
    active_driver = None
    try:
        active_driver = capture_sync_and_refresh_session(args.base_path, args.usuario)
        print("\n--- PRUEBA FINALIZADA ---")
    except Exception as e:
        print(f"\n--- PRUEBA FALLIDA: {e} ---")
    finally:
        if active_driver:
            print("Cerrando el driver en el bloque finally de la prueba.")
            active_driver.quit()
    sys.exit(0)
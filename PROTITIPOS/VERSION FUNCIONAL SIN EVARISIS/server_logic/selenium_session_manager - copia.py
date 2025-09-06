# selenium_session_manager.py
# Versión Mejorada: Realiza login, sincroniza, y mantiene la sesión y el timestamp de Notion actualizados.

import json
import os
import sys
import time
from datetime import datetime
import requests
import configparser

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Configuración (sin cambios) ---
USERNAME = '760010379901'
PASSWORD = 'Qm6Fs1Ia2Wx8'
LOGIN_URL = 'https://vco.ctamedicas.com'
REFRESH_INTERVAL_SECONDS = 3 * 60
TOTAL_DURATION_SECONDS = 5 * 60 * 60

# --- Rutas (sin cambios) ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, 'config.ini')
CHROMEDRIVER_PATH = os.path.join(PROJECT_ROOT, 'chrome-win64', 'chromedriver.exe')
CHROME_BINARY_PATH = os.path.join(PROJECT_ROOT, 'chrome-win64', 'chrome.exe')
SYNC_SUCCESS_FLAG_PATH = os.path.join(PROJECT_ROOT, '.sync_success.flag')
def get_base_path():
    """
    Obtiene la ruta base correcta para los archivos de datos.
    Funciona en modo script y en modo compilado con PyInstaller (onedir),
    teniendo en cuenta la carpeta '_internal'.
    """
    if getattr(sys, 'frozen', False):
        # Si la aplicación está 'congelada' (compilada)
        # La ruta base para los datos es la carpeta '_internal' junto al ejecutable.
        base_dir = os.path.dirname(sys.executable)
        return os.path.join(base_dir, '_internal')
    else:
        # Si se ejecuta como un script de Python normal
        return os.path.dirname(os.path.abspath(__file__))
# =========================================================================
# === FUNCIONES DE AYUDA PARA LA SINCRONIZACIÓN CON NOTION (MODIFICADAS) ===
# =========================================================================

def borrar_session_blocks(headers, page_id):
    """(Sin cambios) Elimina bloques de sesión antiguos."""
    # ... (tu código de esta función es perfecto, lo dejamos igual)
    # ...
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

# La función sincronizar_cookie_con_notion ya no necesita devolver el ID.
def sincronizar_cookie_con_notion(headers, page_id, cookie_value, initial_sync=True):
    """
    Sincroniza la cookie con Notion borrando y creando el bloque.
    El parámetro 'initial_sync' es solo para cambiar los mensajes de log.
    """
    log_prefix = "[Sync-Init]" if initial_sync else "[Sync-Update]"
    try:
        if initial_sync:
            print(f"{log_prefix} Realizando sincronización inicial con Notion...")
        
        borrar_session_blocks(headers, page_id)
        
        timestamp_actual = datetime.now().isoformat()
        contenido_bloque = f"Session PHPSESSID: {cookie_value} | LastUpdate: {timestamp_actual}"
        
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
# === FUNCIÓN PRINCIPAL (MODIFICADA) ===
# =========================================================================

def capture_sync_and_refresh_session():
    # --- Carga de Configuración (sin cambios) ---
    try:
        config = configparser.ConfigParser()
        if not config.read(CONFIG_FILE_PATH):
            raise FileNotFoundError(f"El archivo de configuración no se encontró en {CONFIG_FILE_PATH}")
        NOTION_API_KEY = config.get('Notion', 'ApiKey')
        NOTION_SESSION_PAGE_ID = config.get('Notion', 'NOTION_SESSION_PAGE_ID')
        NOTION_HEADERS = {"Authorization": f"Bearer {NOTION_API_KEY}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: No se pudo leer la configuración de Notion: {e}")
        return 1
    
    # --- Configuración de Selenium (sin cambios) ---
    if not os.path.exists(CHROMEDRIVER_PATH) or not os.path.exists(CHROME_BINARY_PATH):
        print(f"❌ ERROR: No se encontró chromedriver.exe o chrome.exe.")
        return 1
    service = Service(executable_path=CHROMEDRIVER_PATH)
    options = webdriver.ChromeOptions()
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument('--start-maximized')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    
    driver = None
    try:
        # --- Fase de Login (sin cambios) ---
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
        
        # --- PASO 2: Sincronización INICIAL ---
        sincronizacion_exitosa = sincronizar_cookie_con_notion(NOTION_HEADERS, NOTION_SESSION_PAGE_ID, cookie_value, initial_sync=True)
        if not sincronizacion_exitosa:
            raise RuntimeError("Fallo crítico: No se pudo sincronizar la sesión inicial con Notion. Abortando.")

        # --- MODIFICACIÓN CLAVE 1: Crear el archivo de señal ---
        # Creamos un archivo vacío para notificar a la GUI que la sincronización fue exitosa.
        with open(SYNC_SUCCESS_FLAG_PATH, 'w') as f:
            pass
        print("[Signal] Señal de éxito '.sync_success.flag' creada.")

        # --- MODIFICACIÓN CLAVE 2: Minimizar la ventana del navegador ---
        print("[Selenium] Minimizando la ventana del navegador del servidor...")
        driver.minimize_window()
        
        # --- PASO 3: FASE DE REFRESCO (MODIFICADA) ---
        print("\n" + "="*50)
        print("🔄 [Refresh] Iniciando modo de refresco y actualización...")
        print("="*50 + "\n")
        end_time = time.time() + TOTAL_DURATION_SECONDS
        while time.time() < end_time:
            # Primero dormimos, luego actuamos.
            print(f"Próxima actualización en {REFRESH_INTERVAL_SECONDS / 60:.0f} minutos...")
            time.sleep(REFRESH_INTERVAL_SECONDS)
            
            try:
                # 1. Refrescar la página en Selenium para mantener la sesión web viva.
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Refrescando página en Selenium...")
                driver.refresh()
                
                # 2. Re-sincronizar completamente en Notion.
                sincronizar_cookie_con_notion(NOTION_HEADERS, NOTION_SESSION_PAGE_ID, cookie_value, initial_sync=False)

            except Exception as loop_error:
                # Si el navegador se cierra o hay un error de red, lo capturamos aquí.
                print(f"ℹ️ [Refresh] Error durante el ciclo de refresco: {loop_error}")
                break
        else:
            print("✅ [Refresh] Tiempo de refresco completado.")

    except Exception as e:
        print(f"\n❌ Ocurrió un error crítico: {e}")
        return 1
    finally:
        if driver:
            print("🔚 Cerrando navegador.")
            driver.quit()
    return 0

if __name__ == "__main__":
    exit_code = capture_sync_and_refresh_session()
    sys.exit(exit_code)
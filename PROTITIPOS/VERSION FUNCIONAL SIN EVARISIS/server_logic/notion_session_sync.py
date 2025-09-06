# notion_session_sync.py (Versión Refactorizada)
# Lee la configuración desde config.ini para ser un componente modular.

import os
import json
import requests
import sys
import configparser
from datetime import datetime

# Configurar salida UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# --- Gestión de Rutas ---
# BASE_DIR es la carpeta actual (.../server_logic)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# PROJECT_ROOT es la carpeta padre, donde está config.ini
PROJECT_ROOT = os.path.dirname(BASE_DIR)
SESSION_FILE_PATH = os.path.join(BASE_DIR, "session.json")
CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, "config.ini")

def borrar_session_blocks(headers, page_id):
    """Elimina bloques de sesión antiguos de una página de Notion."""
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        count = 0
        for block in data.get("results", []):
            if block.get("type") == "paragraph":
                rich_text = block.get("paragraph", {}).get("rich_text", [])
                if rich_text and rich_text[0].get("plain_text", "").startswith("Session PHPSESSID:"):
                    block_id = block.get("id")
                    del_url = f"https://api.notion.com/v1/blocks/{block_id}"
                    del_res = requests.delete(del_url, headers=headers, timeout=10)
                    if del_res.ok:
                        count += 1
                    else:
                        print(f"❌ Error al borrar bloque {block_id}: {del_res.text}")
        print(f"Bloques antiguos borrados: {count}")
    except requests.RequestException as e:
        print(f"❌ Error de red al intentar borrar bloques: {e}")

def actualizar_session_en_notion(headers, page_id):
    """Lee session.json y actualiza el bloque en Notion."""
    if not os.path.exists(SESSION_FILE_PATH):
        print(f"❌ Error: No se encontró el archivo de sesión en {SESSION_FILE_PATH}")
        return 1 # Devuelve código de error

    try:
        with open(SESSION_FILE_PATH, "r", encoding="utf-8") as f:
            session_data = json.load(f)
        if not session_data or not isinstance(session_data, list) or not session_data[0].get("value"):
            print("❌ Error: El archivo de sesión no contiene datos válidos.")
            return 1
        
        cookie_value = session_data[0].get("value")
        print(f"Cookie obtenida: ...{cookie_value[-6:]}")
        
        # Primero, borrar los bloques antiguos
        borrar_session_blocks(headers, page_id)
        
        # Construir el nuevo bloque con timestamp
        timestamp_actual = datetime.now().isoformat()
        contenido_bloque = f"Session PHPSESSID: {cookie_value} | LastUpdate: {timestamp_actual}"
        print(f"Contenido a sincronizar: {contenido_bloque}")

        nuevo_bloque = {
            "children": [{
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": contenido_bloque}}]}
            }]
        }
        
        url_update = f"https://api.notion.com/v1/blocks/{page_id}/children"
        response = requests.patch(url_update, headers=headers, json=nuevo_bloque)
        response.raise_for_status() # Lanza un error si la petición falla
        
        print("✅ La sesión se ha actualizado correctamente en Notion.")
        return 0 # Devuelve código de éxito

    except (FileNotFoundError, json.JSONDecodeError, IndexError) as e:
        print(f"❌ Error leyendo o procesando session.json: {e}")
        return 1
    except requests.RequestException as e:
        print(f"❌ Error de red al actualizar la sesión en Notion: {e}")
        return 1

def main():
    """Función principal que carga la configuración y orquesta el proceso."""
    print("Iniciando sincronización de sesión en Notion...")

    try:
        config = configparser.ConfigParser()
        if not config.read(CONFIG_FILE_PATH):
            raise FileNotFoundError(f"El archivo de configuración no se encontró en {CONFIG_FILE_PATH}")
            
        api_key = config.get('Notion', 'ApiKey')
        page_id = config.get('Notion', 'NOTION_SESSION_PAGE_ID')

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        return actualizar_session_en_notion(headers, page_id)

    except (configparser.Error, KeyError, FileNotFoundError) as e:
        print(f"❌ Error crítico de configuración: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    if exit_code == 0:
        print("✅ Proceso de sincronización finalizado con éxito.")
    else:
        print("❌ Proceso de sincronización finalizado con errores.")
    sys.exit(exit_code)
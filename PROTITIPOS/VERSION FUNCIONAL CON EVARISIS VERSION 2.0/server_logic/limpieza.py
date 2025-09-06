# limpieza.py (Versión Refactorizada)
# Lee la configuración desde config.ini para limpiar los registros de uso.

import os
import requests
import sys
import configparser

# --- Constantes del Script ---
MARCA_BLOQUE = "===REGISTRO DE USUARIOS==="

# --- Gestión de Rutas ---
# BASE_DIR es la carpeta actual (.../server_logic)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# PROJECT_ROOT es la carpeta padre, donde está config.ini
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, "config.ini")

def log(msg, tipo="INFO"):
    """Función de logging con emojis para la consola."""
    emojis = {
        "INFO": "ℹ️",
        "OK": "✅",
        "ERROR": "❌",
        "WARN": "⚠️",
        "DELETE": "🧹"
    }
    print(f"{emojis.get(tipo, '')} {msg}")

def extraer_texto_parrafo(block):
    """Extrae el texto plano de un bloque de párrafo de Notion."""
    rt = block.get("paragraph", {}).get("rich_text", [])
    return "".join(r.get("plain_text", "") for r in rt if r.get("type") == "text")

def borrar_bloque_registro(headers, page_id):
    """Busca y elimina el bloque de registros en la página de Notion especificada."""
    url_children = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
    try:
        resp = requests.get(url_children, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        log(f"Error al obtener hijos de la página: {e}", "ERROR")
        return 1 # Devuelve código de error

    data = resp.json()
    bloques = data.get("results", [])
    if not bloques:
        log("No se encontraron bloques hijos en la página.", "WARN")

    for block in bloques:
        if block.get("type") == "paragraph":
            texto = extraer_texto_parrafo(block)
            if texto.startswith(MARCA_BLOQUE):
                block_id = block.get("id")
                del_url = f"https://api.notion.com/v1/blocks/{block_id}"
                try:
                    del_res = requests.delete(del_url, headers=headers, timeout=10)
                    del_res.raise_for_status()
                    log(f"Bloque de registros eliminado exitosamente (ID: {block_id})", "DELETE")
                    return 0 # Éxito
                except requests.RequestException as e:
                    log(f"Error al eliminar el bloque: {e}", "ERROR")
                    return 1 # Error
    
    log("No se encontró ningún bloque que contenga la marca de registro.", "INFO")
    return 0 # Éxito (no había nada que borrar)

def main():
    """Carga la configuración y ejecuta el proceso de limpieza."""
    log("Iniciando limpieza de registros de intentos en Notion...")
    
    try:
        config = configparser.ConfigParser()
        if not config.read(CONFIG_FILE_PATH):
            raise FileNotFoundError(f"El archivo de configuración no se encontró en {CONFIG_FILE_PATH}")
            
        api_key = config.get('Notion', 'ApiKey')
        # Leemos el PageId para el registro de usuarios
        page_id_usuarios = config.get('Notion', 'PageId')

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        return borrar_bloque_registro(headers, page_id_usuarios)

    except (configparser.Error, KeyError, FileNotFoundError) as e:
        log(f"Error crítico de configuración: {e}", "ERROR")
        return 1

if __name__ == "__main__":
    exit_code = main()
    if exit_code == 0:
        log("Proceso de limpieza completado.")
    else:
        log("Proceso de limpieza finalizado con errores.")
    sys.exit(exit_code)
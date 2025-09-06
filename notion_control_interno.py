# notion_control_interno.py
import os
import requests
import configparser
from datetime import datetime
import sys # Necesario para obtener la ruta base en modo .exe


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
# --- Funciones de Ayuda (ahora privadas con un '_') ---

def _obtener_usuario_sistema():
    try:
        return os.getlogin()
    except:
        return os.environ.get("USERNAME", "Desconocido")

def _get_ordinal_label(n):
    # (Esta función no cambia)
    if n == 1: return "1er"
    elif n == 2: return "2do"
    elif n == 3: return "3er"
    else: return f"{n}to"

def _extraer_texto_parrafo(block):
    rt = block.get("paragraph", {}).get("rich_text", [])
    return "".join(r.get("plain_text", "") for r in rt if r.get("type") == "text")

def _buscar_o_crear_bloque_registros(log_callback, headers, page_id, marca):
    url_children = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
    resp = requests.get(url_children, headers=headers)
    if not resp.ok:
        log_callback(f"❌ Error al obtener hijos de la página: {resp.text}")
        raise ConnectionError("No se pudo conectar a la página de Notion.")

    data = resp.json()
    for block in data.get("results", []):
        if block.get("type") == "paragraph":
            txt = _extraer_texto_parrafo(block)
            if txt.startswith(marca):
                log_callback("Bloque de registros encontrado.")
                return block["id"]

    log_callback("Bloque de registros no encontrado. Creando uno nuevo...")
    url_create = f"https://api.notion.com/v1/blocks/{page_id}/children"
    contenido_inicial = f"{marca}\n\nAquí se almacenan los registros de inicio de sesión...\n\n\n"
    payload = {"children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": contenido_inicial}}]}}]}
    
    create_resp = requests.patch(url_create, headers=headers, json=payload)
    if not create_resp.ok:
        log_callback(f"❌ Error al crear el bloque de registros: {create_resp.text}")
        raise ConnectionError("No se pudo crear el bloque de registros en Notion.")
    
    new_blocks = create_resp.json().get("results", [])
    if not new_blocks:
        log_callback("❌ Bloque creado, pero no se devolvió en la respuesta de Notion.")
        raise ValueError("Error en la respuesta de la API de Notion al crear bloque.")
        
    log_callback("Nuevo bloque de registros creado con éxito.")
    return new_blocks[0]["id"]

def _obtener_texto_de_bloque(log_callback, headers, block_id):
    url_block = f"https://api.notion.com/v1/blocks/{block_id}"
    resp = requests.get(url_block, headers=headers)
    if not resp.ok:
        log_callback(f"❌ Error al obtener el contenido del bloque: {resp.text}")
        return ""
    return _extraer_texto_parrafo(resp.json())

def _patch_texto_en_bloque(headers, block_id, texto):
    url_block = f"https://api.notion.com/v1/blocks/{block_id}"
    payload = {"paragraph": {"rich_text": [{"type": "text", "text": {"content": texto}}]}}
    return requests.patch(url_block, headers=headers, json=payload)

def _parsear_grupos_por_usuario(texto, marca):
    # (Lógica de parseo no cambia, es interna y no necesita logging)
    lineas = texto.split("\n")
    idx_inicio = 0
    if lineas and lineas[0].startswith(marca):
        idx_inicio = 1
        while idx_inicio < len(lineas) and not lineas[idx_inicio].strip():
            idx_inicio += 1
    
    lineas_contenido = lineas[idx_inicio:]
    grupos, tmp = [], []
    for ln in lineas_contenido:
        if ln.startswith("Usuario: "):
            if tmp:
                while tmp and not tmp[-1].strip(): tmp.pop()
                grupos.append(tmp)
            tmp = [ln]
        else:
            tmp.append(ln)
    if tmp:
        while tmp and not tmp[-1].strip(): tmp.pop()
        if tmp: grupos.append(tmp)
    return grupos

def _rearmar_texto(marca, grupos):
    bloques = ["\n".join(g) for g in grupos]
    cuerpo = "\n\n\n".join(bloques)
    return f"{marca}\n\n{cuerpo}\n" if cuerpo.strip() else f"{marca}\n\n"

def _encontrar_grupo_por_usuario_fecha(grupos, usuario, fecha):
    patron = f"Usuario: {usuario} — {fecha}"
    for i, grp in enumerate(grupos):
        if grp and grp[0].strip() == patron:
            return i, grp
    return None, None

def _contar_intentos_en_grupo(grupo):
    return sum(1 for ln in grupo[1:] if "Intento:" in ln)

# =========================================================================
# === FUNCIÓN PRINCIPAL PÚBLICA (Llamada por la GUI) ===
# =========================================================================

def registrar_uso(log_callback, base_path):
    """
    Realiza todo el proceso de registro en Notion.
    Acepta una función 'log_callback' para enviar mensajes a la GUI.
    Devuelve True si tiene éxito, False si falla.
    """
    try:
          
        config_path = os.path.join(base_path, 'config.ini')
        if not os.path.exists(config_path):
            log_callback(f"❌ Error Crítico: No se encontró el archivo 'config.ini' en la ruta: {config_path}")
            return False

        config = configparser.ConfigParser()
        config.read(config_path)
        
        NOTION_API_KEY = config['Notion']['ApiKey']
        PAGE_ID_USUARIOS = config['Notion']['PageId']
        MARCA_BLOQUE = "===REGISTRO DE USUARIOS==="

        HEADERS = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

        # --- Lógica de Registro ---
        usuario = _obtener_usuario_sistema()
        log_callback(f"Usuario del sistema detectado: {usuario}")
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        hora_actual = datetime.now().strftime("%H:%M:%S")

        block_id_reg = _buscar_o_crear_bloque_registros(log_callback, HEADERS, PAGE_ID_USUARIOS, MARCA_BLOQUE)
        
        texto_original = _obtener_texto_de_bloque(log_callback, HEADERS, block_id_reg)
        grupos = _parsear_grupos_por_usuario(texto_original, MARCA_BLOQUE)
        
        idx, grupo = _encontrar_grupo_por_usuario_fecha(grupos, usuario, fecha_hoy)
        if grupo:
            n_intentos = _contar_intentos_en_grupo(grupo) + 1
            label = _get_ordinal_label(n_intentos)
            grupo.append(f"{label} Intento: {hora_actual}")
            grupos[idx] = grupo
            log_callback(f"Registrando {label} intento para el día de hoy.")
        else:
            nuevo_grupo = [f"Usuario: {usuario} — {fecha_hoy}", f"1er Intento: {hora_actual}"]
            grupos.append(nuevo_grupo)
            log_callback("Registrando primer uso del día.")

        texto_final = _rearmar_texto(MARCA_BLOQUE, grupos)
        resp = _patch_texto_en_bloque(HEADERS, block_id_reg, texto_final)

        if resp.ok:
            log_callback("✅ Registro en Notion completado con éxito.")
            return True
        else:
            log_callback(f"❌ Fallo al actualizar Notion: {resp.text}")
            return False

    except Exception as e:
        log_callback(f"❌ Ocurrió un error inesperado en el control interno: {e}")
        return False
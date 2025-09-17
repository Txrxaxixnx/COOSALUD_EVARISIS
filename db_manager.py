# db_manager.py (Versión con reconexión de contexto y sin borrado de archivos)

import os
import sqlite3
import pandas as pd
import re
from selenium.common.exceptions import WebDriverException

# <<<----------- IMPORTAMOS LAS FUNCIONES CLAVE AQUÍ -----------<<<
from glosas_downloader import establecer_contexto_busqueda, descargar_item_especifico

DB_FILENAME = "glosas_coosalud.db"

def inicializar_db(base_path):
    """Crea el archivo de la base de datos y las tablas si no existen."""
    db_path = os.path.join(base_path, DB_FILENAME)
    print(f"[DB Manager] Asegurando que la base de datos exista en: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cuentas (
        id_cuenta TEXT PRIMARY KEY, radicacion TEXT, fecha_rad TEXT,
        factura TEXT UNIQUE, valor_factura TEXT, valor_glosado TEXT
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS glosas_detalle (
        id_glosa INTEGER PRIMARY KEY, factura TEXT, id_item INTEGER,
        descripcion_item TEXT, tipo TEXT, descripcion TEXT, justificacion TEXT,
        valor_glosado_item REAL, usuario TEXT, fecha_glosa TEXT, estado TEXT,
        FOREIGN KEY (factura) REFERENCES cuentas (factura)
    )''')
    conn.commit()
    conn.close()
    print("✅ [DB Manager] Base de datos y tablas listas.")
    return db_path

def guardar_datos_en_db(db_path, cuenta_info, df_glosas_detalle):
    """Guarda la información de una cuenta y el detalle de sus glosas en la BD."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT OR REPLACE INTO cuentas (id_cuenta, radicacion, fecha_rad, factura, valor_factura, valor_glosado)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            cuenta_info['id'], cuenta_info['radicacion'], cuenta_info['fecha_rad'],
            cuenta_info['factura'], cuenta_info['valor_factura'], cuenta_info['valor_glosado']
        ))
        if df_glosas_detalle is not None and not df_glosas_detalle.empty:
            for _, row in df_glosas_detalle.iterrows():
                cursor.execute('''
                INSERT OR REPLACE INTO glosas_detalle (id_glosa, factura, id_item, descripcion_item, tipo, descripcion, justificacion, valor_glosado_item, usuario, fecha_glosa, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['Id Glosa'], cuenta_info['factura'], row['Id Item'],
                    row['Descripcion Item'], row['Tipo'], row['Descripcion'],
                    row['Justificacion'], row['Valor Glosado'], row['Usuario'],
                    row['Fecha'], row['Estado']
                ))
        conn.commit()
        print(f"  -> Datos de factura {cuenta_info['factura']} guardados en la BD.")
    except sqlite3.Error as e:
        print(f"❌ [DB Manager] Error de SQLite al guardar factura {cuenta_info['factura']}: {e}")
        conn.rollback()
    finally:
        conn.close()

def leer_excel_glosa(ruta_archivo):
    """Lee un archivo Excel de glosa, omitiendo la primera fila de título."""
    try:
        factura_match = re.search(r'(\d+)\.xlsx?$', os.path.basename(ruta_archivo))
        factura_num = factura_match.group(1) if factura_match else None
        df = pd.read_excel(ruta_archivo, skiprows=1)
        df.columns = df.columns.str.strip()
        df['Valor Glosado'] = pd.to_numeric(df['Valor Glosado'], errors='coerce').fillna(0)
        print(f"  -> Lectura de Excel para factura {factura_num} exitosa. {len(df)} filas encontradas.")
        return df
    except Exception as e:
        print(f"⚠️  [DB Manager] No se pudo leer el archivo Excel '{os.path.basename(ruta_archivo)}': {e}")
        return None

# <<<----------- FUNCIÓN PRINCIPAL MODIFICADA PARA SER MÁS ROBUSTA -----------<<<
def procesar_cuentas_en_lote(driver, cuentas, base_path, log_callback, fecha_ini, fecha_fin, download_dir=None):
    """
    Orquesta el proceso de descarga y guardado, re-estableciendo el contexto de búsqueda
    para cada ítem para evitar errores de estado en la página web.
    """
    try:
        db_path = inicializar_db(base_path)
        if download_dir is None:
            download_dir = os.path.join(os.path.expanduser("~"), "Documents", "Glosas_Coosalud_EVARISIS")
        else:
            download_dir = os.path.abspath(download_dir)
        os.makedirs(download_dir, exist_ok=True)
        log_callback(f"[BD] Carpeta de descargas en uso: {download_dir}")
        
        total_cuentas = len(cuentas)
        last_processed_id = None

        for i, cuenta in enumerate(cuentas):
            log_callback(f"Procesando {i+1}/{total_cuentas}: Factura {cuenta['factura']}...")
            
            # <<<--- LÓGICA CLAVE AÑADIDA ---<<<
            # Antes de cada descarga, nos aseguramos de que la página tenga el filtro correcto.
            # Esto soluciona el problema de que la página "olvide" las fechas.
            log_callback("  -> Re-estableciendo contexto de búsqueda para asegurar consistencia...")
            establecer_contexto_busqueda(driver, fecha_ini, fecha_fin)
            log_callback("  -> Contexto re-establecido. Procediendo con la descarga.")
            
            item_para_descargar = {
                "id": cuenta['id'], "factura": cuenta['factura'],
                "detalle": False, "glosa": True
            }
            
            files_antes = set(os.listdir(download_dir))
            processed_id = descargar_item_especifico(driver, item_para_descargar, download_dir, last_processed_id)
            last_processed_id = processed_id

            if not processed_id:
                log_callback(f"⚠️  No se pudo procesar la descarga para la factura {cuenta['factura']}. Saltando.")
                continue

            files_despues = set(os.listdir(download_dir))
            nuevos_archivos = files_despues - files_antes
            
            if not nuevos_archivos:
                log_callback(f"⚠️  No se encontró un nuevo archivo descargado para la factura {cuenta['factura']}.")
                continue
            
            nombre_archivo_nuevo = nuevos_archivos.pop()
            ruta_completa_excel = os.path.join(download_dir, nombre_archivo_nuevo)
            df_detalle_glosa = leer_excel_glosa(ruta_completa_excel)
            guardar_datos_en_db(db_path, cuenta, df_detalle_glosa)
            
            # Los archivos ya no se borran para auditoría.

        log_callback(f"✅ ¡Proceso completado! Se han procesado {total_cuentas} facturas.")
        return True

    except (WebDriverException, ConnectionError) as e:
        log_callback(f"❌ Error de Navegador o Conexión: El proceso se ha detenido. {e}")
        return False
    except Exception as e:
        log_callback(f"❌ Error inesperado en el procesamiento por lotes: {e}")
        import traceback
        traceback.print_exc()
        return False




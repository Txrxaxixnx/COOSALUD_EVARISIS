# glosas_downloader.py

import os
import sys
import json
import time
import argparse
import configparser
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import Select

def get_session_cookie(base_path):
    """Obtiene la cookie de sesión desde Notion."""
    config = configparser.ConfigParser()
    config.read(os.path.join(base_path, 'config.ini'))
    api_key = config.get('Notion', 'ApiKey')
    page_id = config.get('Notion', 'NOTION_SESSION_PAGE_ID')
    
    import requests
    headers = {"Authorization": f"Bearer {api_key}", "Notion-Version": "2022-06-28"}
    url_notion = f"https://api.notion.com/v1/blocks/{page_id}/children"
    res = requests.get(url_notion, headers=headers, timeout=15)
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

    return texto_bloque.split("|")[0].split(":")[1].strip()

def setup_driver(base_path, for_download=False):
    """Configura y devuelve una instancia del driver de Selenium y la ruta de descargas."""
    chromedriver_path = os.path.join(base_path, 'chrome-win64', 'chromedriver.exe')
    chrome_binary_path = os.path.join(base_path, 'chrome-win64', 'chrome.exe')
    
    service = Service(executable_path=chromedriver_path)
    options = webdriver.ChromeOptions()
    options.binary_location = chrome_binary_path
    
    download_dir = None
    if for_download:
        # Definimos la ruta de descargas
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "Glosas_Coosalud")
        os.makedirs(download_dir, exist_ok=True)
        print(f"[Downloader] Los archivos se guardarán en: {download_dir}")
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

    # Devolvemos el driver Y la ruta de descargas (o None si no es para descargar)
    return webdriver.Chrome(service=service, options=options), download_dir

## MODIFICADO: Esta es la única función que necesitas cambiar.
def wait_for_new_file_to_download(download_dir, timeout=60):
    """
    Espera a que un NUEVO archivo aparezca y termine de descargarse.
    Ahora maneja tanto descargas lentas (con .crdownload) como rápidas.
    """
    files_before = set(os.listdir(download_dir))
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        files_after = set(os.listdir(download_dir))
        new_files = files_after - files_before
        
        if new_files:
            # Encontramos al menos un archivo nuevo. Tomamos el primero.
            new_file_name = new_files.pop()
            
            ## --- INICIO DE LA NUEVA LÓGICA INTELIGENTE --- ##
            
            # CASO A: Es un archivo de descarga temporal (descarga lenta/grande)
            if new_file_name.endswith('.crdownload'):
                temp_file_path = os.path.join(download_dir, new_file_name)
                print(f"Descarga lenta detectada: {new_file_name}. Esperando a que finalice...")
                
                # Esperamos a que el archivo temporal desaparezca (se renombre)
                while time.time() - start_time < timeout:
                    if not os.path.exists(temp_file_path):
                        print("✅ Descarga completada (el archivo temporal desapareció).")
                        return True
                    time.sleep(0.5)
                
                print("¡ADVERTENCIA! El archivo temporal no desapareció en el tiempo esperado.")
                return False

            # CASO B: Es un archivo final (descarga muy rápida)
            else:
                print(f"Descarga rápida detectada: {new_file_name}. ¡Considerada completa!")
                return True # Si no es .crdownload, es el archivo final. ¡Éxito!
                
            ## --- FIN DE LA NUEVA LÓGICA INTELIGENTE --- ##

        time.sleep(0.5) # Esperamos medio segundo antes de volver a comprobar

    print("¡ADVERTENCIA! La descarga no pareció iniciarse en el tiempo esperado.")
    return False
def obtener_estado_paginacion(driver):
    """
    Extrae el estado actual de la paginación de la tabla de DataTables.
    Devuelve un diccionario con la información.
    """
    try:
        wait = WebDriverWait(driver, 10)
        
        # Esperar a que el contenedor principal esté presente
        wait.until(EC.presence_of_element_located((By.ID, "tablaRespuestaGlosa_wrapper")))

        info_texto = driver.find_element(By.ID, "tablaRespuestaGlosa_info").text
        
        # Comprobar si los botones están deshabilitados (tienen la clase 'disabled')
        prev_button = driver.find_element(By.ID, "tablaRespuestaGlosa_previous")
        anterior_deshabilitado = "disabled" in prev_button.get_attribute("class")
        
        next_button = driver.find_element(By.ID, "tablaRespuestaGlosa_next")
        siguiente_deshabilitado = "disabled" in next_button.get_attribute("class")

        # Obtener el valor seleccionado actualmente en el combobox
        selector_entradas = Select(driver.find_element(By.NAME, "tablaRespuestaGlosa_length"))
        entradas_actuales = selector_entradas.first_selected_option.get_attribute("value")

        return {
            "info_texto": info_texto,
            "anterior_deshabilitado": anterior_deshabilitado,
            "siguiente_deshabilitado": siguiente_deshabilitado,
            "entradas_actuales": entradas_actuales
        }
    except (NoSuchElementException, TimeoutException) as e:
        print(f"Advertencia: No se pudo obtener el estado de paginación. {e}")
        return None

def navegar_pagina(driver, direccion):
    """
    Hace clic en el botón 'Siguiente' o 'Anterior' de la paginación.
    Espera a que la tabla se recargue.
    """
    print(f"[Paginación] Navegando a la página '{direccion}'...")
    wait = WebDriverWait(driver, 30)
    
    if direccion == "siguiente":
        boton_selector = (By.ID, "tablaRespuestaGlosa_next")
    elif direccion == "anterior":
        boton_selector = (By.ID, "tablaRespuestaGlosa_previous")
    else:
        return

    # Hacemos clic en el enlace dentro del LI
    driver.find_element(*boton_selector).find_element(By.TAG_NAME, "a").click()
    
    # DataTables es astuto: muestra "Procesando..." brevemente. Esperamos a que desaparezca.
    procesando_selector = (By.ID, "tablaRespuestaGlosa_processing")
    wait.until(EC.invisibility_of_element_located(procesando_selector))
    print("[Paginación] ¡Nueva página cargada!")

    # --- LÍNEA A AGREGAR ---
    scroll_to_pagination(driver)

def cambiar_numero_entradas(driver, valor):
    """
    Cambia el número de entradas a mostrar en la tabla.
    """
    print(f"[Paginación] Cambiando a mostrar '{valor}' entradas...")
    wait = WebDriverWait(driver, 30)
    
    selector_entradas = Select(driver.find_element(By.NAME, "tablaRespuestaGlosa_length"))
    selector_entradas.select_by_value(str(valor))

    procesando_selector = (By.ID, "tablaRespuestaGlosa_processing")
    wait.until(EC.invisibility_of_element_located(procesando_selector))
    print("[Paginación] ¡Tabla actualizada con nuevas entradas!")

    scroll_to_pagination(driver)

def fase_buscar(driver, fecha_ini, fecha_fin, base_path):
    """Navega, filtra y extrae la lista de glosas de la PRIMERA PÁGINA."""
    print("[Fase Búsqueda] Iniciando...")
    wait = WebDriverWait(driver, 60)
    
    # Pasos 1 y 2 (Navegación y Filtro) - Esto ya está perfecto
    print("Navegando a la sección de glosas...")
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href="#respuestaGlo"]'))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href="respuestaGlosaSearch"]'))).click()
    print("Página de Bolsa Respuesta cargada.")

    print(f"Aplicando filtro de fechas: {fecha_ini} a {fecha_fin}")
    filtro_fecha_element = wait.until(EC.presence_of_element_located((By.ID, "filterBy")))
    select_obj = Select(filtro_fecha_element)
    select_obj.select_by_value("radicacion.fecha_radicacion")
    print("Filtro 'Fecha Radicacion' seleccionado.")
    
    fecha_ini_element = driver.find_element(By.ID, "fechaIni")
    driver.execute_script("arguments[0].value = arguments[1]", fecha_ini_element, fecha_ini)
    fecha_fin_element = driver.find_element(By.ID, "fechaFin")
    driver.execute_script("arguments[0].value = arguments[1]", fecha_fin_element, fecha_fin)
    
    driver.find_element(By.ID, "btBolsaSearchRespuesta").click()
    print("Botón 'Consultar' presionado.")

    # Paso 3: Esperar a que la tabla se recargue (Esto ya está perfecto)
    print("Esperando resultados y extrayendo datos...")
    cargando_selector = (By.XPATH, "//td[@class='dataTables_empty' and text()='Cargando...']")
    print("Esperando a que la tabla termine de cargar los datos del filtro...")
    wait.until(EC.invisibility_of_element_located(cargando_selector))
    print("¡Tabla cargada con los datos del filtro!")
    # --- LÍNEA A AGREGAR ---
    scroll_to_pagination(driver)
    print("Aplicando espera de 10 segundos para estabilización final de la tabla...")
    time.sleep(1)

    return extraer_datos_tabla_actual(driver)


def scroll_to_pagination(driver):
    """
    Hace scroll en la página web hasta que el panel de paginación sea visible.
    Esto asegura que los botones 'Siguiente' y 'Anterior' sean clickeables.
    """
    try:
        print("[Scroll] Desplazando a la vista del panel de paginación...")
        pagination_info_element = driver.find_element(By.ID, "tablaRespuestaGlosa_info")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", pagination_info_element)
        time.sleep(0.5) # Pequeña pausa para que el scroll termine
    except NoSuchElementException:
        print("Advertencia: No se encontró el panel de paginación para hacer scroll.")

def extraer_datos_tabla_actual(driver):
    """
    Función reutilizable que extrae datos y paginación de la tabla visible.
    """
    resultados = []
    try:
        num_filas = len(driver.find_elements(By.XPATH, "//table[@id='tablaRespuestaGlosa']/tbody/tr"))
        print(f"Extrayendo datos de {num_filas} filas en la página actual.")
        
        for i in range(1, num_filas + 1):
            base_xpath = f"//table[@id='tablaRespuestaGlosa']/tbody/tr[{i}]"
            
            row_text_check = driver.find_element(By.XPATH, base_xpath).text
            if not row_text_check or "ningún dato disponible" in row_text_check.lower():
                continue

            radicacion = driver.find_element(By.XPATH, f"{base_xpath}/td[2]").text
            fecha_rad = driver.find_element(By.XPATH, f"{base_xpath}/td[3]").text
            factura = driver.find_element(By.XPATH, f"{base_xpath}/td[5]").text
            valor_factura = driver.find_element(By.XPATH, f"{base_xpath}/td[7]").text
            valor_glosado = driver.find_element(By.XPATH, f"{base_xpath}/td[8]").text
            id_cuenta = driver.find_element(By.XPATH, f"{base_xpath}/td[9]/button").get_attribute("idcuenta")

            resultados.append({
                "id": id_cuenta,
                "radicacion": radicacion,
                "fecha_rad": fecha_rad,
                "factura": factura,
                "valor_factura": valor_factura,
                "valor_glosado": valor_glosado,
            })
    except Exception as e:
        print(f"Error al extraer datos de la tabla: {e}")
        resultados = []
        
    estado_paginacion = obtener_estado_paginacion(driver)
    
    return resultados, estado_paginacion


## NUEVA FUNCIÓN 1: La "Preparación"
def establecer_contexto_busqueda(driver, fecha_ini, fecha_fin):
    """
    Navega a la página de glosas y aplica el filtro de fecha una sola vez.
    Deja el navegador listo para las descargas individuales.
    """
    print("[Contexto] Estableciendo contexto de búsqueda por fecha...")
    wait = WebDriverWait(driver, 60)
    
    # Navegamos a la página si no estamos ya en ella
    if "respuestaGlosaSearch" not in driver.current_url:
        print("[Contexto] Navegando a la sección de glosas...")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href="#respuestaGlo"]'))).click()
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href="respuestaGlosaSearch"]'))).click()
    
    print(f"[Contexto] Aplicando filtro de fechas: {fecha_ini} a {fecha_fin}")
    filtro_fecha_element = wait.until(EC.presence_of_element_located((By.ID, "filterBy")))
    select_obj = Select(filtro_fecha_element)
    select_obj.select_by_value("radicacion.fecha_radicacion")
    
    fecha_ini_element = driver.find_element(By.ID, "fechaIni")
    driver.execute_script("arguments[0].value = arguments[1]", fecha_ini_element, fecha_ini)
    fecha_fin_element = driver.find_element(By.ID, "fechaFin")
    driver.execute_script("arguments[0].value = arguments[1]", fecha_fin_element, fecha_fin)
    
    driver.find_element(By.ID, "btBolsaSearchRespuesta").click()
    print("[Contexto] Botón 'Consultar' presionado.")
    
    cargando_selector = (By.XPATH, "//td[@class='dataTables_empty' and text()='Cargando...']")
    wait.until(EC.invisibility_of_element_located(cargando_selector))
    print("✅ [Contexto] ¡Contexto establecido! La tabla está lista.")
    time.sleep(2) # Pequeña pausa para estabilización final

def descargar_item_especifico(driver, item, download_dir, last_processed_id=None):
    """
    Busca, descarga y vuelve.
    Implementa una lógica de clic robusta y refresco condicional.
    """
    item_id = item['id']
    item_factura = item['factura']
    print(f"\n[Descarga] Procesando Factura: {item_factura} (ID: {item_id})")
    wait = WebDriverWait(driver, 10) # Reducimos el wait general a 10s para agilidad

    try:
        # --- Búsqueda y clic en 'Play' ---
        search_box_selector = (By.CSS_SELECTOR, "div#tablaRespuestaGlosa_filter input[type='search']")
        search_box = wait.until(EC.presence_of_element_located(search_box_selector))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_box)
        time.sleep(1)
        search_box.clear()
        search_box.send_keys(item_factura)
        time.sleep(5) 
        play_button_xpath = f"//button[@idcuenta='{item_id}']"
        play_button = wait.until(EC.element_to_be_clickable((By.XPATH, play_button_xpath)))
        play_button.click()
        
        print("[Descarga] Entrando a la vista de detalles...")
        
        # --- LÓGICA DE TRANSICIÓN CORREGIDA Y DEFINITIVA ---
        
        # Primero, hacemos el clic en el pop-up con reintentos
        confirm_button_selector = (By.CSS_SELECTOR, "button.swal2-confirm")
        max_retries = 5
        clicked = False
        for i in range(max_retries):
            try:
                # Usamos una espera corta aquí, porque el pop-up es rápido o no aparece
                WebDriverWait(driver, 2).until(EC.element_to_be_clickable(confirm_button_selector)).click()
                print(f"[Descarga] Clic en pop-up exitoso en intento {i+1}.")
                clicked = True
                break
            except TimeoutException:
                # Si no aparece en 2 segundos, asumimos que la página cargó sin pop-up
                print("[Descarga] Pop-up no detectado, continuando directamente.")
                clicked = True
                break
            except Exception as e:
                print(f"  -> Clic en pop-up falló (Intento {i+1}/{max_retries}): {e}. Reintentando...")
                time.sleep(0.5)

        if not clicked:
            raise Exception("No se pudo hacer clic en el pop-up de confirmación.")

        print("[Descarga] Ventana emergente gestionada.")
        
        # AHORA, esperamos a que la página de destino cargue.
        titulo_selector = (By.ID, "card-header-title-audit-start")
        print("[Descarga] Esperando a que la página de detalles cargue...")
        wait.until(EC.visibility_of_element_located(titulo_selector))
        print("✅ [Descarga] ¡Página de detalles cargada y confirmada!")
        
        # Y AHORA, JUSTO DESPUÉS DE CARGAR, DECIDIMOS SI REFRESCAR.
        if item_id == last_processed_id:
            print(f"-> [Inteligencia] Mismo ID ({item_id}) detectado. Forzando recarga (F5)...")
            driver.refresh()
            # Esperamos de nuevo a que el título aparezca después del refresh
            wait.until(EC.visibility_of_element_located(titulo_selector))
            print("   ...Recarga completada.")
        
        time.sleep(1) # Pausa final para estabilización

        # --- Lógica de Descarga (sin cambios) ---
        if item.get('detalle', False):
            # ...
            print("-> Descargando 'Detalle de cuenta'...")
            detalle_wrapper_selector = (By.ID, "tableAuditDetail_wrapper")
            wait.until(EC.visibility_of_element_located(detalle_wrapper_selector))
            print("[Descarga] Sección 'Detalles' cargada.")
            download_detalle_btn_selector = (By.XPATH, "//div[@id='tableAuditDetail_wrapper']//button[contains(., 'Descargar')]")
            download_button = wait.until(EC.element_to_be_clickable(download_detalle_btn_selector))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", download_button)
            time.sleep(1)
            download_button.click()
            print("[Descarga] Botón de descarga de detalles presionado.")
            if wait_for_new_file_to_download(download_dir, 60):
                print("✅ Descarga de detalles completada.")
            else:
                print("¡ADVERTENCIA! La descarga de detalles no finalizó en el tiempo esperado.")


        if item.get('glosa', False):
            # ...
            print("-> Descargando 'Glosas de la cuenta'...")
            glosa_wrapper_selector = (By.ID, "tableAuditGlosas_wrapper")
            wait.until(EC.visibility_of_element_located(glosa_wrapper_selector))
            print("[Descarga] Sección 'Glosas' cargada.")
            download_glosa_btn_selector = (By.XPATH, "//div[@id='tableAuditGlosas_wrapper']//button[contains(., 'Descargar')]")
            download_button = wait.until(EC.element_to_be_clickable(download_glosa_btn_selector))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", download_button)
            time.sleep(1)
            download_button.click()
            print("[Descarga] Botón de descarga de glosas presionado.")
            if wait_for_new_file_to_download(download_dir, 60):
                print("✅ Descarga de glosas completada.")
            else:
                print("¡ADVERTENCIA! La descarga de glosas no finalizó en el tiempo esperado.")

        print(f"[Descarga] Tarea para ID {item_id} completada. Volviendo a la lista...")
        driver.back()
        scroll_to_pagination(driver)

        
        # --- Lógica de reseteo ---
        wait.until(EC.presence_of_element_located((By.ID, "tablaRespuestaGlosa_wrapper")))
        search_box_reset = wait.until(EC.presence_of_element_located(search_box_selector))
        search_box_reset.clear()
        time.sleep(2)

        return item_id 
        
    except Exception as e:
        print(f"❌ [Descarga] No se pudo procesar el item ID {item_id}. Error: {e}")
        print("[Descarga] Intentando recuperar volviendo a la página de búsqueda principal...")
        try:
            driver.get("https://vco.ctamedicas.com/respuestaGlosaSearch")
        except Exception as nav_error:
            print(f"  -> No se pudo navegar de vuelta. Error de navegación: {nav_error}")
            
        return None
    
if __name__ == "__main__":
    # Este bloque es ahora el ÚNICO punto de entrada para la ejecución 
    # independiente del script. Es más claro y no hay duplicación.

    parser = argparse.ArgumentParser(description="Automatización de descarga de glosas.")
    parser.add_argument("--fase", required=True, choices=['buscar', 'descargar'], help="Fase a ejecutar.")
    parser.add_argument("--base-path", required=True, help="Ruta base de la aplicación.")
    parser.add_argument("--fecha-ini", help="Fecha de inicio (YYYY-MM-DD) para la búsqueda.")
    parser.add_argument("--fecha-fin", help="Fecha de fin (YYYY-MM-DD) para la búsqueda.")
    parser.add_argument("--items", help="String JSON con la lista de items a descargar.")
    parser.add_argument(
        "--mantener-abierto", 
        action="store_true", 
        help="Mantiene el navegador abierto después de completar la fase para interacción manual."
    )
    args = parser.parse_args()

    driver = None
    try:
        cookie = get_session_cookie(args.base_path)
        es_para_descargar = args.fase == 'descargar' or args.mantener_abierto
        driver, download_dir = setup_driver(args.base_path, for_download=es_para_descargar)
        
        # Inyectar cookie
        driver.get("https://vco.ctamedicas.com")
        driver.add_cookie({'name': 'PHPSESSID', 'value': cookie})
        driver.refresh()
        
        if args.fase == 'buscar':
            fase_buscar(driver, args.fecha_ini, args.fecha_fin, args.base_path)
        elif args.fase == 'descargar':
            items_a_descargar = json.loads(args.items)
            fase_descargar(driver, items_a_descargar, args.base_path, args.fecha_ini, args.fecha_fin, download_dir)

        if args.mantener_abierto:
            print("\n" + "="*50)
            print(" MODO INTERACTIVO: El navegador se mantendrá abierto.")
            print(" Presiona la tecla ENTER en esta consola para cerrar el navegador.")
            print("="*50)
            input()
    
    except Exception as e:
        print(f"ERROR FATAL: {e}")
        if args.mantener_abierto:
            input("Se produjo un error. Presiona Enter para cerrar...")        
    finally:
        if driver:
            print("Cerrando el navegador y finalizando el script.")
            driver.quit()
        sys.exit(0)
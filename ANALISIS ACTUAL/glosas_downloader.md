### **Análisis del Archivo: `glosas_downloader.py`**

#### **1. Propósito Principal**

Este script es el "trabajador" de la aplicación. Su objetivo es realizar operaciones automatizadas dentro de la sesión web que fue previamente establecida por `selenium_session_manager.py`. Específicamente, está diseñado para navegar a una sección de "Glosas" (un término común en auditoría médica/financiera), buscar información dentro de un rango de fechas y/o descargar archivos asociados a registros específicos.

Está diseñado para funcionar en **dos modos o fases distintas**: `buscar` y `descargar`, que se controlan mediante argumentos de línea de comandos.

#### **2. Componentes Clave**

El script se organiza en varias funciones de ayuda y dos funciones principales que corresponden a cada fase.

*   **Funciones de Ayuda:**
    *   `get_session_cookie(base_path)`: Esta es una pieza de conexión fundamental. Se conecta a la API de Notion (usando las credenciales del `config.ini`) para **leer la cookie `PHPSESSID`** que `selenium_session_manager.py` guardó allí. Esto le permite "secuestrar" o "reutilizar" la sesión activa sin necesidad de volver a iniciar sesión.
    *   `setup_driver(base_path, for_download=False)`: Crea una nueva instancia del navegador Chrome. A diferencia de `selenium_session_manager.py`, este navegador **no es headless**, lo que significa que mostrará una ventana visible en la pantalla. Crucialmente, si el argumento `for_download` es `True`, configura el navegador para que descargue archivos automáticamente a una carpeta específica (`C:\Users\<Usuario>\Downloads\Glosas_Coosalud`) sin preguntar.
    *   `wait_for_new_file_to_download(download_dir, timeout=60)`: Una función de utilidad muy inteligente. Monitorea un directorio de descargas esperando a que aparezca un nuevo archivo. Primero detecta el archivo temporal de Chrome (`.crdownload`) y luego espera a que este desaparezca (lo que indica que la descarga ha finalizado y el archivo ha sido renombrado). Esto resuelve el problema común de no saber cuándo una descarga ha terminado realmente.

*   **Funciones de Fase:**
    *   `fase_buscar(driver, fecha_ini, fecha_fin, base_path)`:
        1.  Navega a la sección de búsqueda de glosas.
        2.  Utiliza JavaScript (`driver.execute_script`) para establecer un rango de fechas en los campos de entrada. Este es un método robusto para manipular campos de fecha que a veces son problemáticos.
        3.  Hace clic en el botón "Consultar".
        4.  Espera a que un indicador de "Cargando..." desaparezca de la tabla de resultados, asegurando que los datos se han cargado.
        5.  Itera a través de las filas de la tabla de resultados, extrayendo datos de cada celda. Implementa una estrategia **anti-"Stale Element Reference Exception"**: en lugar de encontrar todos los elementos de una vez, vuelve a buscar cada fila por su índice en cada iteración del bucle, lo que es más resistente a cambios en el DOM de la página.
        6.  Guarda los datos extraídos en un archivo `glosas_results.json` en la `base_path`. Este archivo sirve como puente entre la fase de `buscar` y la de `descargar`.

    *   `fase_descargar(driver, items, base_path, fecha_ini, fecha_fin, download_dir)`:
        1.  **Establece el Contexto**: Primero, repite el proceso de filtrado por fecha. Esto es crucial porque asume que la búsqueda interna de la página web funciona mejor si primero se acota el universo de datos al rango de fechas correcto.
        2.  **Itera sobre los Items**: Recibe una lista de `items` (probablemente leídos desde `glosas_results.json`).
        3.  Para cada item:
            *   Utiliza la barra de búsqueda de la tabla para filtrar y encontrar la fila específica de la factura.
            *   Hace scroll para asegurar que la barra de búsqueda esté visible antes de interactuar con ella.
            *   Introduce el número de factura y espera un tiempo fijo (`time.sleep(5)`) para que el filtrado por JavaScript de la tabla se complete.
            *   Hace clic en el botón de "play" (o detalles) para ese registro.
            *   Maneja una ventana emergente de confirmación.
            *   Dentro de la página de detalles, busca y hace clic en los botones de "Descargar", utilizando la función `wait_for_new_file_to_download` para confirmar que cada archivo se ha guardado correctamente.
            *   Navega hacia atrás (`driver.back()`) para volver a la tabla y procesar el siguiente item.
        4.  Incluye manejo de errores para saltar a la siguiente iteración si un elemento no se encuentra.

*   **Bloque Principal (`if __name__ == "__main__":`)**
    *   Usa `argparse` para gestionar los argumentos de la línea de comandos. Esto es lo que lo hace tan flexible.
    *   `--fase`: El argumento más importante, decide si se ejecuta `fase_buscar` o `fase_descargar`.
    *   `--base-path`: Igual que en el script anterior, define la ruta raíz de la aplicación.
    *   `--fecha-ini`, `--fecha-fin`: Necesarios para ambas fases.
    *   `--items`: Un string en formato JSON, necesario solo para la fase `descargar`.
    *   **Flujo de ejecución**:
        1.  Llama a `get_session_cookie` para obtener la sesión de Notion.
        2.  Configura el driver de Selenium.
        3.  Abre la URL base del sitio.
        4.  **Inyecta la cookie `PHPSESSID`** en el navegador y refresca la página. Este es el paso mágico que le permite entrar a la sesión sin login.
        5.  Llama a la función de fase correspondiente (`fase_buscar` o `fase_descargar`) con los argumentos proporcionados.
        6.  Asegura que el `driver` se cierre correctamente en un bloque `finally`, incluso si ocurren errores.

#### **3. Dependencias y Conexiones**

*   **Librerías Python:** `os`, `sys`, `json`, `time`, `argparse`, `configparser`, `selenium`.
*   **Servicios Externos:**
    *   `https://api.notion.com`: Lee la cookie de sesión desde Notion.
    *   `https://vco.ctamedicas.com`: El sitio web donde realiza todas las operaciones.
*   **Archivos Locales (Necesidades):**
    *   `./config.ini`: Para las credenciales de Notion.
    *   `./chrome-win64/chromedriver.exe` y `./chrome-win64/chrome.exe`: El navegador y su controlador.
    *   `./glosas_results.json`: Este archivo es **leído** por la `fase_descargar` (pero es **creado** por la `fase_buscar`).
*   **Archivos Locales (Generados):**
    *   `glosas_results.json`: Creado por `fase_buscar`.
    *   Los archivos de glosas descargados en la carpeta `Downloads/Glosas_Coosalud`.

#### **4. Flujo de Lógica General**

1.  El script es invocado desde la línea de comandos, especificando una fase y otros parámetros.
2.  Lee la cookie de sesión activa desde Notion.
3.  Inicia un navegador Chrome visible.
4.  Inyecta la cookie en el navegador para autenticarse.
5.  **Si la fase es `buscar`**: Navega, filtra por fecha, extrae los datos de la primera página de la tabla y los guarda en `glosas_results.json`.
6.  **Si la fase es `descargar`**: Recibe una lista de items (en formato JSON), navega, filtra por fecha para establecer el contexto, y luego busca y descarga los archivos para cada item de la lista, uno por uno.
7.  Al finalizar, cierra el navegador.
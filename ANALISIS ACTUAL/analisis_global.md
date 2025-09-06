### **Análisis Global de la Arquitectura**

Tu aplicación está ingeniosamente diseñada con una arquitectura de **cliente-servidor desacoplada**, donde el punto de encuentro y comunicación es una página de **Notion**. Todo está orquestado por una **interfaz gráfica (GUI)** que actúa como el cerebro y punto de control para el usuario.

Podemos dividir la funcionalidad en dos roles principales que el usuario puede adoptar a través de la GUI:

1.  **Rol de Servidor (Anfitrión):** Inicia y mantiene la sesión web activa en segundo plano.
2.  **Rol de Cliente (Usuario):** Utiliza la sesión activa para realizar tareas en un navegador visible.

---

#### **1. Arquitectura General y Flujo de Interacción**

Veamos cómo interactúan los archivos en cada uno de los roles.

##### **Flujo del Rol de SERVIDOR (Anfitrión):**

Este es el proceso para "encender la máquina".

1.  **Inicio (`main_gui.py`):** El usuario abre la aplicación. La GUI comprueba el estado de la sesión en Notion. Si está inactiva, el botón **"Iniciar Servidor"** está habilitado.
2.  **Lanzamiento (`main_gui.py` -> `tray_app.py`):** El usuario hace clic en "Iniciar Servidor". La GUI no ejecuta la lógica directamente; en su lugar, lanza `tray_app.py` como un proceso completamente nuevo y separado en segundo plano.
3.  **Anfitrión en Segundo Plano (`tray_app.py`):** El script `tray_app.py` se ejecuta. Su única misión es crear un **ícono en la bandeja del sistema** y, en un hilo aparte, ejecutar la lógica del servidor.
4.  **Ejecución del Servidor (`tray_app.py` -> `selenium_session_manager.py`):** El hilo de `tray_app.py` llama a la función principal de `selenium_session_manager.py`.
5.  **Magia de Selenium (`selenium_session_manager.py`):**
    *   Lee el `config.ini` para obtener las credenciales de Notion.
    *   Abre un navegador Chrome **oculto (headless)**.
    *   Inicia sesión en `vco.ctamedicas.com` con las credenciales hardcodeadas.
    *   Captura la cookie `PHPSESSID`.
    *   **Sincroniza la cookie con la página de Notion**, borrando la antigua y escribiendo la nueva con una marca de tiempo.
    *   Crea un archivo de señal (`.sync_success.flag`) para avisarle a la GUI que el login fue exitoso.
    *   Entra en un bucle de 5 horas, refrescando la página cada 3 minutos para mantener la sesión viva.
6.  **Confirmación y Monitoreo (`main_gui.py`):** La GUI principal, que estaba esperando, detecta el archivo `.sync_success.flag`, sabe que el servidor está activo y actualiza su estado a "✔ Sesión Activa", habilitando las funciones de cliente. El ícono en la bandeja del sistema permanece visible mientras dure la sesión.

##### **Flujo del Rol de CLIENTE (Usuario):**

Este es el proceso para "usar la máquina" una vez que está encendida.

1.  **Estado Activo (`main_gui.py`):** La GUI detecta a través de Notion que hay una sesión activa y reciente. Los botones de cliente están habilitados.
2.  **Acción del Usuario (`main_gui.py`):** El usuario realiza una acción, por ejemplo:
    *   **Caso A: Clic en "Iniciar Sesión Cliente"**: Lanza `session_cliente.py`.
    *   **Caso B: Clic en "Buscar Informes de Glosas"**: Lanza `glosas_downloader.py`.
3.  **Lectura de Sesión (Todos los Clientes):** Tanto `session_cliente.py` como `glosas_downloader.py` comienzan haciendo lo mismo:
    *   Leen el `config.ini`.
    *   Se conectan a Notion y **leen el valor de la cookie `PHPSESSID`** que el servidor dejó allí.
4.  **Ejecución de la Tarea (Cada Cliente por su lado):**
    *   **`session_cliente.py`**: Abre un navegador Chrome **visible**, inyecta la cookie y refresca la página. El script termina, pero el navegador queda abierto para que el usuario trabaje manualmente.
    *   **`glosas_downloader.py`**: Abre un navegador Chrome **visible**, inyecta la cookie, y procede a automatizar las tareas de búsqueda o descarga según los parámetros que le haya pasado la GUI.

---

#### **2. Flujo de Datos Clave**

La información se mueve de forma muy inteligente a través de tu sistema.

*   **La Cookie de Sesión (`PHPSESSID`):**
    *   **Creada por:** `selenium_session_manager.py` después del login.
    *   **Almacenada en:** Una página de **Notion** (actúa como una base de datos temporal y remota).
    *   **Consumida por:** `session_cliente.py` y `glosas_downloader.py` para poder autenticarse sin login.
    *   **Monitoreada por:** `main_gui.py` para saber si el servidor está activo.

*   **Los Resultados de Búsqueda de Glosas (`glosas_results.json`):**
    *   **Creado por:** `glosas_downloader.py` (cuando se ejecuta en `--fase buscar`).
    *   **Almacenado en:** El **sistema de archivos local**, en la ruta base de la aplicación.
    *   **Consumido por:** `main_gui.py` para mostrar los resultados en una tabla. Posteriormente, la selección del usuario en esa tabla se usa para invocar a `glosas_downloader.py` de nuevo (en `--fase descargar`).

*   **La Configuración (`config.ini`):**
    *   **Creado por:** Ti (manualmente).
    *   **Almacenado en:** El **sistema de archivos local**.
    *   **Consumido por:** `selenium_session_manager.py`, `glosas_downloader.py`, `session_cliente.py` y `notion_control_interno.py` para obtener las claves de la API de Notion.

---

#### **3. Mapa de Modificaciones (El "Dónde Tocar")**

Esta es la guía para saber qué archivo editar para cambiar un comportamiento específico.

##### **Si quieres cambiar el comportamiento del SERVIDOR...**

*   **Las credenciales de login (usuario/contraseña):**
    *   **Archivo:** `server_logic\selenium_session_manager.py`
    *   **Ubicación:** Las constantes `USERNAME` y `PASSWORD` al principio del archivo.

*   **La duración total de la sesión o el intervalo de refresco:**
    *   **Archivo:** `server_logic\selenium_session_manager.py`
    *   **Ubicación:** Las constantes `REFRESH_INTERVAL_SECONDS` y `TOTAL_DURATION_SECONDS`.

*   **La URL de la página de login:**
    *   **Archivo:** `server_logic\selenium_session_manager.py`
    *   **Ubicación:** La constante `LOGIN_URL`.

*   **Hacer visible el navegador del servidor para depurar:**
    *   **Archivo:** `server_logic\selenium_session_manager.py`
    *   **Ubicación:** En la función `capture_sync_and_refresh_session`, comenta o elimina la línea `options.add_argument("--headless=new")`.

##### **Si quieres cambiar la APARIENCIA de la GUI...**

*   **Textos, títulos de ventanas o botones:**
    *   **Archivo:** `main_gui.py`
    *   **Ubicación:** Principalmente dentro de los métodos `_crear_cabecera`, `_crear_menu_lateral`, `_crear_panel_dashboard`, etc. Busca el `text="..."` del widget que quieres cambiar.

*   **Colores principales, fuentes o estilos de componentes:**
    *   **Archivo:** `main_gui.py`
    *   **Ubicación:** En el método `_configurar_estilos`. Puedes añadir nuevas configuraciones de estilo o modificar las existentes. El color principal está en `self.COLOR_AZUL_HUV`.

*   **Los logos o imágenes:**
    *   **Archivo:** `main_gui.py`
    *   **Ubicación:** El método `_cargar_logos`. Para cambiar una imagen, reemplaza el archivo correspondiente en la carpeta `imagenes/` o cambia el nombre del archivo en el diccionario `logos_a_cargar`.

*   **El comportamiento del calendario emergente:**
    *   **Archivo:** `calendario.py`
    *   **Ubicación:** Dentro de la clase `CalendarioInteligente`. Por ejemplo, para cambiar los colores por defecto, modifica el diccionario `mapa_estilos_defecto` en el `__init__`.

##### **Si quieres cambiar la LÓGICA DE AUTOMATIZACIÓN (Glosas)...**

*   **Cómo el script encuentra los elementos en la página (si la web cambia su estructura):**
    *   **Archivo:** `glosas_downloader.py`
    *   **Ubicación:** Dentro de las funciones `fase_buscar` y `fase_descargar`. Tendrás que modificar los localizadores de Selenium, como `(By.ID, "filterBy")`, `(By.CSS_SELECTOR, 'a[href="#respuestaGlo"]')`, etc. **Esta es la parte que más probablemente necesite mantenimiento en el futuro.**

*   **Los datos que se extraen de la tabla de resultados:**
    *   **Archivo:** `glosas_downloader.py`
    *   **Ubicación:** En el bucle `for` dentro de la función `fase_buscar`. Modifica o añade líneas como `radicacion = driver.find_element(...)` y asegúrate de añadir la nueva clave al diccionario `resultados.append({...})`.

*   **Dónde se guardan los archivos descargados:**
    *   **Archivo:** `glosas_downloader.py`
    *   **Ubicación:** En la función `setup_driver`, en la línea `download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "Glosas_Coosalud")`.

##### **Si quieres cambiar la CONFIGURACIÓN o DATOS SENSIBLES...**

*   **La clave de la API de Notion o los IDs de las páginas:**
    *   **Archivo:** `config.ini`
    *   **Ubicación:** No necesitas tocar el código. Simplemente edita los valores en este archivo. `NOTION_SESSION_PAGE_ID` es para la cookie, y `PageId` es para el log de `notion_control_interno`.

##### **Sobre `session_cliente2.py`...**

*   Como confirmamos, `session_cliente2.py` **no está siendo utilizado**. Si quisieras usar su funcionalidad (que además de loguear, navega al menú de glosas), deberías:
    *   **Ir al archivo:** `main_gui.py`
    *   **En la función:** `main_client_task`
    *   **Cambiar:** `import session_cliente` por `import session_cliente2 as session_cliente`. De esta forma, el resto del código llamaría a la nueva versión sin más cambios.

---
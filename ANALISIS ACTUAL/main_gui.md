### **Análisis del Archivo: `main_gui.py`**

#### **1. Propósito Principal**

Este script es el **centro de control y la interfaz gráfica principal (GUI)** de toda la aplicación. A diferencia de los otros scripts que son "trabajadores" de fondo, este es el componente con el que el usuario interactúa directamente.

Su propósito es multifacético:

1.  **Presentar una Interfaz de Usuario:** Ofrece una ventana principal con un dashboard, menús y un registro de actividad (consola).
2.  **Actuar como Despachador de Procesos:** Es un script "inteligente" que puede ejecutarse en diferentes modos. Dependiendo de los argumentos de línea de comandos con los que se inicie (`--run-server`, `--run-client`), puede lanzar la lógica del servidor o del cliente en segundo plano en lugar de mostrar la GUI.
3.  **Orquestar las Tareas:** Desde la GUI, el usuario puede iniciar tareas complejas (como buscar y descargar glosas). El script no ejecuta esta lógica pesada directamente, sino que **lanza los otros scripts (`glosas_downloader.py`) como subprocesos**, manteniendo la interfaz receptiva.
4.  **Monitorear el Estado del Sistema:** Comprueba periódicamente el estado de la sesión de Selenium (consultando Notion) y actualiza la interfaz en consecuencia, habilitando o deshabilitando funcionalidades.
5.  **Gestionar Roles (Anfitrión/Cliente):** La GUI adapta su comportamiento según el estado de la sesión. Si no hay sesión activa, permite al usuario actuar como "Anfitrión" e iniciar el servidor. Si la sesión ya está activa, le permite actuar como "Cliente" y utilizarla.

#### **2. Componentes Clave**

El script está estructurado en una clase principal `CoosaludApp` y un bloque de lanzamiento muy importante.

*   **Función `get_base_path()`:**
    *   Una función de utilidad crucial. Detecta si la aplicación se está ejecutando como un script normal de Python o como un ejecutable compilado (con PyInstaller). Esto le permite encontrar siempre sus archivos de recursos (imágenes, `config.ini`, `chrome-win64`) sin importar cómo se lance, lo que es fundamental para la portabilidad.

*   **Clase `CoosaludApp(ttk.Window)`:**
    *   **`__init__` (Constructor):**
        *   Recibe información del usuario (nombre, cargo, foto) como argumentos, lo que sugiere que está diseñada para ser lanzada por otro sistema (un "launcher" de Evarisis).
        *   Carga configuraciones (`config.ini`), logos e imágenes.
        *   Construye la interfaz gráfica llamando a métodos `_crear_...`.
        *   Inicia dos bucles de fondo con `self.after()`: uno para `comprobar_estado_servidor` y otro para `ejecutar_control_interno`.
        *   Define `on_closing` para asegurarse de que si la GUI inició un proceso de servidor, este se termine limpiamente al cerrar la ventana.
    *   **Métodos de Construcción de UI (`_crear_...`):**
        *   Crean y organizan los diferentes componentes visuales: la cabecera, el menú lateral, el panel principal (que puede cambiar entre vistas como "dashboard" y "configuración"), y una barra de estado.
        *   Destaca el `_crear_panel_configuracion` que incluye una **consola de texto (`scrolledtext`)** para mostrar logs y dar feedback al usuario sobre lo que ocurre en segundo plano.
    *   **Monitoreo de Estado y Lógica de Roles:**
        *   `comprobar_estado_servidor()` y `_tarea_comprobar_estado()`: Trabajan juntas. Inician un hilo que se conecta a Notion, lee el bloque de la sesión, y **verifica la marca de tiempo (`LastUpdate`)**. Si la marca de tiempo es reciente, considera la sesión activa.
        *   `_actualizar_ui_estado()`: Es el cerebro de la lógica de roles. Basado en el estado de la sesión, habilita/deshabilita los botones "Iniciar Servidor" y "Iniciar Sesión Cliente". Si la sesión está activa, también hace que la etiqueta de estado sea un botón gigante para facilitar el acceso.
    *   **Orquestación de Tareas (Glosas):**
        *   `iniciar_proceso_glosas()`: Abre el widget `CalendarioInteligente` para que el usuario seleccione un rango de fechas.
        *   `_tarea_buscar_glosas()`: Lanza `glosas_downloader.py` como un **subproceso** con los argumentos `--fase buscar` y las fechas seleccionadas. Espera a que termine.
        *   `_mostrar_resultados_glosas()`: Lee el `glosas_results.json` generado por el subproceso y muestra los datos en una tabla (`Treeview`). Crea los botones de descarga.
        *   `_tarea_descargar_glosas()`: Cuando el usuario selecciona filas y hace clic en descargar, esta función lanza `glosas_downloader.py` de nuevo, pero esta vez con `--fase descargar` y la lista de ítems seleccionados.
    *   **Lanzamiento de Subprocesos (`iniciar_servidor`, `iniciar_sesion_cliente`)**:
        *   Estos métodos lanzan **el propio script `main_gui.py` como un subproceso**, pero pasándole los argumentos `--run-server` o `--run-client`. Esta es una técnica de diseño clave para empaquetar toda la lógica en un solo punto de entrada.
        *   `_tarea_lanzar_servidor()` tiene una lógica de "handshake": después de lanzar el subproceso del servidor, **espera a que aparezca el archivo `.sync_success.flag`** para confirmar que el login y la sincronización inicial fueron exitosos.

*   **Bloque `if __name__ == "__main__":` (El Despachador):**
    *   Utiliza `argparse` para interpretar los argumentos de la línea de comandos.
    *   **Si se pasa `--run-server`**: Llama a `main_server_task()`, que a su vez parece que ejecutará `tray_app.py` (otro módulo que aún no he visto).
    *   **Si se pasa `--run-client`**: Llama a `main_client_task()`, que ejecutará la lógica de `session_cliente.py` (otro módulo pendiente).
    *   **Si no se pasa ninguno de los anteriores (Modo GUI por defecto)**:
        *   Realiza una comprobación de seguridad: debe estar presente el argumento `--lanzado-por-evarisis`. Si no, muestra un error y se cierra.
        *   Crea y ejecuta la instancia de la clase `CoosaludApp`, mostrando la ventana principal.

#### **3. Dependencias y Conexiones**

*   **Scripts Propios (Importados):** `notion_control_interno`, `glosas_downloader`, `calendario`.
*   **Scripts Propios (Ejecutados como Subprocesos):** `glosas_downloader.py`, `tray_app.py` (inferido), `session_cliente.py` (inferido), y `main_gui.py` (a sí mismo en diferentes modos).
*   **Archivos Locales (Necesidades):** `config.ini`, `gestorcoosalud.ico`, todas las imágenes en la carpeta `imagenes/`, y la estructura de `chrome-win64/`.
*   **Archivos Locales (Comunicación):**
    *   Espera la creación de `.sync_success.flag` por parte del proceso servidor.
    *   Lee `glosas_results.json` creado por `glosas_downloader.py`.
*   **Servicios Externos:** API de Notion (para monitorear el estado de la sesión).
*   **Librerías de Terceros:** `tkinter`, `ttkbootstrap`, `PIL` (Pillow), `requests`.

#### **4. Flujo de Lógica General**

1.  Un programa externo (Evarisis) lanza `main_gui.py` con argumentos de usuario y la bandera `--lanzado-por-evarisis`.
2.  La ventana de la aplicación (`CoosaludApp`) se abre.
3.  Inmediatamente, la GUI comienza a consultar la API de Notion en un bucle para verificar si hay una sesión activa.
4.  **Escenario A (No hay sesión):** La etiqueta de estado dice "Sesión Inactiva". El botón "Iniciar Servidor" está habilitado.
    *   El usuario hace clic en "Iniciar Servidor".
    *   La GUI se relanza a sí misma en un subproceso con el flag `--run-server`.
    *   Este subproceso ejecuta `tray_app.py`, que a su vez probablemente ejecute `selenium_session_manager.py`.
    *   `selenium_session_manager` hace el login y crea el archivo `.sync_success.flag`.
    *   La GUI principal detecta el archivo `.flag`, sabe que el login fue exitoso, y actualiza su estado a "Sesión Activa", habilitando las funciones de cliente.
5.  **Escenario B (Hay sesión activa):** La etiqueta de estado dice "Sesión Activa". El botón "Iniciar Servidor" está deshabilitado, y las funciones de cliente (como "Buscar Glosas") están habilitadas.
    *   El usuario hace clic en "Buscar Informes de Glosas".
    *   Se abre el calendario para seleccionar fechas.
    *   La GUI lanza `glosas_downloader.py --fase buscar` en un subproceso.
    *   Cuando termina, la GUI lee el JSON resultante y muestra los datos en una tabla.
    *   El usuario selecciona filas y hace clic en "Descargar".
    *   La GUI lanza `glosas_downloader.py --fase descargar` en otro subproceso.
    *   La descarga ocurre en segundo plano mientras la GUI permanece activa.
    *   Todo el progreso se reporta en la consola de la GUI.
6.  Al cerrar la ventana principal, cualquier proceso de servidor que haya iniciado se termina.

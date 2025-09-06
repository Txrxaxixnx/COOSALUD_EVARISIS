# main_gui.py:
import tkinter as tk
from tkinter import messagebox, scrolledtext
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import os
import sys
import subprocess
import threading
from datetime import datetime, timedelta
import requests
import time # Asegúrate de tenerlo importado


from ttkbootstrap.dialogs import Messagebox
import json

# Importamos la lógica que acabamos de separar
try:
    import notion_control_interno
    import glosas_downloader
    from calendario import CalendarioInteligente
except ImportError as e:
    print(f"Error de importación: {e}") # <-- Mensaje más claro
    notion_control_interno = None
    glosas_downloader = None
    CalendarioInteligente = None

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

class CoosaludApp(ttk.Window):
    def __init__(self, nombre_usuario, cargo_usuario, foto_path, tema):
        super().__init__(themename=tema)

        self.server_process = None

        ## ---- NUEVOS ATRIBUTOS PARA GESTIONAR EL NAVEGADOR ---- ##
        self.driver_glosas = None # Guardará la instancia del navegador
        self.download_dir_glosas = None # Guardará la ruta de descargas
        self.glosas_thread_lock = threading.Lock() # Evita ejecutar dos tareas de glosas a la vez
        self.last_processed_glosa_id = None # <-- AÑADIR ESTA LÍNEA
        self.resultados_actuales = [] # <-- NUEVO: Para guardar los datos


        ## -------------------------------------------------------- ##

        self.current_user = {"nombre": nombre_usuario, "cargo": cargo_usuario}
        self.foto_usuario = self._cargar_foto_usuario(foto_path)

        self.title("EVARISIS GESTOR COOSALUD")
        self.state('zoomed')
        self.base_path = get_base_path()

        try:
            # Construimos la ruta al ícono usando la ruta base que ya funciona
            # para el modo normal y el modo compilado (_internal).
            icon_path = os.path.join(self.base_path, "gestorcoosalud.ico")
            self.iconbitmap(icon_path)
        except Exception as e:
            # Si el ícono no se encuentra, la app no se romperá.
            # Simplemente mostrará una advertencia en la consola.
            print(f"Advertencia: No se pudo cargar el ícono de la aplicación: {e}")

        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(os.path.join(self.base_path, 'config.ini'))
            
            # Cargar configuración de Notion
            self.NOTION_API_KEY = config['Notion']['ApiKey']
            self.NOTION_SESSION_PAGE_ID = config['Notion']['NOTION_SESSION_PAGE_ID']
            
            # Cargar rutas de Chrome (para Selenium)
            self.chrome_driver_path = os.path.join(self.base_path, "chrome-win64", "chromedriver.exe")
            # Opcional: Si quieres forzar el uso del Chrome empaquetado
            self.chrome_binary_path = os.path.join(self.base_path, "chrome-win64", "chrome.exe")

        except (KeyError, configparser.Error) as e:
            messagebox.showerror("Error de Configuración", f"No se pudo leer 'config.ini' o falta una clave.\nDetalles: {e}")
            self.destroy() # Cierra la app si no puede leer la config
            return
        
        self.image_path = os.path.join(self.base_path, "imagenes")
        self.COLOR_AZUL_HUV = "#005A9C"
        self.logos = self._cargar_logos()
        self._configurar_estilos()
        self._crear_widgets()

        # Iniciar procesos automáticamente
        self.after(500, self.comprobar_estado_servidor)
        self.after(1000, self.ejecutar_control_interno) # Nuevo paso
        self.protocol("WM_DELETE_WINDOW", self.on_closing)


    def _cargar_logos(self):
        logos = {}
        logos_a_cargar = {
            "huv": "logo1.jpg", "coosalud": "logo1.png",
            "innovacion_cartoon": "logo2.png", "innovacion_moderno": "logo3.png"
        }
        for nombre, archivo in logos_a_cargar.items():
            try:
                ruta_completa = os.path.join(self.image_path, archivo)
                size = (120, 40) if nombre == "coosalud" else (80, 80)
                img = Image.open(ruta_completa).resize(size, Image.Resampling.LANCZOS)
                logos[nombre] = ImageTk.PhotoImage(img)
            except Exception: logos[nombre] = None
        return logos

    def _cargar_foto_usuario(self, foto_path):
        if foto_path and foto_path != "SIN_FOTO" and os.path.exists(foto_path):
            try:
                img = Image.open(foto_path).resize((60, 60), Image.Resampling.LANCZOS)
                # Podríamos redondear la imagen si quisiéramos, pero por ahora la dejamos cuadrada
                return ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Error al cargar foto de usuario: {e}")
        return None
    
    def _configurar_estilos(self):
        style = self.style
        style.configure('Sidebar.TButton', font=('Segoe UI', 12), anchor='w')
        style.configure('Header.TLabel', font=('Segoe UI', 22, "bold"), foreground=self.COLOR_AZUL_HUV)
        style.configure('Status.TLabel', font=('Segoe UI', 11, 'bold'), padding=10)

    def _crear_widgets(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._crear_cabecera()
        self._crear_menu_lateral()
        self._crear_panel_principal()
        self._crear_barra_estado()
    
    def _crear_cabecera(self):
        header_frame = ttk.Frame(self, padding=(20, 10), style='primary.TFrame')
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        if self.logos.get("huv"): 
            ttk.Label(header_frame, image=self.logos["huv"], style='primary.TLabel').pack(side=LEFT, padx=(0, 15))
        
        ttk.Label(header_frame, text="EVARISIS GESTOR COOSALUD", style='Header.TLabel', background=self.style.colors.primary).pack(side=LEFT, expand=True)
        
        # --- BLOQUE MODIFICADO: Perfil de Usuario a la derecha ---
        if self.foto_usuario:
            ttk.Label(header_frame, image=self.foto_usuario, style='primary.TLabel').pack(side=RIGHT, padx=10)

        profile_info_frame = ttk.Frame(header_frame, style='primary.TFrame')
        profile_info_frame.pack(side=RIGHT, padx=(0, 10))

        ttk.Label(profile_info_frame, text=self.current_user["nombre"], font=('Segoe UI', 12, "bold"), anchor=E, style='primary.TLabel').pack(fill=X)
        ttk.Label(profile_info_frame, text=self.current_user["cargo"], font=('Segoe UI', 9), anchor=E, style='secondary.TLabel').pack(fill=X) # Usamos secondary para el cargo

    def _crear_menu_lateral(self):
            sidebar_frame = ttk.Frame(self, padding=20, width=250)
            sidebar_frame.grid(row=1, column=0, sticky="ns")
            sidebar_frame.grid_propagate(False)

            # 1. La etiqueta de estado. La haremos CLICABLE cuando la sesión esté activa.
            self.lbl_estado_servidor = ttk.Label(sidebar_frame, text=" ⚪ Comprobando...", bootstyle="secondary")
            self.lbl_estado_servidor.configure(style='Status.TLabel')
            self.lbl_estado_servidor.pack(fill=X, pady=(0, 30))

            # 2. El botón para el ROL DE CLIENTE (inyectar cookie).
            # Lo renombramos para claridad y lo asociamos a un nuevo método.
            self.btn_iniciar_sesion_cliente = ttk.Button(sidebar_frame, text="  Iniciar Sesión Cliente", style='Sidebar.TButton', command=self.iniciar_sesion_cliente)
            self.btn_iniciar_sesion_cliente.pack(fill=X, pady=5, ipady=10)
            
            # 3. El botón para el ROL DE ANFITRIÓN (iniciar el servidor).
            self.btn_iniciar_servidor = ttk.Button(sidebar_frame, text="  Iniciar Servidor", style='Sidebar.TButton', command=self.iniciar_servidor, state="disabled")
            self.btn_iniciar_servidor.pack(fill=X, pady=5, ipady=10)
            
            ttk.Button(sidebar_frame, text="  Dashboard", style='Sidebar.TButton', command=lambda: self.mostrar_panel("dashboard")).pack(fill=X, pady=5, ipady=10)
            ttk.Button(sidebar_frame, text="  Configuración", style='Sidebar.TButton', command=lambda: self.mostrar_panel("configuracion")).pack(fill=X, pady=5, ipady=10)

    def _crear_panel_principal(self):
        self.main_panel = ttk.Frame(self, padding=(20,20,20,0))
        self.main_panel.grid(row=1, column=1, sticky="nsew")
        self.main_panel.grid_rowconfigure(0, weight=1)
        self.main_panel.grid_columnconfigure(0, weight=1)

        self.paneles = {}
        self.paneles["bienvenida"] = self._crear_panel_bienvenida()
        self.paneles["dashboard"] = self._crear_panel_dashboard()
        self.paneles["configuracion"] = self._crear_panel_configuracion()
        
        self.mostrar_panel("bienvenida")

    def _crear_panel_bienvenida(self):
        panel = ttk.Frame(self.main_panel)
        panel.grid(row=0, column=0, sticky="nsew")
        content_frame = ttk.Frame(panel)
        content_frame.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(content_frame, text="Bienvenido/a", font=("Segoe UI", 20, "bold")).pack(pady=10)
        info_text = "La herramienta está iniciando los controles internos.\nPor favor, espere mientras se verifica el estado de la sesión..."
        ttk.Label(content_frame, text=info_text, font=("Segoe UI", 12), justify="center").pack(pady=10, fill=X)
        return panel

    def _crear_panel_configuracion(self):
        panel = ttk.Frame(self.main_panel, padding=(0, 0, 0, 10)) # Añadimos padding inferior
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1) # Fila para la consola
        panel.grid_columnconfigure(0, weight=1) # Columna única

        # Contenido del panel (puedes agregar configuraciones aquí en el futuro)
        content_frame = ttk.Frame(panel)
        content_frame.grid(row=0, column=0, sticky="new", pady=(0, 20))
        ttk.Label(content_frame, text="Panel de Configuración", font=("Segoe UI", 20, "bold")).pack(pady=10)
        ttk.Label(content_frame, text="Aquí se mostrará el registro de procesos y futuras opciones.", font=("Segoe UI", 12)).pack()
        
        # AÑADIMOS LA CONSOLA AQUÍ ABAJO
        console_frame = ttk.Labelframe(panel, text="Registro de Proceso", padding=10)
        console_frame.grid(row=1, column=0, sticky="nsew") # Se expande

        self.console_text = scrolledtext.ScrolledText(console_frame, height=8, state="disabled", wrap=tk.WORD, font=("Consolas", 10))
        self.console_text.pack(fill="both", expand=True)
        
        return panel

    def _crear_panel_dashboard(self):
        # ... (código existente hasta la creación de self.results_frame)
        panel = ttk.Frame(self.main_panel)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_rowconfigure(2, weight=1) # Fila para la tabla
        panel.grid_columnconfigure(0, weight=1)

        ttk.Label(panel, text="Dashboard de Tareas Automatizadas", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky='w')
        
        self.btn_glosas = ttk.Button(panel, text="Buscar Informes de Glosas", command=self.iniciar_proceso_glosas, bootstyle="success", state="disabled")
        self.btn_glosas.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)

        self.results_frame = ttk.Frame(panel, padding=(0, 20, 0, 0))
        self.results_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        
        # ## INICIO DE LA NUEVA SECCIÓN DE PAGINACIÓN ##
        self.pagination_frame = ttk.Frame(panel, padding=(0, 10, 0, 0))
        self.pagination_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.pagination_frame.grid_columnconfigure(2, weight=1) # Columna del medio se expande

        # Controles (se crearán vacíos y se llenarán después)
        self.combo_entradas = ttk.Combobox(self.pagination_frame, values=["20", "50", "100", "500", "Todos"], state="readonly", width=8)
        self.combo_entradas.bind("<<ComboboxSelected>>", self.on_cambiar_entradas)
        self.combo_entradas.pack(side=LEFT, padx=5)

        self.btn_anterior = ttk.Button(self.pagination_frame, text="Anterior", command=lambda: self.on_navegar("anterior"))
        self.btn_anterior.pack(side=LEFT, padx=5)
        
        self.lbl_paginacion_info = ttk.Label(self.pagination_frame, text="", anchor="center")
        self.lbl_paginacion_info.pack(side=LEFT, padx=10, expand=True, fill=X)
        
        self.btn_siguiente = ttk.Button(self.pagination_frame, text="Siguiente", command=lambda: self.on_navegar("siguiente"))
        self.btn_siguiente.pack(side=RIGHT, padx=5)

        self.pagination_frame.grid_remove() # Ocultamos el panel al inicio
        # ## FIN DE LA NUEVA SECCIÓN ##

        return panel

    def mostrar_panel(self, nombre_panel):
        for panel in self.paneles.values():
            panel.grid_forget()
        self.paneles[nombre_panel].grid(row=0, column=0, sticky="nsew")

    def _crear_barra_estado(self):
        status_bar = ttk.Frame(self, padding=(10, 5), style='secondary.TFrame')
        status_bar.grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Label(status_bar, text="Desarrollado por Innovación y Desarrollo del HUV Versión 2.0", font=("Segoe UI", 8), style='secondary.TLabel').pack(side=LEFT)
        self.lbl_reloj = ttk.Label(status_bar, font=("Segoe UI", 8), style='secondary.TLabel')
        self.lbl_reloj.pack(side=RIGHT)
        self._actualizar_reloj()

    def _actualizar_reloj(self):
        now = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        self.lbl_reloj.config(text=now)
        self.after(1000, self._actualizar_reloj)

    def _log_to_console(self, message):
        self.console_text.config(state="normal")
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)
        self.console_text.config(state="disabled")

    # ## MODIFICADO ##: La función on_closing ahora también cierra el navegador.
    def on_closing(self):
        """Maneja el evento de cierre de la ventana principal de forma segura."""
        self._log_to_console("Cerrando aplicación...")

        # Lógica existente para cerrar el proceso del servidor
        if self.server_process and self.server_process.poll() is None:
            self._log_to_console("[GUI] Cerrando el proceso del servidor en segundo plano...")
            self.server_process.terminate()
            self.server_process.wait()
            self._log_to_console("[GUI] Proceso del servidor cerrado.")
        
        # ## NUEVO ##: Lógica para cerrar el navegador de glosas si está abierto
        if self.driver_glosas:
            self._log_to_console("[Glosas] Cerrando navegador de automatización...")
            try:
                self.driver_glosas.quit()
            except Exception as e:
                self._log_to_console(f"Error al cerrar el driver de glosas: {e}")

        self.destroy() # Cierra la ventana de la GUI
    # --- MONITOREO DE ESTADO (Como te indiqué antes) ---
    def comprobar_estado_servidor(self):
        threading.Thread(target=self._tarea_comprobar_estado, daemon=True).start()

    def _tarea_comprobar_estado(self):
        # ... (Esta función la dejas exactamente como te la pasé en mi respuesta anterior,
        # la que consulta Notion y valida el timestamp. No la repito aquí por brevedad) ...
        # ... pero asegúrate de que esté aquí.
        headers = { "Authorization": f"Bearer {self.NOTION_API_KEY}", "Notion-Version": "2022-06-28" }
        url = f"https://api.notion.com/v1/blocks/{self.NOTION_SESSION_PAGE_ID}/children"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            texto_bloque = None
            for block in data.get("results", []):
                if block.get("type") == "paragraph":
                    rt = block.get("paragraph", {}).get("rich_text", [])
                    if rt and rt[0].get("plain_text", "").startswith("Session PHPSESSID:"):
                        texto_bloque = rt[0].get("plain_text")
                        break
            if not texto_bloque:
                self.after(0, self._actualizar_ui_estado, "danger", "✖ Sesión Inactiva", True)
                return
            timestamp_str = texto_bloque.split("| LastUpdate:")[1].strip()
            last_update = datetime.fromisoformat(timestamp_str)
            if datetime.now() - last_update > timedelta(minutes=5):
                bootstyle, texto, habilitar_boton = "warning", "⚠ Sesión Expirada", True
            else:
                bootstyle, texto, habilitar_boton = "success", "✔ Sesión Activa", False
            self.after(0, self._actualizar_ui_estado, bootstyle, texto, habilitar_boton)
        except requests.RequestException:
            self.after(0, self._actualizar_ui_estado, "danger", "✖ Error de Red", True)
        except (IndexError, ValueError):
            self.after(0, self._actualizar_ui_estado, "danger", "✖ Bloque Malformado", True)
        finally:
            self.after(60000, self.comprobar_estado_servidor)
            
    def _actualizar_ui_estado(self, bootstyle, texto, habilitar_boton_servidor):
        """Actualiza la UI para reflejar el estado de la sesión, controlando ambos roles."""
        self.lbl_estado_servidor.configure(text=texto, bootstyle=bootstyle)
        
        # --- LÓGICA DE CONTROL DE ROLES ---

        # 1. Control del botón del SERVIDOR (Anfitrión)
        estado_servidor = "normal" if habilitar_boton_servidor else "disabled"
        self.btn_iniciar_servidor.config(state=estado_servidor)
        
        # 2. Control del botón y la etiqueta del CLIENTE
        # Si la sesión está ACTIVA (es decir, el botón del servidor está DESHABILITADO)...
        if not habilitar_boton_servidor:
            # Habilitamos el botón del cliente
            self.btn_iniciar_sesion_cliente.config(state="normal")
            self.btn_glosas.config(state="normal") # Habilitamos el botón de descarga

            # Y hacemos que la etiqueta de estado sea un botón gigante y obvio
            self.lbl_estado_servidor.config(cursor="hand2") # Cambia el cursor a una mano
            self.lbl_estado_servidor.bind("<Button-1>", lambda e: self.iniciar_sesion_cliente())
            self.lbl_estado_servidor.configure(text="✔ Sesión Activa (Clic aquí para usar)") # Texto más claro
        else:
            # Si la sesión está INACTIVA, deshabilitamos todo lo del cliente
            self.btn_iniciar_sesion_cliente.config(state="disabled")
            self.btn_glosas.config(state="disabled") # Deshabilitamos el botón de descarga
            self.lbl_estado_servidor.config(cursor="") # Cursor normal
            self.lbl_estado_servidor.unbind("<Button-1>") # Quitamos el evento clic

    # --- CONTROL INTERNO (Sin cambios, pero eliminando la activación del botón) ---
    def ejecutar_control_interno(self):
        if not notion_control_interno:
            self._log_to_console("❌ ERROR: El módulo 'notion_control_interno.py' no se encontró.")
            messagebox.showerror("Error Crítico", "No se encontró el módulo de control interno.")
            return
        self._log_to_console("[1/2] Iniciando control interno...")
        threading.Thread(target=self._tarea_control_interno, daemon=True).start()

    def _tarea_control_interno(self):
        exito = notion_control_interno.registrar_uso(lambda msg: self.after(0, self._log_to_console, msg),
                                                    self.base_path # <-- Aquí le damos la ruta correcta que calculamos en __init__

        )
        self.after(0, self._finalizar_control_interno, exito)

    def _finalizar_control_interno(self, exito):
        if exito:
            self._log_to_console("✅ Control interno concretado.")
        else:
            self._log_to_console("❌ La fase de control interno falló.")
            messagebox.showerror("Error de Control", "No se pudo registrar el uso de la herramienta.")

    # --- LÓGICA PARA EL ROL DE ANFITRIÓN (Iniciar Servidor) ---
    def iniciar_servidor(self):
        self.btn_iniciar_servidor.config(state="disabled")
        self._log_to_console("\n[Anfitrión] Iniciando secuencia del servidor...")
        threading.Thread(target=self._tarea_lanzar_servidor, daemon=True).start()


    def _tarea_lanzar_servidor(self):
        """
        Lanza el servidor unificado y espera una señal de éxito para actualizar la UI.
        """
        try:
            python_exe = sys.executable
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"

            # --- LÓGICA CONDICIONAL PARA COMPATIBILIDAD ---
            # Construimos el comando base
            command = [python_exe]
            
            # Si NO estamos compilados (ejecutando .py), debemos añadir el nombre del script
            if not getattr(sys, 'frozen', False):
                command.append(sys.argv[0]) # sys.argv[0] es 'main_gui.py'
            
            # Añadimos las banderas para que el subproceso sepa qué hacer
            command.extend(["--run-server", f"--base-path={self.base_path}"])
            # --- FIN DE LA LÓGICA CONDICIONAL ---
            
            flag_file_path = os.path.join(self.base_path, '.sync_success.flag') # La ruta al archivo señal

            # 1. Limpieza: Asegurarnos de que no exista una señal de una ejecución anterior.
            if os.path.exists(flag_file_path):
                os.remove(flag_file_path)

            # 2. Lanzar el servidor en segundo plano.
            self.after(0, self._log_to_console, "[Anfitrión] Lanzando el gestor de sesión del servidor...")
            self.server_process = subprocess.Popen(
                command,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW 
            )
            
            # 3. Esperar activamente la señal (con un tiempo máximo de espera).
            self.after(0, self._log_to_console, "[Anfitrión] ...esperando señal de sincronización exitosa del servidor...")
            timeout = 45  # Esperar un máximo de 45 segundos
            start_time = time.time()
            sync_success = False
            while time.time() - start_time < timeout:
                if os.path.exists(flag_file_path):
                    self.after(0, self._log_to_console, "✅ [Anfitrión] ¡Señal recibida! La sincronización inicial fue un éxito.")
                    os.remove(flag_file_path) # Limpiamos el archivo señal
                    sync_success = True
                    break
                time.sleep(0.5) # Esperar medio segundo antes de volver a comprobar

            # 4. Reaccionar al resultado.
            if sync_success:
                self.after(0, self._log_to_console, "[Anfitrión] Forzando actualización de estado de la UI...")
                # Forzamos una comprobación inmediata del estado del servidor.
                # Esto actualizará el botón del cliente al instante.
                self.comprobar_estado_servidor()
            else:
                self.after(0, self._log_to_console, "❌ [Anfitrión] Error: El servidor no envió la señal de éxito a tiempo.")
                self.after(0, lambda: self.btn_iniciar_servidor.config(state="normal")) # Reactivar botón

        except Exception as e:
            error_msg = f"❌ [Anfitrión] Error inesperado al lanzar la secuencia: {e}"
            self.after(0, self._log_to_console, error_msg)
            self.after(0, lambda: self.btn_iniciar_servidor.config(state="normal"))

    # --- LÓGICA PARA EL ROL DE CLIENTE (Usar Sesión) ---
    def iniciar_sesion_cliente(self):
        self._log_to_console("\n[Cliente] Solicitando inicio de sesión...")
        threading.Thread(target=self._tarea_iniciar_sesion_cliente, daemon=True).start()

    def _tarea_iniciar_sesion_cliente(self):
        """Lanza el script de cliente dedicado en un proceso separado."""
        try:
            python_exe = sys.executable


            # --- LÓGICA CONDICIONAL PARA COMPATIBILIDAD ---
            command = [python_exe]
            if not getattr(sys, 'frozen', False):
                command.append(sys.argv[0]) # Añade 'main_gui.py'
            
            command.extend(["--run-client", f"--base-path={self.base_path}"])
            # --- FIN DE LA LÓGICA CONDICIONAL ---


            # Lanzamos el script de cliente, no necesita consola
            subprocess.Popen(
                command, 
                creationflags=subprocess.CREATE_NO_WINDOW  
            )
            self.after(0, self._log_to_console, "✅ [Cliente] Orden de inicio de sesión enviada.")
        except Exception as e:
            error_msg = f"❌ [Cliente] Error al lanzar el proceso del cliente: {e}"
            self.after(0, self._log_to_console, error_msg)


    ## NUEVO ##: Función para iniciar el navegador una sola vez.
    def _iniciar_navegador_glosas_si_no_existe(self):
        """
        Verifica si el driver de glosas existe. Si no, lo crea, inicia sesión
        y lo guarda en self.driver_glosas.
        """
        if self.driver_glosas:
            self.after(0, self._log_to_console, "[Glosas] Reutilizando navegador ya existente.")
            return True

        try:
            self.after(0, self._log_to_console, "[Glosas] Iniciando nuevo navegador de automatización...")
            cookie = glosas_downloader.get_session_cookie(self.base_path)
            
            # Llamamos a setup_driver de nuestro módulo importado
            self.driver_glosas, self.download_dir_glosas = glosas_downloader.setup_driver(self.base_path, for_download=True)
            
            self.after(0, self._log_to_console, "[Glosas] Inyectando cookie de sesión...")
            self.driver_glosas.get("https://vco.ctamedicas.com")
            self.driver_glosas.add_cookie({'name': 'PHPSESSID', 'value': cookie})
            self.driver_glosas.refresh()
            self.after(0, self._log_to_console, "✅ [Glosas] Navegador listo y sesión iniciada.")
            return True
        except Exception as e:
            self.after(0, self._log_to_console, f"❌ [Glosas] Error fatal al iniciar el navegador: {e}")
            self.after(0, lambda: Messagebox.show_error(f"No se pudo iniciar el navegador de automatización:\n\n{e}", "Error Crítico"))
            self.driver_glosas = None # Aseguramos un estado limpio
            return False

    def iniciar_proceso_glosas(self):
        """Paso 1: Preguntar al usuario por el rango de fechas usando CalendarioInteligente."""
        
        if not CalendarioInteligente:
            messagebox.showerror("Error de Módulo", "El módulo 'calendario.py' no se pudo cargar. No se puede continuar.")
            return

        # --- SELECCIÓN DE FECHA DE INICIO ---
        self._log_to_console("\n[Glosas] Solicitando fecha de inicio...")
        fecha_ini_obj = CalendarioInteligente.seleccionar_fecha(
            parent=self,
            titulo="Seleccione la FECHA DE INICIO",
            codigo_pais_festivos='CO', # Festivos de Colombia
            locale='es_CO'
        )
        
        if not fecha_ini_obj:
            self._log_to_console("[Glosas] Proceso cancelado por el usuario (fecha de inicio).")
            return # El usuario cerró el primer calendario
        
        fecha_ini_str = fecha_ini_obj.strftime("%Y-%m-%d")
        self._log_to_console(f"[Glosas] Fecha de inicio seleccionada: {fecha_ini_str}")

        # --- SELECCIÓN DE FECHA DE FIN ---
        self._log_to_console("[Glosas] Solicitando fecha de fin...")
        fecha_fin_obj = CalendarioInteligente.seleccionar_fecha(
            parent=self,
            titulo="Seleccione la FECHA DE FIN",
            fecha_inicial=fecha_ini_obj, # El segundo calendario empieza donde terminó el primero
            codigo_pais_festivos='CO',
            locale='es_CO'
        )
        
        if not fecha_fin_obj:
            self._log_to_console("[Glosas] Proceso cancelado por el usuario (fecha de fin).")
            return # El usuario cerró el segundo calendario

        # Validación de fechas
        if fecha_fin_obj < fecha_ini_obj:
            self._log_to_console("[Glosas] Error: La fecha de fin es anterior a la de inicio.")
            Messagebox.show_error("La fecha de fin no puede ser anterior a la fecha de inicio.", "Error de Fechas")
            return
            
        fecha_fin_str = fecha_fin_obj.strftime("%Y-%m-%d")
        self.fecha_ini_actual = fecha_ini_str
        self.fecha_fin_actual = fecha_fin_str
        # ## NUEVO ##: Control para no ejecutar dos tareas a la vez
        if not self.glosas_thread_lock.acquire(blocking=False):
            self._log_to_console("⚠️ [Glosas] Ya hay una tarea en ejecución. Por favor, espere.")
            Messagebox.show_warning("Ya hay una tarea de glosas en ejecución. Por favor, espere a que termine.", "Tarea en Progreso")
            return                
        # Lanzamos la tarea pesada en un hilo
        self._log_to_console(f"[Glosas] Buscando registros entre {fecha_ini_str} y {fecha_fin_str}...")
        hilo_busqueda = threading.Thread(
            target=self._tarea_buscar_glosas, 
            args=(fecha_ini_str, fecha_fin_str),
            daemon=True
        )
        hilo_busqueda.start()

    def _tarea_buscar_glosas(self, fecha_ini, fecha_fin):
        """Paso 2: Ejecuta la búsqueda y obtiene la primera página de datos."""
        try:
            if not self._iniciar_navegador_glosas_si_no_existe():
                return
            
            self.after(0, self._log_to_console, "[Glosas] Ejecutando búsqueda inicial...")
            
            # Ahora fase_buscar devuelve dos cosas
            resultados, estado_paginacion = glosas_downloader.fase_buscar(self.driver_glosas, fecha_ini, fecha_fin, self.base_path)
            
            self.after(0, self._log_to_console, f"✅ [Glosas] Búsqueda completada. {estado_paginacion['info_texto']}.")
            
            # Guardamos los resultados y actualizamos TODA la UI
            self.resultados_actuales = resultados
            self.after(0, self._actualizar_ui_resultados, resultados, estado_paginacion)

        except Exception as e:
            self.after(0, self._log_to_console, f"❌ [Glosas] Error en la búsqueda: {e}")
            self.after(0, lambda: Messagebox.show_error(f"Ocurrió un error durante la búsqueda:\n\n{e}", "Error de Búsqueda"))
        finally:
            # Liberamos el lock para permitir futuras tareas
            self.glosas_thread_lock.release()

    def _mostrar_resultados_glosas(self, resultados):
        """Paso 3: Mostrar los resultados directamente en el panel del dashboard."""
        
        # Limpiamos cualquier resultado anterior del frame
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        if not resultados:
            Messagebox.show_info("No se encontraron glosas para el rango de fechas seleccionado.", "Búsqueda Vacía", parent=self)
            return
        
        self.results_frame.grid_rowconfigure(0, weight=1)
        self.results_frame.grid_columnconfigure(0, weight=1)

        # Creamos la tabla de resultados (Treeview estándar)
        cols = ["radicacion", "fecha_rad", "factura", "valor_factura", "valor_glosado"]
        tree = ttk.Treeview(self.results_frame, columns=cols, show='headings', selectmode='extended')
        
        # Encabezados y columnas
        tree.heading("radicacion", text="N° Radicación")
        tree.heading("fecha_rad", text="Fecha Rad.")
        tree.heading("factura", text="N° Factura")
        tree.heading("valor_factura", text="Valor Factura")
        tree.heading("valor_glosado", text="Valor Glosado")
        tree.column("radicacion", width=200)
        tree.column("fecha_rad", width=100, anchor='center')
        # ... puedes ajustar más anchos si quieres

        # Scrollbar para la tabla
        scrollbar = ttk.Scrollbar(self.results_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        # Añadimos los datos a la tabla
        for res in resultados:
            # Usamos el ID de la glosa como el ID del item (iid) para fácil recuperación
            tree.insert("", "end", iid=res['id'], values=(res['radicacion'], res['fecha_rad'], res['factura'], res['valor_factura'], res['valor_glosado']))

        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Creamos un frame para los botones de descarga
        download_buttons_frame = ttk.Frame(self.results_frame)
        download_buttons_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(10,0))
        
        def on_download(download_type):
            selected_iids = tree.selection() # Obtenemos los IIDs de las filas seleccionadas
            if not selected_iids:
                Messagebox.show_warning("No ha seleccionado ninguna glosa de la tabla.", "Selección Vacía", parent=self)
                return

            items_a_descargar = []
            for iid in selected_iids:
                # Obtenemos los datos asociados a esta fila del Treeview
                item_data = tree.item(iid)
                
                # El 'iid' que establecimos es el ID de la cuenta, ¡perfecto!
                id_cuenta = iid 
                
                # 'item_data['values']' es una tupla con los valores de las columnas.
                # La factura es el 3er elemento (índice 2) de la tupla.
                # Columnas: ["radicacion", "fecha_rad", "factura", "valor_factura", "valor_glosado"]
                # Índices:      0             1            2            3               4
                numero_factura = item_data['values'][2]

                items_a_descargar.append({
                    "id": id_cuenta,
                    "factura": numero_factura, # <-- Aquí está el dato clave que añadimos
                    "detalle": download_type == 'detalle',
                    "glosa": download_type == 'glosa'
                })
            
            # 1. ELIMINAMOS las líneas que destruían la tabla
            # self.results_frame.destroy()  <-- ELIMINADA
            # self.mostrar_panel("bienvenida") <-- ELIMINADA
            # self.mostrar_panel("dashboard")  <-- ELIMINADA

            # 2. (OPCIONAL PERO RECOMENDADO) Deseleccionamos las filas en la tabla
            # para dar feedback visual de que la acción se ha procesado.
            tree.selection_set([]) 
            
            # 3. (OPCIONAL PERO RECOMENDADO) Mostramos un mensaje informativo
            Messagebox.show_info(
                title="Descarga Iniciada",
                message=f"La descarga de {len(items_a_descargar)} item(s) ha comenzado en segundo plano.\nPuede seguir usando la aplicación.\n\nRevise el 'Registro de Proceso' en el panel de Configuración para ver el progreso.",
                parent=self
            )

            self._log_to_console(f"\n[Glosas] Se procederá a descargar '{download_type}' para {len(items_a_descargar)} item(s).")
            threading.Thread(target=self._tarea_descargar_glosas, args=(items_a_descargar, self.fecha_ini_actual, self.fecha_fin_actual), daemon=True).start()

        # Botones de descarga (tu código aquí ya es correcto)
        btn_descargar_detalle = ttk.Button(download_buttons_frame, text="Descargar Detalles Seleccionados", bootstyle="info", command=lambda: on_download('detalle'))
        btn_descargar_detalle.pack(side=LEFT, expand=True, fill=X, padx=(0, 5))
        
        btn_descargar_glosa = ttk.Button(download_buttons_frame, text="Descargar Glosas Seleccionadas", bootstyle="info", command=lambda: on_download('glosa'))
        btn_descargar_glosa.pack(side=LEFT, expand=True, fill=X, padx=(5, 0))


    def _tarea_descargar_glosas(self, items_a_descargar, fecha_ini, fecha_fin):
        """Paso 4: Ejecuta la descarga en el navegador ya existente, con memoria."""
        if not self.glosas_thread_lock.acquire(blocking=False):
            self.after(0, self._log_to_console, "⚠️ [Glosas] Ya hay una tarea en ejecución...")
            self.after(0, lambda: Messagebox.show_warning("Ya hay otra tarea en ejecución.", "Tarea en Progreso"))
            return

        try:
            if not self.driver_glosas:
                raise Exception("No se encontró un navegador activo para la descarga.")

            self.after(0, self._log_to_console, f"--- Iniciando lote de {len(items_a_descargar)} descargas ---")
            
            # Bucle para llamar a la acción de descarga para cada item
            for item in items_a_descargar:
                # Llamamos a la función pasando el último ID recordado
                processed_id = glosas_downloader.descargar_item_especifico(
                    self.driver_glosas, 
                    item,
                    self.download_dir_glosas,
                    self.last_processed_glosa_id # <-- Pasamos la memoria
                )
                
                # Actualizamos la memoria con el resultado de la operación
                self.last_processed_glosa_id = processed_id

            self.after(0, self._log_to_console, "--- Lote de descargas finalizado. ---")
            self.after(0, lambda: Messagebox.show_info("La descarga de los archivos seleccionados ha finalizado.", "Descarga Completada"))

        except Exception as e:
            self.after(0, self._log_to_console, f"❌ [Glosas] Error en la descarga: {e}")
            self.after(0, lambda: Messagebox.show_error(f"Ocurrió un error durante la descarga:\n\n{e}", "Error de Descarga"))
        finally:
            self.glosas_thread_lock.release()
    # ## NUEVA FUNCIÓN para actualizar la UI ##
    def _actualizar_ui_resultados(self, resultados, estado_paginacion):
        """
        Función centralizada para refrescar la tabla y los controles de paginación.
        """
        # 1. Actualizar la tabla
        self._mostrar_resultados_glosas(resultados)

        # 2. Actualizar y mostrar los controles de paginación
        if estado_paginacion:
            self.pagination_frame.grid() # Hacemos visible el panel
            self.lbl_paginacion_info.config(text=estado_paginacion["info_texto"])
            
            self.btn_anterior.config(state="disabled" if estado_paginacion["anterior_deshabilitado"] else "normal")
            self.btn_siguiente.config(state="disabled" if estado_paginacion["siguiente_deshabilitado"] else "normal")

            valor_map = {"-1": "Todos"}
            valor_actual = estado_paginacion["entradas_actuales"]
            self.combo_entradas.set(valor_map.get(valor_actual, valor_actual))
        else:
            self.pagination_frame.grid_remove() # Ocultamos si no hay info

        # --- CORRECCIÓN: Reemplazar yview_moveto ---
        # Forzamos a Tkinter a que procese todos los cambios pendientes
        self.update_idletasks()
        # Hacer scroll al panel de resultados (si es necesario)
        try:
            # Intentamos hacer scroll al frame de resultados
            self.results_frame.tkraise()  # Trae el frame al frente
            # Alternativa: scroll al main_panel
            self.main_panel.focus_set()
        except:
            pass  # Si falla, no es crítico
        # --- FIN DE LA CORRECCIÓN ---
        
    # ## NUEVAS FUNCIONES para manejar los eventos de la GUI ##
    def on_navegar(self, direccion):
        """Se activa al pulsar 'Siguiente' o 'Anterior'."""
        if not self.glosas_thread_lock.acquire(blocking=False):
            Messagebox.show_warning("Ya hay una tarea en ejecución.", "Tarea en Progreso")
            return
            
        self._log_to_console(f"\n[Glosas] Solicitando página '{direccion}'...")
        threading.Thread(target=self._tarea_navegar, args=(direccion,), daemon=True).start()

    def _tarea_navegar(self, direccion):
        try:
            glosas_downloader.navegar_pagina(self.driver_glosas, direccion)
            resultados, estado_paginacion = glosas_downloader.extraer_datos_tabla_actual(self.driver_glosas)
            
            self.resultados_actuales = resultados
            self.after(0, self._actualizar_ui_resultados, resultados, estado_paginacion)
        except Exception as e:
            self.after(0, self._log_to_console, f"❌ Error al navegar: {e}")
        finally:
            self.glosas_thread_lock.release()

    def on_cambiar_entradas(self, event=None):
        """Se activa al cambiar el valor del combobox."""
        if not self.glosas_thread_lock.acquire(blocking=False):
            Messagebox.show_warning("Ya hay una tarea en ejecución.", "Tarea en Progreso")
            return
        
        valor_map = {"Todos": "-1"}
        valor_seleccionado = self.combo_entradas.get()
        valor_real = valor_map.get(valor_seleccionado, valor_seleccionado)
        
        self._log_to_console(f"\n[Glosas] Solicitando mostrar '{valor_seleccionado}' entradas...")
        threading.Thread(target=self._tarea_cambiar_entradas, args=(valor_real,), daemon=True).start()

    def _tarea_cambiar_entradas(self, valor):
        try:
            glosas_downloader.cambiar_numero_entradas(self.driver_glosas, valor)
            resultados, estado_paginacion = glosas_downloader.extraer_datos_tabla_actual(self.driver_glosas)
            
            self.resultados_actuales = resultados
            self.after(0, self._actualizar_ui_resultados, resultados, estado_paginacion)
        except Exception as e:
            self.after(0, self._log_to_console, f"❌ Error al cambiar entradas: {e}")
        finally:
            self.glosas_thread_lock.release()

def main_server_task(base_path):
    """
    Función que contiene la lógica del servidor.
    Ahora lanza la aplicación de bandeja del sistema.
    """
    import tray_app
    # Llamamos a la función principal del script de bandeja
    tray_app.main(base_path)
    sys.exit(0)

def main_client_task(base_path):
    """
    Función que contiene la lógica del cliente.
    Importa y ejecuta la tarea del cliente de sesión.
    """
    # Necesitamos refactorizar un poco session_cliente.py para que esto funcione
    import session_cliente
    session_cliente.run_client_logic(base_path) # Usaremos esta nueva función
    sys.exit(0)

# --- PUNTO DE ENTRADA PRINCIPAL DE LA APLICACIÓN ---

if __name__ == "__main__":
    import multiprocessing
    import sys
    import argparse 
    import tkinter as tk
    from tkinter import messagebox

    multiprocessing.freeze_support()

    # --- NUEVO ENFOQUE: PARSER UNIFICADO Y DESPACHADOR ---
    parser = argparse.ArgumentParser(description="Gestor Coosalud para EVARISIS.")
    
    # Grupo para modos de operación: solo uno puede ser elegido.
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--run-server", action="store_true", help="Ejecuta la lógica del servidor en segundo plano.")
    mode_group.add_argument("--run-client", action="store_true", help="Ejecuta la lógica del cliente en segundo plano.")

    # Argumentos para los modos de operación en segundo plano
    parser.add_argument("--base-path", type=str, help="Ruta base necesaria para los modos de servidor/cliente.")

    # Argumentos para el modo GUI (por defecto si no se elige otro modo)
    parser.add_argument("--lanzado-por-evarisis", action="store_true", help="Bandera de seguridad para el lanzamiento de la GUI.")
    parser.add_argument("--nombre", default="Usuario Invitado", type=str, help="Nombre del usuario.")
    parser.add_argument("--cargo", default="N/A", type=str, help="Cargo del usuario.")
    parser.add_argument("--foto", default="SIN_FOTO", type=str, help="Ruta a la foto del usuario.")
    parser.add_argument("--tema", default="litera", type=str, help="Tema de ttkbootstrap para la GUI.")
    parser.add_argument("--ruta-datos", type=str, help="Ruta a la carpeta de datos central (consistencia).")

    args = parser.parse_args()

    # --- LÓGICA DEL DESPACHADOR ---
    
    if args.run_server:
        if not args.base_path:
            print("ERROR: El modo --run-server requiere el argumento --base-path.")
            sys.exit(1)
        main_server_task(args.base_path)

    elif args.run_client:
        if not args.base_path:
            print("ERROR: El modo --run-client requiere el argumento --base-path.")
            sys.exit(1)
        main_client_task(args.base_path)
    
    else: # Modo GUI por defecto
        if not args.lanzado_por_evarisis:
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(
                "Acceso Denegado", 
                "Esta aplicación es un módulo de EVARISIS y debe ser ejecutada desde el dashboard principal."
            )
            root.destroy()
            sys.exit(1)

        app = CoosaludApp(
            nombre_usuario=args.nombre,
            cargo_usuario=args.cargo,
            foto_path=args.foto,
            tema=args.tema
        )
        app.mainloop()
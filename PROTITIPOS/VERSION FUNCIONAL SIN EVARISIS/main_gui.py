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

# Importamos la lógica que acabamos de separar
try:
    import notion_control_interno
except ImportError:
    notion_control_interno = None

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
    def __init__(self):
        super().__init__(themename="litera")
        self.title("Herramienta Multiusuario Coosalud HUV")
        self.state('zoomed')
        self.base_path = get_base_path()

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
        if self.logos.get("huv"): ttk.Label(header_frame, image=self.logos["huv"], style='primary.TLabel').pack(side=LEFT, padx=(0, 15))
        ttk.Label(header_frame, text="Herramienta Multiusuario Coosalud HUV", style='Header.TLabel', background=self.style.colors.primary).pack(side=LEFT, expand=True)
        if self.logos.get("innovacion_moderno"): ttk.Label(header_frame, image=self.logos["innovacion_moderno"], style='primary.TLabel').pack(side=RIGHT, padx=10)
        if self.logos.get("coosalud"): ttk.Label(header_frame, image=self.logos["coosalud"], style='primary.TLabel').pack(side=RIGHT, padx=10)

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
        self.paneles["dashboard"] = self._crear_panel_proximamente("Dashboard")
        self.paneles["configuracion"] = self._crear_panel_proximamente("Configuración")
        
        console_frame = ttk.Labelframe(self, text="Registro de Proceso", padding=10)
        console_frame.grid(row=2, column=1, sticky="ew", padx=20, pady=(10,20))

        self.console_text = scrolledtext.ScrolledText(console_frame, height=6, state="disabled", wrap=tk.WORD, font=("Consolas", 10))
        self.console_text.pack(fill="both", expand=True)
        
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

    def _crear_panel_proximamente(self, nombre_panel):
        panel = ttk.Frame(self.main_panel)
        panel.grid(row=0, column=0, sticky="nsew")
        content_frame = ttk.Frame(panel)
        content_frame.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(content_frame, text=f"Panel de {nombre_panel}", font=("Segoe UI", 20, "bold")).pack(pady=10)
        ttk.Label(content_frame, text="Esta sección estará disponible próximamente, donde se agregaran nuevas funciones a demanda.", font=("Segoe UI", 14, "italic")).pack(pady=20)
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

    # --- LÓGICA DE PROCESOS ---

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
            # Y hacemos que la etiqueta de estado sea un botón gigante y obvio
            self.lbl_estado_servidor.config(cursor="hand2") # Cambia el cursor a una mano
            self.lbl_estado_servidor.bind("<Button-1>", lambda e: self.iniciar_sesion_cliente())
            self.lbl_estado_servidor.configure(text="✔ Sesión Activa (Clic aquí para usar)") # Texto más claro
        else:
            # Si la sesión está INACTIVA, deshabilitamos todo lo del cliente
            self.btn_iniciar_sesion_cliente.config(state="disabled")
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
            subprocess.Popen(
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
# --- LÓGICA PARA EJECUTAR TAREAS EN SUBPROCESOS ---

def main_server_task(base_path):
    """
    Función que contiene la lógica del servidor.
    Importa y ejecuta la tarea del gestor de sesión.
    """
    from server_logic import selenium_session_manager
    # Llamamos a la función principal del script del servidor, pasándole la ruta
    exit_code = selenium_session_manager.capture_sync_and_refresh_session(base_path)
    sys.exit(exit_code)

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

    # Esta línea es crucial y debe estar aquí
    multiprocessing.freeze_support()

    # --- El "Director de Orquesta" ---
    # Comprueba si el ejecutable fue llamado con una tarea específica
    
    # 1. ¿Nos pidieron que actuemos como el SERVIDOR?
    if '--run-server' in sys.argv:
        try:
            # Extraemos el argumento --base-path que nos pasó la GUI principal
            base_path_arg = next(arg for arg in sys.argv if arg.startswith('--base-path='))
            base_path = base_path_arg.split('=', 1)[1]
            main_server_task(base_path)
        except (StopIteration, IndexError):
            print("ERROR: El modo --run-server requiere el argumento --base-path.")
            sys.exit(1)

    # 2. ¿Nos pidieron que actuemos como el CLIENTE?
    elif '--run-client' in sys.argv:
        try:
            base_path_arg = next(arg for arg in sys.argv if arg.startswith('--base-path='))
            base_path = base_path_arg.split('=', 1)[1]
            main_client_task(base_path)
        except (StopIteration, IndexError):
            print("ERROR: El modo --run-client requiere el argumento --base-path.")
            sys.exit(1)
            
    # 3. Si no hay tareas especiales, ejecutamos la GUI
    else:
        app = CoosaludApp()
        app.mainloop()
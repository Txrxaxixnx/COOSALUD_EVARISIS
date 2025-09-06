# main_gui.py:
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import os
import sys
import subprocess
import threading
from datetime import datetime, timedelta
import requests
import time
import pandas as pd
import glob
import re # Importamos re para expresiones regulares
import shutil # <--- AÑADE ESTA LÍNEA SI NO ESTÁ

from ttkbootstrap.dialogs import Messagebox
import json

# Importamos la lógica que acabamos de separar
try:
    import notion_control_interno
    import glosas_downloader
    from calendario import CalendarioInteligente
except ImportError as e:
    print(f"Error de importación: {e}")
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
        base_dir = os.path.dirname(sys.executable)
        return os.path.join(base_dir, '_internal')
    else:
        return os.path.dirname(os.path.abspath(__file__))

class CoosaludApp(ttk.Window):
    def __init__(self, nombre_usuario, cargo_usuario, foto_path, tema):
        super().__init__(themename=tema)

        self.server_process = None

        self.driver_glosas = None
        self.download_dir_glosas = None
        self.glosas_thread_lock = threading.Lock()
        self.last_processed_glosa_id = None
        self.resultados_actuales = []

        self.current_user = {"nombre": nombre_usuario, "cargo": cargo_usuario}
        self.foto_usuario = self._cargar_foto_usuario(foto_path)

        self.title("EVARISIS GESTOR COOSALUD")
        self.state('zoomed')
        self.base_path = get_base_path()

        try:
            icon_path = os.path.join(self.base_path, "gestorcoosalud.ico")
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Advertencia: No se pudo cargar el ícono de la aplicación: {e}")

        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(os.path.join(self.base_path, 'config.ini'))
            
            self.NOTION_API_KEY = config['Notion']['ApiKey']
            self.NOTION_SESSION_PAGE_ID = config['Notion']['NOTION_SESSION_PAGE_ID']
            
            self.chrome_driver_path = os.path.join(self.base_path, "chrome-win64", "chromedriver.exe")
            self.chrome_binary_path = os.path.join(self.base_path, "chrome-win64", "chrome.exe")

        except (KeyError, configparser.Error) as e:
            messagebox.showerror("Error de Configuración", f"No se pudo leer 'config.ini' o falta una clave.\nDetalles: {e}")
            self.destroy()
            return
        
        self.image_path = os.path.join(self.base_path, "imagenes")
        self.COLOR_AZUL_HUV = "#005A9C"
        self.logos = self._cargar_logos()
        self._configurar_estilos()
        self._crear_widgets()

        self.after(500, self.comprobar_estado_servidor)
        self.after(1000, self.ejecutar_control_interno)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ... (Las funciones _cargar_logos, _cargar_foto_usuario, _configurar_estilos, _crear_cabecera, _crear_menu_lateral no cambian)
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
        
        if self.foto_usuario:
            ttk.Label(header_frame, image=self.foto_usuario, style='primary.TLabel').pack(side=RIGHT, padx=10)

        profile_info_frame = ttk.Frame(header_frame, style='primary.TFrame')
        profile_info_frame.pack(side=RIGHT, padx=(0, 10))

        ttk.Label(profile_info_frame, text=self.current_user["nombre"], font=('Segoe UI', 12, "bold"), anchor=E, style='primary.TLabel').pack(fill=X)
        ttk.Label(profile_info_frame, text=self.current_user["cargo"], font=('Segoe UI', 9), anchor=E, style='secondary.TLabel').pack(fill=X)

    def _crear_menu_lateral(self):
        sidebar_frame = ttk.Frame(self, padding=20, width=250)
        sidebar_frame.grid(row=1, column=0, sticky="ns")
        sidebar_frame.grid_propagate(False)

        self.lbl_estado_servidor = ttk.Label(sidebar_frame, text=" ⚪ Comprobando...", bootstyle="secondary")
        self.lbl_estado_servidor.configure(style='Status.TLabel')
        self.lbl_estado_servidor.pack(fill=X, pady=(0, 30))

        self.btn_iniciar_sesion_cliente = ttk.Button(sidebar_frame, text="  Iniciar Sesión Cliente", style='Sidebar.TButton', command=self.iniciar_sesion_cliente)
        self.btn_iniciar_sesion_cliente.pack(fill=X, pady=5, ipady=10)
        
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
        panel = ttk.Frame(self.main_panel, padding=(0, 0, 0, 10))
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        content_frame = ttk.Frame(panel)
        content_frame.grid(row=0, column=0, sticky="new", pady=(0, 20))
        ttk.Label(content_frame, text="Panel de Configuración", font=("Segoe UI", 20, "bold")).pack(pady=10)
        ttk.Label(content_frame, text="Aquí se mostrará el registro de procesos y futuras opciones.", font=("Segoe UI", 12)).pack()
        
        console_frame = ttk.Labelframe(panel, text="Registro de Proceso", padding=10)
        console_frame.grid(row=1, column=0, sticky="nsew")

        self.console_text = scrolledtext.ScrolledText(console_frame, height=8, state="disabled", wrap=tk.WORD, font=("Consolas", 10))
        self.console_text.pack(fill="both", expand=True)
        
        return panel

    def _crear_panel_dashboard(self):
        panel = ttk.Frame(self.main_panel)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_rowconfigure(3, weight=1) # Fila para la tabla de resultados
        panel.grid_columnconfigure(0, weight=1)

        ttk.Label(panel, text="Dashboard de Tareas Automatizadas", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky='w')
        
        self.btn_glosas = ttk.Button(panel, text="Buscar Informes de Glosas", command=self.iniciar_proceso_glosas, bootstyle="success", state="disabled")
        self.btn_glosas.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

        # ## CAMBIO: Se eliminó el botón de automatización completa de aquí ##
        # self.btn_automatizar_glosas = ttk.Button(...) # <-- LÍNEA ELIMINADA

        self.results_frame = ttk.Frame(panel, padding=(0, 20, 0, 0))
        self.results_frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
        
        # ## SECCIÓN DE PAGINACIÓN Y AUTOMATIZACIÓN ##
        self.pagination_frame = ttk.Frame(panel, padding=(0, 10, 0, 0))
        self.pagination_frame.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.pagination_frame.grid_columnconfigure(3, weight=1) # Columna del medio se expande

        # Controles de paginación
        self.combo_entradas = ttk.Combobox(self.pagination_frame, values=["20", "50", "100", "500", "Todos"], state="readonly", width=8)
        self.combo_entradas.bind("<<ComboboxSelected>>", self.on_cambiar_entradas)
        self.combo_entradas.pack(side=LEFT, padx=5)

        self.btn_anterior = ttk.Button(self.pagination_frame, text="Anterior", command=lambda: self.on_navegar("anterior"))
        self.btn_anterior.pack(side=LEFT, padx=5)
        
        self.lbl_paginacion_info = ttk.Label(self.pagination_frame, text="", anchor="center")
        self.lbl_paginacion_info.pack(side=LEFT, padx=10, expand=True, fill=X)

        # ## NUEVO: Botón de automatización integrado en la barra de resultados ##
        self.btn_iniciar_automatizacion = ttk.Button(
            self.pagination_frame, 
            text="🤖 Iniciar Automatización", 
            command=self.iniciar_proceso_automatizacion_integrada, # Llama a la nueva función
            bootstyle="warning"
        )
        self.btn_iniciar_automatizacion.pack(side=RIGHT, padx=5)
        
        self.btn_siguiente = ttk.Button(self.pagination_frame, text="Siguiente", command=lambda: self.on_navegar("siguiente"))
        self.btn_siguiente.pack(side=RIGHT, padx=5)

        self.pagination_frame.grid_remove() # Ocultamos todo el panel al inicio
        
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

    def on_closing(self):
        self._log_to_console("Cerrando aplicación...")
        if self.server_process and self.server_process.poll() is None:
            self._log_to_console("[GUI] Cerrando el proceso del servidor en segundo plano...")
            self.server_process.terminate()
            self.server_process.wait()
            self._log_to_console("[GUI] Proceso del servidor cerrado.")
        
        if self.driver_glosas:
            self._log_to_console("[Glosas] Cerrando navegador de automatización...")
            try:
                self.driver_glosas.quit()
            except Exception as e:
                self._log_to_console(f"Error al cerrar el driver de glosas: {e}")
        self.destroy()

    # ... (Las funciones de comprobación de estado, control interno, iniciar servidor/cliente no cambian)
    def comprobar_estado_servidor(self):
        threading.Thread(target=self._tarea_comprobar_estado, daemon=True).start()

    def _tarea_comprobar_estado(self):
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
        self.lbl_estado_servidor.configure(text=texto, bootstyle=bootstyle)
        
        estado_servidor = "normal" if habilitar_boton_servidor else "disabled"
        self.btn_iniciar_servidor.config(state=estado_servidor)
        
        if not habilitar_boton_servidor:
            self.btn_iniciar_sesion_cliente.config(state="normal")
            self.btn_glosas.config(state="normal")
            self.lbl_estado_servidor.config(cursor="hand2")
            self.lbl_estado_servidor.bind("<Button-1>", lambda e: self.iniciar_sesion_cliente())
            self.lbl_estado_servidor.configure(text="✔ Sesión Activa (Clic aquí para usar)")
        else:
            self.btn_iniciar_sesion_cliente.config(state="disabled")
            self.btn_glosas.config(state="disabled")
            self.lbl_estado_servidor.config(cursor="")
            self.lbl_estado_servidor.unbind("<Button-1>")

    def ejecutar_control_interno(self):
        if not notion_control_interno:
            self._log_to_console("❌ ERROR: El módulo 'notion_control_interno.py' no se encontró.")
            messagebox.showerror("Error Crítico", "No se encontró el módulo de control interno.")
            return
        self._log_to_console("[1/2] Iniciando control interno...")
        threading.Thread(target=self._tarea_control_interno, daemon=True).start()

    def _tarea_control_interno(self):
        exito = notion_control_interno.registrar_uso(lambda msg: self.after(0, self._log_to_console, msg),
                                                     self.base_path)
        self.after(0, self._finalizar_control_interno, exito)

    def _finalizar_control_interno(self, exito):
        if exito:
            self._log_to_console("✅ Control interno concretado.")
        else:
            self._log_to_console("❌ La fase de control interno falló.")
            messagebox.showerror("Error de Control", "No se pudo registrar el uso de la herramienta.")

    def iniciar_servidor(self):
        self.btn_iniciar_servidor.config(state="disabled")
        self._log_to_console("\n[Anfitrión] Iniciando secuencia del servidor...")
        threading.Thread(target=self._tarea_lanzar_servidor, daemon=True).start()

    def _tarea_lanzar_servidor(self):
        try:
            python_exe = sys.executable
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"

            command = [python_exe]
            if not getattr(sys, 'frozen', False):
                command.append(sys.argv[0])
            
            command.extend(["--run-server", f"--base-path={self.base_path}"])
            
            flag_file_path = os.path.join(self.base_path, '.sync_success.flag')

            if os.path.exists(flag_file_path):
                os.remove(flag_file_path)

            self.after(0, self._log_to_console, "[Anfitrión] Lanzando el gestor de sesión del servidor...")
            self.server_process = subprocess.Popen(
                command,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW 
            )
            
            self.after(0, self._log_to_console, "[Anfitrión] ...esperando señal de sincronización exitosa del servidor...")
            timeout = 45 
            start_time = time.time()
            sync_success = False
            while time.time() - start_time < timeout:
                if os.path.exists(flag_file_path):
                    self.after(0, self._log_to_console, "✅ [Anfitrión] ¡Señal recibida! La sincronización inicial fue un éxito.")
                    os.remove(flag_file_path)
                    sync_success = True
                    break
                time.sleep(0.5)

            if sync_success:
                self.after(0, self._log_to_console, "[Anfitrión] Forzando actualización de estado de la UI...")
                self.comprobar_estado_servidor()
            else:
                self.after(0, self._log_to_console, "❌ [Anfitrión] Error: El servidor no envió la señal de éxito a tiempo.")
                self.after(0, lambda: self.btn_iniciar_servidor.config(state="normal"))

        except Exception as e:
            error_msg = f"❌ [Anfitrión] Error inesperado al lanzar la secuencia: {e}"
            self.after(0, self._log_to_console, error_msg)
            self.after(0, lambda: self.btn_iniciar_servidor.config(state="normal"))

    def iniciar_sesion_cliente(self):
        self._log_to_console("\n[Cliente] Solicitando inicio de sesión...")
        threading.Thread(target=self._tarea_iniciar_sesion_cliente, daemon=True).start()

    def _tarea_iniciar_sesion_cliente(self):
        try:
            python_exe = sys.executable
            command = [python_exe]
            if not getattr(sys, 'frozen', False):
                command.append(sys.argv[0])
            
            command.extend(["--run-client", f"--base-path={self.base_path}"])

            subprocess.Popen(
                command, 
                creationflags=subprocess.CREATE_NO_WINDOW  
            )
            self.after(0, self._log_to_console, "✅ [Cliente] Orden de inicio de sesión enviada.")
        except Exception as e:
            error_msg = f"❌ [Cliente] Error al lanzar el proceso del cliente: {e}"
            self.after(0, self._log_to_console, error_msg)
    
    # ... (El resto de las funciones de la GUI y la lógica de Glosas se definen a continuación) ...
    # ... (Las funciones de búsqueda, descarga, paginación, etc., permanecen iguales pero ahora se añade la automatización)

    def _iniciar_navegador_glosas_si_no_existe(self):
        if self.driver_glosas:
            self.after(0, self._log_to_console, "[Glosas] Reutilizando navegador ya existente.")
            return True

        try:
            self.after(0, self._log_to_console, "[Glosas] Iniciando nuevo navegador de automatización...")
            cookie = glosas_downloader.get_session_cookie(self.base_path)
            
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
            self.driver_glosas = None
            return False

    def iniciar_proceso_glosas(self):
        if not CalendarioInteligente:
            messagebox.showerror("Error de Módulo", "El módulo 'calendario.py' no se pudo cargar.")
            return

        self._log_to_console("\n[Glosas] Solicitando fecha de inicio...")
        fecha_ini_obj = CalendarioInteligente.seleccionar_fecha(parent=self, titulo="Seleccione la FECHA DE INICIO", codigo_pais_festivos='CO', locale='es_CO')
        
        if not fecha_ini_obj:
            self._log_to_console("[Glosas] Proceso cancelado por el usuario (fecha de inicio).")
            return
        
        fecha_ini_str = fecha_ini_obj.strftime("%Y-%m-%d")
        self._log_to_console(f"[Glosas] Fecha de inicio seleccionada: {fecha_ini_str}")

        self._log_to_console("[Glosas] Solicitando fecha de fin...")
        fecha_fin_obj = CalendarioInteligente.seleccionar_fecha(parent=self, titulo="Seleccione la FECHA DE FIN", fecha_inicial=fecha_ini_obj, codigo_pais_festivos='CO', locale='es_CO')
        
        if not fecha_fin_obj:
            self._log_to_console("[Glosas] Proceso cancelado por el usuario (fecha de fin).")
            return

        if fecha_fin_obj < fecha_ini_obj:
            self._log_to_console("[Glosas] Error: La fecha de fin es anterior a la de inicio.")
            Messagebox.show_error("La fecha de fin no puede ser anterior a la fecha de inicio.", "Error de Fechas")
            return
            
        fecha_fin_str = fecha_fin_obj.strftime("%Y-%m-%d")
        self.fecha_ini_actual = fecha_ini_str
        self.fecha_fin_actual = fecha_fin_str

        if not self.glosas_thread_lock.acquire(blocking=False):
            self._log_to_console("⚠️ [Glosas] Ya hay una tarea en ejecución. Por favor, espere.")
            Messagebox.show_warning("Ya hay una tarea de glosas en ejecución. Por favor, espere a que termine.", "Tarea en Progreso")
            return

        self._log_to_console(f"[Glosas] Buscando registros entre {fecha_ini_str} y {fecha_fin_str}...")
        hilo_busqueda = threading.Thread(target=self._tarea_buscar_glosas, args=(fecha_ini_str, fecha_fin_str), daemon=True)
        hilo_busqueda.start()

    def _tarea_buscar_glosas(self, fecha_ini, fecha_fin):
        try:
            if not self._iniciar_navegador_glosas_si_no_existe():
                return
            
            self.after(0, self._log_to_console, "[Glosas] Ejecutando búsqueda inicial...")
            
            resultados, estado_paginacion = glosas_downloader.fase_buscar(self.driver_glosas, fecha_ini, fecha_fin, self.base_path)
            
            self.after(0, self._log_to_console, f"✅ [Glosas] Búsqueda completada. {estado_paginacion['info_texto']}.")
            
            self.resultados_actuales = resultados
            self.after(0, self._actualizar_ui_resultados, resultados, estado_paginacion)

        except Exception as e:
            self.after(0, self._log_to_console, f"❌ [Glosas] Error en la búsqueda: {e}")
            self.after(0, lambda: Messagebox.show_error(f"Ocurrió un error durante la búsqueda:\n\n{e}", "Error de Búsqueda"))
        finally:
            self.glosas_thread_lock.release()

    def _mostrar_resultados_glosas(self, resultados):
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        if not resultados:
            Messagebox.show_info("No se encontraron glosas para el rango de fechas seleccionado.", "Búsqueda Vacía", parent=self)
            return
        
        self.results_frame.grid_rowconfigure(0, weight=1)
        self.results_frame.grid_columnconfigure(0, weight=1)

        cols = ["radicacion", "fecha_rad", "factura", "valor_factura", "valor_glosado"]
        tree = ttk.Treeview(self.results_frame, columns=cols, show='headings', selectmode='extended')
        
        tree.heading("radicacion", text="N° Radicación")
        tree.heading("fecha_rad", text="Fecha Rad.")
        tree.heading("factura", text="N° Factura")
        tree.heading("valor_factura", text="Valor Factura")
        tree.heading("valor_glosado", text="Valor Glosado")
        tree.column("radicacion", width=200)
        tree.column("fecha_rad", width=100, anchor='center')

        scrollbar = ttk.Scrollbar(self.results_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        for res in resultados:
            tree.insert("", "end", iid=res['id'], values=(res['radicacion'], res['fecha_rad'], res['factura'], res['valor_factura'], res['valor_glosado']))

        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        download_buttons_frame = ttk.Frame(self.results_frame)
        download_buttons_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(10,0))
        
        def on_download(download_type):
            selected_iids = tree.selection()
            if not selected_iids:
                Messagebox.show_warning("No ha seleccionado ninguna glosa de la tabla.", "Selección Vacía", parent=self)
                return

            items_a_descargar = []
            for iid in selected_iids:
                item_data = tree.item(iid)
                id_cuenta = iid 
                numero_factura = item_data['values'][2]

                items_a_descargar.append({
                    "id": id_cuenta,
                    "factura": numero_factura,
                    "detalle": download_type == 'detalle',
                    "glosa": download_type == 'glosa'
                })
            
            tree.selection_set([]) 
            
            Messagebox.show_info(
                title="Descarga Iniciada",
                message=f"La descarga de {len(items_a_descargar)} item(s) ha comenzado en segundo plano.\nPuede seguir usando la aplicación.\n\nRevise el 'Registro de Proceso' en el panel de Configuración para ver el progreso.",
                parent=self
            )

            self._log_to_console(f"\n[Glosas] Se procederá a descargar '{download_type}' para {len(items_a_descargar)} item(s).")
            threading.Thread(target=self._tarea_descargar_glosas, args=(items_a_descargar,), daemon=True).start()

        btn_descargar_detalle = ttk.Button(download_buttons_frame, text="Descargar Detalles Seleccionados", bootstyle="info", command=lambda: on_download('detalle'))
        btn_descargar_detalle.pack(side=LEFT, expand=True, fill=X, padx=(0, 5))
        
        btn_descargar_glosa = ttk.Button(download_buttons_frame, text="Descargar Glosas Seleccionadas", bootstyle="info", command=lambda: on_download('glosa'))
        btn_descargar_glosa.pack(side=LEFT, expand=True, fill=X, padx=(5, 0))

    def _tarea_descargar_glosas(self, items_a_descargar):
        if not self.glosas_thread_lock.acquire(blocking=False):
            self.after(0, self._log_to_console, "⚠️ [Glosas] Ya hay una tarea en ejecución...")
            self.after(0, lambda: Messagebox.show_warning("Ya hay otra tarea en ejecución.", "Tarea en Progreso"))
            return

        try:
            if not self.driver_glosas:
                raise Exception("No se encontró un navegador activo para la descarga.")

            self.after(0, self._log_to_console, f"--- Iniciando lote de {len(items_a_descargar)} descargas ---")
            
            for item in items_a_descargar:
                processed_id = glosas_downloader.descargar_item_especifico(
                    self.driver_glosas, 
                    item,
                    self.download_dir_glosas,
                    self.last_processed_glosa_id
                )
                
                self.last_processed_glosa_id = processed_id

            self.after(0, self._log_to_console, "--- Lote de descargas finalizado. ---")
            self.after(0, lambda: Messagebox.show_info("La descarga de los archivos seleccionados ha finalizado.", "Descarga Completada"))

        except Exception as e:
            self.after(0, self._log_to_console, f"❌ [Glosas] Error en la descarga: {e}")
            self.after(0, lambda: Messagebox.show_error(f"Ocurrió un error durante la descarga:\n\n{e}", "Error de Descarga"))
        finally:
            self.glosas_thread_lock.release()

    def _actualizar_ui_resultados(self, resultados, estado_paginacion):
        self._mostrar_resultados_glosas(resultados)

        if estado_paginacion:
            self.pagination_frame.grid()
            self.lbl_paginacion_info.config(text=estado_paginacion["info_texto"])
            
            self.btn_anterior.config(state="disabled" if estado_paginacion["anterior_deshabilitado"] else "normal")
            self.btn_siguiente.config(state="disabled" if estado_paginacion["siguiente_deshabilitado"] else "normal")

            valor_map = {"-1": "Todos"}
            valor_actual = estado_paginacion["entradas_actuales"]
            self.combo_entradas.set(valor_map.get(valor_actual, valor_actual))
        else:
            self.pagination_frame.grid_remove()

        self.update_idletasks()
        try:
            self.results_frame.tkraise()
            self.main_panel.focus_set()
        except:
            pass
        
    def on_navegar(self, direccion):
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

    def _consolidar_archivos_reporte(self, ruta_carpeta_reporte, fecha_ini, fecha_fin):
            """
            Encuentra todos los archivos Excel en la carpeta de reporte, los une
            en un único archivo 'Consolidado de Glosas.xlsx' con un encabezado personalizado.
            """
            try:
                self.after(0, self._log_to_console, f"[Consolidador] Buscando archivos Excel en '{os.path.basename(ruta_carpeta_reporte)}'...")
                
                # Buscar todos los archivos .xls y .xlsx en la carpeta
                archivos_excel = glob.glob(os.path.join(ruta_carpeta_reporte, "*.xls*"))

                if not archivos_excel:
                    self.after(0, self._log_to_console, "[Consolidador] No se encontraron archivos Excel para consolidar.")
                    return None

                self.after(0, self._log_to_console, f"[Consolidador] Se encontraron {len(archivos_excel)} archivos para procesar.")
                
                lista_de_dataframes = []
                for archivo in archivos_excel:
                    try:
                        # Leemos el excel, OMITIENDO LA PRIMERA FILA que es el título.
                        df_individual = pd.read_excel(archivo, skiprows=1)
                        if not df_individual.empty:
                            lista_de_dataframes.append(df_individual)
                    except Exception as e:
                        self.after(0, self._log_to_console, f"⚠️  [Consolidador] No se pudo leer el archivo '{os.path.basename(archivo)}': {e}")

                if not lista_de_dataframes:
                    self.after(0, self._log_to_console, "❌ [Consolidador] Ningún archivo contenía datos válidos para consolidar.")
                    return None
                
                # Unir todos los dataframes en uno solo
                df_consolidado = pd.concat(lista_de_dataframes, ignore_index=True)
                self.after(0, self._log_to_console, f"[Consolidador] Se consolidaron un total de {len(df_consolidado)} filas.")

                # --- Creación del archivo Excel con encabezado personalizado ---
                
                # 1. Preparar el contenido del encabezado personalizado
                encabezado_personalizado = pd.DataFrame({
                    'A': [f"Reporte de Glosas Recopilado"],
                    'B': [f"Período: {fecha_ini} a {fecha_fin}"],
                    'C': [f"Total Archivos Procesados: {len(archivos_excel)}"]
                })

                # 2. Definir el nombre y la ruta del archivo final
                nombre_archivo_final = "Consolidado de Glosas.xlsx"
                ruta_archivo_final = os.path.join(ruta_carpeta_reporte, nombre_archivo_final)

                # 3. Usar ExcelWriter para escribir en el archivo por partes
                with pd.ExcelWriter(ruta_archivo_final, engine='openpyxl') as writer:
                    # Escribir el encabezado personalizado sin su propio header
                    encabezado_personalizado.to_excel(writer, sheet_name='Consolidado', startrow=0, index=False, header=False)
                    
                    # Escribir el dataframe consolidado, dejando espacio para el encabezado
                    # startrow=3 deja una fila en blanco para mejor legibilidad
                    df_consolidado.to_excel(writer, sheet_name='Consolidado', startrow=3, index=False)
                
                self.after(0, self._log_to_console, f"✅ [Consolidador] Archivo final '{nombre_archivo_final}' creado exitosamente.")
                return nombre_archivo_final

            except Exception as e:
                self.after(0, self._log_to_console, f"❌ [Consolidador] Error fatal durante la consolidación: {e}")
                return None

    def _organizar_archivos_reporte(self, files_antes_de_descarga):
            """
            Crea una carpeta con la fecha y mueve los archivos.
            Ahora devuelve la RUTA COMPLETA y el NOMBRE de la carpeta.
            """
            try:
                self.after(0, self._log_to_console, "[Organizador] Identificando archivos nuevos...")
                
                files_despues_de_descarga = set(os.listdir(self.download_dir_glosas))
                archivos_nuevos = files_despues_de_descarga - files_antes_de_descarga

                if not archivos_nuevos:
                    self.after(0, self._log_to_console, "[Organizador] No se encontraron nuevos archivos para organizar.")
                    return None, None

                fecha_actual_str = datetime.now().strftime("%Y-%m-%d")
                nombre_carpeta_reporte = f"Reporte de Glosas {fecha_actual_str}"
                ruta_carpeta_reporte = os.path.join(self.download_dir_glosas, nombre_carpeta_reporte)

                os.makedirs(ruta_carpeta_reporte, exist_ok=True)
                self.after(0, self._log_to_console, f"[Organizador] Carpeta de reporte creada: '{nombre_carpeta_reporte}'")

                for nombre_archivo in archivos_nuevos:
                    ruta_origen = os.path.join(self.download_dir_glosas, nombre_archivo)
                    ruta_destino = os.path.join(ruta_carpeta_reporte, nombre_archivo)
                    shutil.move(ruta_origen, ruta_destino)
                
                self.after(0, self._log_to_console, f"[Organizador] Se movieron {len(archivos_nuevos)} archivos a la nueva carpeta.")
                
                # Devolver la ruta completa Y el nombre
                return ruta_carpeta_reporte, nombre_carpeta_reporte

            except Exception as e:
                self.after(0, self._log_to_console, f"❌ [Organizador] Error al mover archivos: {e}")
                return None, None

    # ########################################################################## #
    # ## INICIO DE LA NUEVA LÓGICA DE AUTOMATIZACIÓN (VERSIÓN SIMPLIFICADA)     ##
    # ########################################################################## #

    def iniciar_proceso_automatizacion_integrada(self):
        """
        Se activa con el botón 'Iniciar Automatización'.
        Pregunta al usuario cuántos de los ITEMS VISIBLES en la tabla desea descargar en cadena.
        """
        # 1. Bloquear para evitar acciones duplicadas
        if not self.glosas_thread_lock.acquire(blocking=False):
            Messagebox.show_warning("Ya hay una tarea de descarga en ejecución.", "Tarea en Progreso")
            return

        # 2. Verificar que tengamos resultados en la tabla para procesar
        if not self.resultados_actuales:
            Messagebox.show_warning("No hay resultados en la tabla para automatizar.", "Tabla Vacía", parent=self)
            self.glosas_thread_lock.release() # Liberamos el bloqueo si no hay nada que hacer
            return

        total_en_tabla = len(self.resultados_actuales)
        items_a_procesar = []

        try:
            # 3. Preguntar al usuario la cantidad
            cantidad_str = simpledialog.askstring(
                "Automatizar Descarga Secuencial",
                f"La tabla actual muestra {total_en_tabla} glosas.\n\n"
                f"¿Cuántas desea descargar en secuencia?\n"
                f"Escriba un número (1 a {total_en_tabla}) o la palabra 'todas'.",
                parent=self
            )

            # 4. Si el usuario cancela, liberamos el bloqueo y terminamos
            if not cantidad_str:
                self._log_to_console("[Automatización] Proceso cancelado por el usuario.")
                self.glosas_thread_lock.release()
                return

            # 5. Procesar la respuesta del usuario
            cantidad_str = cantidad_str.strip().lower()
            if cantidad_str == "todas":
                cantidad_a_descargar = total_en_tabla
            else:
                try:
                    cantidad_a_descargar = int(cantidad_str)
                    if not (0 < cantidad_a_descargar <= total_en_tabla):
                        Messagebox.showerror("Cantidad Inválida", f"Por favor, ingrese un número entre 1 y {total_en_tabla}.", parent=self)
                        self.glosas_thread_lock.release()
                        return
                except ValueError:
                    Messagebox.showerror("Entrada Inválida", "Por favor, ingrese un número válido o la palabra 'todas'.", parent=self)
                    self.glosas_thread_lock.release()
                    return

            # 6. Preparar la lista de ítems a descargar
            # Tomamos los primeros N resultados de la lista que ya tenemos en memoria
            resultados_para_descargar = self.resultados_actuales[:cantidad_a_descargar]
            
            for item_data in resultados_para_descargar:
                items_a_procesar.append({
                    "id": item_data['id'],
                    "factura": item_data['factura'],
                    "detalle": False,  # No descargamos detalle
                    "glosa": True      # Solo descargamos la glosa
                })

            # 7. Si todo es correcto, lanzamos la tarea en segundo plano
            # IMPORTANTE: No liberamos el bloqueo aquí. La tarea de fondo lo hará cuando termine.
            self._log_to_console(f"\n🤖 [Automatización] Iniciando descarga en cadena de {len(items_a_procesar)} glosas...")
            threading.Thread(
                target=self._tarea_ejecutar_descarga_en_cadena,
                args=(items_a_procesar,),
                daemon=True
            ).start()

        except Exception as e:
            # Si ocurre cualquier error inesperado durante la preparación, lo notificamos y liberamos el bloqueo
            self._log_to_console(f"❌ Error al preparar la automatización: {e}")
            self.glosas_thread_lock.release()

    def _tarea_ejecutar_descarga_en_cadena(self, items_a_descargar):
            """
            Esta es la tarea que se ejecuta en segundo plano. Descarga, organiza
            y finalmente CONSOLIDA los archivos. (VERSIÓN FINAL)
            """
            try:
                if not self.driver_glosas:
                    raise Exception("El navegador de automatización no está iniciado.")
                
                files_antes = set(os.listdir(self.download_dir_glosas))
                
                total = len(items_a_descargar)
                self.after(0, self._log_to_console, f"--- Procesando {total} glosas una por una ---")

                for i, item in enumerate(items_a_descargar):
                    self.after(0, self._log_to_console, f"[{i+1}/{total}] Procesando factura {item['factura']}...")
                    
                    processed_id = glosas_downloader.descargar_item_especifico(
                        self.driver_glosas, item, self.download_dir_glosas, self.last_processed_glosa_id
                    )
                    self.last_processed_glosa_id = processed_id

                self.after(0, self._log_to_console, "✅ --- Descarga en cadena finalizada. ---")

                # Llamar a la función para organizar los archivos en su carpeta
                ruta_carpeta_reporte, nombre_carpeta_reporte = self._organizar_archivos_reporte(files_antes)

                # Si la organización fue exitosa, proceder a consolidar
                if ruta_carpeta_reporte:
                    nombre_archivo_consolidado = self._consolidar_archivos_reporte(
                        ruta_carpeta_reporte, 
                        self.fecha_ini_actual, 
                        self.fecha_fin_actual
                    )
                    
                    # Preparar el mensaje final para el usuario
                    mensaje_final = (
                        f"Se han procesado y descargado {total} glosas exitosamente.\n\n"
                        f"📁 Se guardaron en la carpeta:\n'{nombre_carpeta_reporte}'\n\n"
                    )
                    if nombre_archivo_consolidado:
                        mensaje_final += f"📋 Se generó el archivo consolidado:\n'{nombre_archivo_consolidado}'"
                    else:
                        mensaje_final += "No se pudo generar el archivo consolidado."

                else:
                    mensaje_final = f"Se procesaron {total} glosas, pero no se encontraron nuevos archivos para organizar."

                self.after(0, lambda: Messagebox.show_info("Proceso Finalizado", mensaje_final, parent=self))

            except Exception as e:
                self.after(0, self._log_to_console, f"❌ [Automatización] Error durante la descarga en cadena: {e}")
                self.after(0, lambda: Messagebox.showerror("Error en Automatización", f"Ocurrió un error durante el proceso:\n\n{e}", parent=self))
                
            finally:
                self.glosas_thread_lock.release()
                self._log_to_console("[Automatización] Proceso terminado y bloqueo liberado.")

    # ########################################################################## #
    # ## FIN DE LA NUEVA LÓGICA DE AUTOMATIZACIÓN (VERSIÓN SIMPLIFICADA)        ##
    # ########################################################################## #

    def _reconfigurar_directorio_descarga(self, nuevo_directorio):
        """Reconfigura el directorio de descarga del navegador existente."""
        try:
            self.driver_glosas.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': nuevo_directorio
            })
            self.after(0, self._log_to_console, f"[Config] Directorio de descarga cambiado a: {os.path.basename(nuevo_directorio)}")
        except Exception as e:
            self.after(0, self._log_to_console, f"[Config] Advertencia: No se pudo cambiar directorio de descarga: {e}")

    def _consolidar_archivos_excel_desde_carpeta(self, ruta_carpeta, fecha_ini, fecha_fin):
        """Consolida todos los archivos Excel de una carpeta específica."""
        try:
            pattern = os.path.join(ruta_carpeta, "*.xls*") # Busca .xls y .xlsx
            archivos_excel = glob.glob(pattern)
            
            self._log_to_console(f"[Consolidación] Archivos encontrados: {len(archivos_excel)}")
            
            if not archivos_excel:
                raise Exception("No se encontraron archivos Excel para consolidar.")
            
            datos_consolidados = []
            for archivo in archivos_excel:
                try:
                    df = pd.read_excel(archivo, engine='openpyxl' if archivo.endswith('.xlsx') else 'xlrd')
                    if not df.empty:
                        datos_consolidados.append(df)
                except Exception as e:
                    self._log_to_console(f"⚠️ [Consolidación] No se pudo leer el archivo {os.path.basename(archivo)}: {e}")
            
            if not datos_consolidados:
                raise Exception("Ningún archivo Excel pudo ser procesado.")
            
            df_consolidado = pd.concat(datos_consolidados, ignore_index=True)
            
            nombre_archivo = f"CONSOLIDADO_GLOSAS_{fecha_ini}_a_{fecha_fin}.xlsx"
            ruta_consolidado = os.path.join(ruta_carpeta, nombre_archivo)
            
            df_consolidado.to_excel(ruta_consolidado, index=False, engine='openpyxl')
            
            self._log_to_console(f"✅ [Consolidación] Archivo consolidado creado con {len(df_consolidado):,} filas.")
            return ruta_consolidado
            
        except Exception as e:
            self.after(0, self._log_to_console, f"❌ [Consolidación] {e}")
            raise e

    # ########################################################################## #
    # ## FIN DE LA NUEVA LÓGICA DE AUTOMATIZACIÓN INTEGRADA                     ##
    # ########################################################################## #

# --- PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":
    # ... (El bloque __main__ no necesita cambios, su lógica de despachador es correcta)
    import multiprocessing
    import sys
    import argparse
    import tkinter as tk
    from tkinter import messagebox

    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Gestor Coosalud para EVARISIS.")
    
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--run-server", action="store_true", help="Ejecuta la lógica del servidor en segundo plano.")
    mode_group.add_argument("--run-client", action="store_true", help="Ejecuta la lógica del cliente en segundo plano.")

    parser.add_argument("--base-path", type=str, help="Ruta base necesaria para los modos de servidor/cliente.")

    parser.add_argument("--lanzado-por-evarisis", action="store_true", help="Bandera de seguridad para el lanzamiento de la GUI.")
    parser.add_argument("--nombre", default="Usuario Invitado", type=str, help="Nombre del usuario.")
    parser.add_argument("--cargo", default="N/A", type=str, help="Cargo del usuario.")
    parser.add_argument("--foto", default="SIN_FOTO", type=str, help="Ruta a la foto del usuario.")
    parser.add_argument("--tema", default="litera", type=str, help="Tema de ttkbootstrap para la GUI.")
    parser.add_argument("--ruta-datos", type=str, help="Ruta a la carpeta de datos central (consistencia).")

    args = parser.parse_args()

    if args.run_server:
        # Lógica para el servidor (importar y ejecutar tray_app)
        if not args.base_path:
            print("ERROR: El modo --run-server requiere el argumento --base-path.")
            sys.exit(1)
        import tray_app
        tray_app.main(args.base_path)
        sys.exit(0)

    elif args.run_client:
        # Lógica para el cliente (importar y ejecutar session_cliente)
        if not args.base_path:
            print("ERROR: El modo --run-client requiere el argumento --base-path.")
            sys.exit(1)
        import session_cliente
        session_cliente.run_client_logic(args.base_path)
        sys.exit(0)
    
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
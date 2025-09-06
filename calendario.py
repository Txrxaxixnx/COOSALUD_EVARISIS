# calendario.py (Versión Final y 100% Funcional)

import calendar
import datetime
import tkinter as tk
from tkinter import ttk
import types

# =========================================================================
# BLOQUE DE IMPORTACIÓN DEFINITIVO
# Basado en el diagnóstico del error, este bloque hace lo siguiente:
# 1. Intenta importar 'tooltip' de la forma más común.
# 2. Si lo que importa es un MÓDULO (tu caso), extrae de su interior
#    el nombre 'ToolTip' (con mayúsculas), que es el que Python nos dijo que usáramos.
# 3. Si todo eso falla, prueba el método de las versiones antiguas.
# =========================================================================
try:
    from ttkbootstrap import tooltip as tooltip_object
    if isinstance(tooltip_object, types.ModuleType):
        # TU CASO ESPECÍFICO: El objeto importado es un módulo,
        # y dentro de él, la clase se llama 'ToolTip'.
        tooltip = tooltip_object.ToolTip
    else:
        # Caso estándar moderno: el objeto importado ya es la función.
        tooltip = tooltip_object
except ImportError:
    # Caso de versiones antiguas de la librería.
    from ttkbootstrap.tooltip import Tooltip as tooltip
except Exception as e:
    print(f"Error inesperado al importar Tooltip: {e}")
    def tooltip(*args, **kwargs):
        print("ADVERTENCIA: Tooltips desactivados por un error.")
        return None
# =========================================================================

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
except ImportError:
    raise ImportError("Por favor, asegúrate de que ttkbootstrap esté instalado: pip install ttkbootstrap")

try:
    import babel
    from babel.dates import get_day_names, get_month_names
except ImportError:
    raise ImportError("Por favor, instale babel: pip install Babel")

try:
    import holidays
except ImportError:
    raise ImportError("Por favor, instale holidays: pip install holidays")


class CalendarioInteligente(ttk.Toplevel):
    """
    Un widget de calendario inteligente y modal que se integra con ttkbootstrap.
    Permite la selección de fechas y visualiza datos contextuales para cada día.
    """

    @classmethod
    def seleccionar_fecha(cls, parent=None, fecha_inicial=None, mapa_de_datos=None,
                         locale='es_ES', codigo_pais_festivos=None, titulo="Seleccionar Fecha",
                         mapa_estilos=None):
        dialogo = cls(parent, fecha_inicial, mapa_de_datos, locale,
                      codigo_pais_festivos, titulo, mapa_estilos)
        dialogo.wait_window()
        return dialogo.fecha_seleccionada

    def __init__(self, parent=None, fecha_inicial=None, mapa_de_datos=None,
                 locale='es_ES', codigo_pais_festivos=None, titulo="Seleccionar Fecha",
                 mapa_estilos=None):
        
        super().__init__(parent)
        self.title(titulo)

        self.protocol("WM_DELETE_WINDOW", self._on_cancelar)
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        self.locale = locale
        self.codigo_pais_festivos = codigo_pais_festivos
        self.mapa_de_datos_usuario = mapa_de_datos or {}
        
        mapa_estilos_defecto = {'Día Festivo': 'danger', 'seleccionado': 'success', 'hoy': 'outline-info'}
        self.mapa_estilos = {**mapa_estilos_defecto, **(mapa_estilos or {})}

        hoy = datetime.date.today()
        self.fecha_mostrada = fecha_inicial or hoy
        self.fecha_seleccionada_actual = fecha_inicial or hoy
        self.fecha_seleccionada = None

        self.festivos_cargados_por_anio = set()
        self.mapa_de_datos_interno = {}
        
        self._cargar_festivos_si_es_necesario(self.fecha_mostrada.year)
        self._construir_ui()
        self._actualizar_vista_calendario()
        
        self.update_idletasks()
        if parent:
            x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{x}+{y}")

    def _cargar_festivos_si_es_necesario(self, anio):
        if self.codigo_pais_festivos and anio not in self.festivos_cargados_por_anio:
            try:
                festivos_del_anio = holidays.country_holidays(self.codigo_pais_festivos, years=anio)
                self.festivos_cargados_por_anio.add(anio)
                mapa_festivos = {
                    fecha: {'estado': 'Día Festivo', 'detalle': nombre}
                    for fecha, nombre in festivos_del_anio.items()
                }
                self.mapa_de_datos_interno.update(mapa_festivos)
            except Exception as e:
                print(f"No se pudieron cargar los festivos para '{self.codigo_pais_festivos}' año {anio}: {e}")
        
        self.mapa_de_datos_interno.update(self.mapa_de_datos_usuario)

    def _construir_ui(self):
        frame_principal = ttk.Frame(self, padding=10)
        frame_principal.pack(expand=True, fill=BOTH)

        frame_header = ttk.Frame(frame_principal)
        frame_header.pack(fill=X, pady=5)
        btn_mes_anterior = ttk.Button(frame_header, text="<", command=lambda: self._cambiar_mes(-1), bootstyle="secondary")
        btn_mes_anterior.pack(side=LEFT)
        self.lbl_mes_anio = ttk.Label(frame_header, font="-weight bold -size 12", anchor=CENTER)
        self.lbl_mes_anio.pack(side=LEFT, expand=True, fill=X)
        btn_mes_siguiente = ttk.Button(frame_header, text=">", command=lambda: self._cambiar_mes(1), bootstyle="secondary")
        btn_mes_siguiente.pack(side=LEFT)

        frame_dias_semana = ttk.Frame(frame_principal)
        frame_dias_semana.pack(fill=X, pady=(5, 2))
        
        nombres_dias_babel = get_day_names('abbreviated', locale=self.locale)
        nombres_dias = [nombres_dias_babel[i] for i in range(7)]
        
        for i, nombre_dia in enumerate(nombres_dias):
            frame_dias_semana.columnconfigure(i, weight=1)
            lbl = ttk.Label(frame_dias_semana, text=nombre_dia.upper(), anchor=CENTER, bootstyle="secondary")
            lbl.grid(row=0, column=i, sticky="nsew")

        frame_calendario = ttk.Frame(frame_principal, name="grid-calendario")
        frame_calendario.pack(expand=True, fill=BOTH)
        
        self.botones_dias = []
        for i in range(6):
            frame_calendario.rowconfigure(i, weight=1)
            for j in range(7):
                frame_calendario.columnconfigure(j, weight=1)
                btn = ttk.Button(frame_calendario, text="", bootstyle="light")
                btn.grid(row=i, column=j, sticky="nsew", padx=1, pady=1)
                self.botones_dias.append(btn)

        frame_footer = ttk.Frame(frame_principal)
        frame_footer.pack(fill=X, pady=(10, 0))
        ttk.Button(frame_footer, text="Cancelar", command=self._on_cancelar, bootstyle="secondary").pack(side=RIGHT)
        ttk.Button(frame_footer, text="Confirmar", command=self._on_confirmar, bootstyle="primary").pack(side=RIGHT, padx=5)

    def _actualizar_vista_calendario(self):
        nombres_meses = get_month_names('wide', locale=self.locale)
        self.lbl_mes_anio.config(text=f"{nombres_meses[self.fecha_mostrada.month].capitalize()} {self.fecha_mostrada.year}")
        
        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        matriz_mes = cal.monthdatescalendar(self.fecha_mostrada.year, self.fecha_mostrada.month)
        
        hoy = datetime.date.today()

        for i, fecha in enumerate(sum(matriz_mes, [])):
            btn = self.botones_dias[i]
            
            # Limpieza del tooltip viejo
            if hasattr(btn, 'tooltip') and btn.tooltip:
                try:
                    btn.tooltip.destroy()
                # CORRECCIÓN FINAL: Capturamos CUALQUIER error posible al destruir el tooltip,
                # lo que evita que el bucle de actualización se detenga.
                except Exception:
                    pass
                btn.tooltip = None
            
            btn.config(text=str(fecha.day))
            
            bootstyle = "light"
            estado_tk = "normal"
            tooltip_text = None

            if fecha.month != self.fecha_mostrada.month:
                estado_tk = "disabled"
                bootstyle = "light-outline"
            else:
                if fecha == hoy:
                    bootstyle = self.mapa_estilos.get('hoy', 'outline-info')
                if fecha in self.mapa_de_datos_interno:
                    info_dia = self.mapa_de_datos_interno[fecha]
                    estado_dia = info_dia.get('estado')
                    if estado_dia in self.mapa_estilos:
                        bootstyle = self.mapa_estilos[estado_dia]
                    tooltip_text = info_dia.get('detalle') or info_dia.get('estado')
                if fecha == self.fecha_seleccionada_actual:
                    bootstyle = self.mapa_estilos.get('seleccionado', 'success')
            
            btn.config(bootstyle=bootstyle, state=estado_tk, command=lambda f=fecha: self._on_seleccionar_dia(f))
            
            if tooltip_text:
                btn.tooltip = tooltip(btn, text=tooltip_text)

    def _cambiar_mes(self, delta):
        current_year, current_month = self.fecha_mostrada.year, self.fecha_mostrada.month
        new_month = current_month + delta
        new_year = current_year
        if new_month > 12:
            new_month = 1
            new_year += 1
        elif new_month < 1:
            new_month = 12
            new_year -= 1
        
        self.fecha_mostrada = self.fecha_mostrada.replace(year=new_year, month=new_month, day=1)
        self._cargar_festivos_si_es_necesario(self.fecha_mostrada.year)
        self._actualizar_vista_calendario()

    def _on_seleccionar_dia(self, fecha):
        self.fecha_seleccionada_actual = fecha
        self._actualizar_vista_calendario()

    def _on_confirmar(self):
        self.fecha_seleccionada = self.fecha_seleccionada_actual
        self.destroy()

    def _on_cancelar(self):
        self.fecha_seleccionada = None
        self.destroy()

# --- Ejemplo de Uso ---
if __name__ == '__main__':
    class App(ttk.Window):
        def __init__(self):
            super().__init__(themename="litera")
            self.title("Ejemplo Calendario Inteligente")
            self.geometry("400x300")
            
            self.lbl_resultado = ttk.Label(self, text="Haga clic para seleccionar una fecha.", font="-size 12")
            self.lbl_resultado.pack(pady=20, expand=True)
            
            ttk.Button(self, text="Abrir Calendario", command=self.abrir_calendario).pack(pady=10)

        def abrir_calendario(self):
            self.lbl_resultado.config(text="Esperando selección...")
            mapa_de_reportes = {
                datetime.date.today() - datetime.timedelta(days=1): {'estado': 'Reporte Correcto', 'detalle': 'Todo OK'},
                datetime.date.today() - datetime.timedelta(days=2): {'estado': 'Reporte con Advertencia'},
            }
            mapa_de_estilos_custom = {'Reporte Correcto': 'info', 'Reporte con Advertencia': 'warning'}

            self.current_locale = 'es_CO'

            fecha_elegida = CalendarioInteligente.seleccionar_fecha(
                parent=self,
                fecha_inicial=datetime.date.today(),
                mapa_de_datos=mapa_de_reportes,
                locale=self.current_locale,
                codigo_pais_festivos='CO',
                mapa_estilos=mapa_de_estilos_custom
            )

            if fecha_elegida:
                babel_locale = babel.Locale.parse(self.current_locale)
                try:
                    fecha_formateada = babel.dates.format_date(fecha_elegida, format='full', locale=babel_locale)
                except Exception:
                    fecha_formateada = fecha_elegida.strftime('%d/%m/%Y')

                self.lbl_resultado.config(text=f"Fecha: {fecha_formateada}", bootstyle="success")
            else:
                self.lbl_resultado.config(text="Selección cancelada.", bootstyle="danger")

    app = App()
    app.mainloop()
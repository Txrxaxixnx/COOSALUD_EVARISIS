## Análisis del Archivo: `calendario.py` (06/09/2025)

1) Propósito

- Widget de calendario modal, estilizado con ttkbootstrap, para seleccionar fechas con soporte de locales (Babel) y festivos por país (holidays). Permite resaltar días con “estado” y mostrar tooltips con “detalle”.

2) API y uso

- `CalendarioInteligente.seleccionar_fecha(parent=None, fecha_inicial=None, mapa_de_datos=None, locale='es_ES', codigo_pais_festivos=None, titulo='Seleccionar Fecha', mapa_estilos=None) -> date|None`
  - `mapa_de_datos`: dict[date] → {'estado': str, 'detalle'?: str}
  - `mapa_estilos`: dict[estado] → bootstyle (ej. 'danger', 'success', 'info')
  - Retorna `datetime.date` o `None` si el usuario cancela.

3) Componentes clave

- Importación de `tooltip` compatible con múltiples versiones de ttkbootstrap (usa `tooltip.ToolTip` si el import devuelve un módulo).
- Carga perezosa de festivos por año (holidays), fusionados con `mapa_de_datos` del usuario.
- Construcción de UI: header (mes/año, navegación), fila de nombres de día (localizada), grilla 6x7 de días, footer con Confirmar/Cancelar.
- `_actualizar_vista_calendario`: setea texto, estado y estilo de cada día; asigna tooltip si hay `detalle`; maneja “hoy” y “seleccionado”.

4) Dependencias

- `ttkbootstrap`, `Babel`, `holidays`; opcionalmente tooltips de ttkbootstrap.

5) Ejemplo rápido

```python
fecha = CalendarioInteligente.seleccionar_fecha(
    parent=raiz,
    fecha_inicial=datetime.date.today(),
    mapa_de_datos={datetime.date.today(): {'estado': 'Reporte Correcto', 'detalle': 'OK'}},
    locale='es_CO',
    codigo_pais_festivos='CO',
    mapa_estilos={'Reporte Correcto': 'info'}
)
```

6) Estado

- Funcional y estable. Maneja edge cases de tooltips y compatibilidad de import.

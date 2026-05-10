# Calidad de datos

La calidad de datos puede cambiar completamente un backtest.

El diagnostico avanzado revisa:

- Columnas requeridas.
- Fechas invalidas o duplicadas.
- Gaps de fechas.
- Valores nulos.
- OHLC inconsistente.
- Outliers extremos de retorno.
- Volumen cero, negativo o sospechoso.
- Diferencias grandes entre `close` y `adj_close`.
- Tipo de activo detectado: tradicional, cripto, futures o desconocido.
- Calendario esperado segun activo.

## Calendarios

Para datos diarios, el diagnostico compara fechas observadas contra un calendario esperado:

- Cripto: 7 dias por semana.
- Acciones/ETFs USA: usa `pandas-market-calendars` si esta instalado; si no, cae a un calendario built-in de dias habiles menos feriados principales NYSE/Nasdaq.
- Futures/desconocidos: calendario generico de dias habiles.
- Algunos sufijos de ticker intentan mapear a exchange especifico, por ejemplo `.L`, `.TO`, `.PA`, `.DE`, `.HK`, `.T` y `.AX`.

Esto evita marcar fines de semana o feriados USA como gaps falsos en ETFs, y permite detectar fines de semana faltantes en cripto.

La app prioriza siempre la fuente mas precisa disponible:

1. `pandas-market-calendars`, si esta instalado y soporta el exchange.
2. Calendario built-in del proyecto.
3. Calendario generico de dias habiles si no se conoce el exchange.

Instalacion del extra opcional:

```powershell
python -m pip install -e .[dev,ui,calendars]
```

Cuando usa `pandas-market-calendars`, el reporte muestra la fuente y tambien medias jornadas detectadas si la libreria las informa.

El Data Quality Score es heuristico. Sirve para priorizar revision, no para garantizar que los datos sean institucionales.

Al mezclar ETFs y cripto, los calendarios son distintos. En portfolios o comparaciones multi-activo, las fechas comunes pueden ocultar movimientos de fin de semana de cripto hasta la siguiente fecha compartida.

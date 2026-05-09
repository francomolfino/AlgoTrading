TOOLTIPS = {
    "ticker": "Ticker tal como lo entiende la fuente de datos. Ejemplos: SPY, QQQ, BTC-USD.",
    "date_range": "Periodo historico a descargar o analizar. Periodos muy cortos dan conclusiones debiles.",
    "timeframe": "Intervalo de las barras. El proyecto esta mas probado con datos diarios 1d.",
    "missing_data": "NaN, fechas duplicadas o gaps grandes pueden distorsionar indicadores y backtests.",
    "adjusted_close": "Precio ajustado por splits y dividendos cuando la fuente lo provee.",
    "volume": "Cantidad operada. Sirve para detectar dias raros, no garantiza liquidez real.",
    "validation": "Chequea columnas requeridas, fechas, nulos y consistencia basica OHLCV.",
    "capital": "Capital inicial simulado. No representa dinero real ni una cuenta conectada.",
    "commission": "Costo por operacion en basis points. 1 bps = 0.01%.",
    "slippage": "Penalizacion simple para aproximar peor precio de ejecucion.",
    "benchmark": "Referencia para comparar. Buy and hold se calcula automaticamente cuando aplica.",
    "position_sizing": "Fraccion del capital que la estrategia puede usar en una entrada.",
    "drawdown": "Caida desde el maximo previo de equity. Mide dolor y riesgo de supervivencia.",
    "sharpe": "Retorno ajustado por volatilidad aproximado. Puede inflarse en muestras pequenas.",
    "cagr": "Retorno anual compuesto. Solo tiene sentido en periodos suficientemente largos.",
    "stop_loss": "Salida simulada si el cierre cae debajo del umbral. No modela gaps intradiarios.",
    "take_profit": "Salida simulada si el cierre supera el umbral. Puede cortar tendencias fuertes.",
    "rebalance": "Ajuste periodico de pesos. En esta primera UI queda para Portfolio Lab.",
    "exposure": "Porcentaje maximo del capital expuesto al mercado.",
    "in_sample": "Periodo usado para desarrollar o elegir parametros.",
    "out_of_sample": "Periodo separado para evaluar sin tocar parametros.",
    "walk_forward": "Prueba por ventanas moviles para mirar estabilidad temporal.",
    "overfitting": "Ajustar demasiado al pasado hasta capturar ruido en vez de una idea robusta.",
    "robustness": "Capacidad de mantener resultados razonables en activos, parametros y periodos distintos.",
    "sensitivity": "Cuanto cambian los resultados al mover parametros cercanos.",
}


EDUCATIONAL_WARNING = (
    "Herramienta educativa y de research. No opera dinero real, no envia ordenes reales "
    "y no promete rentabilidad."
)


PAPER_SIMULATION_WARNING = (
    "Modo simulacion. No se envian ordenes reales, no hay broker real conectado "
    "y los fills son generados por FakeBroker."
)


RESEARCH_FLOW_STEPS = [
    "Validar datos antes de mirar senales.",
    "Revisar senales antes de correr backtest.",
    "Comparar siempre contra buy and hold o benchmark.",
    "Leer drawdown, trades y periodo antes que retorno total.",
    "Validar robustez fuera de muestra antes de creer un resultado.",
]


METRIC_EXPLANATIONS = {
    "Retorno total": "Cambio acumulado de equity en el periodo. Puede ser enganoso si el periodo es corto.",
    "CAGR": "Retorno anual compuesto. Tiene sentido solo con suficiente historial.",
    "Sharpe aprox.": "Retorno ajustado por volatilidad. Puede inflarse con pocos trades o poca muestra.",
    "Max drawdown": "Peor caida desde un maximo previo. Mide riesgo de supervivencia, no solo incomodidad.",
    "Win rate": "Porcentaje de trades ganadores. No alcanza: pocos ganadores grandes pueden compensar muchos perdedores.",
    "Numero de trades": "Tamano de muestra. Con pocos trades, cualquier conclusion es fragil.",
    "Exceso vs benchmark": "Diferencia contra buy and hold. Si es negativa, la estrategia no justifico su complejidad en ese periodo.",
    "Exposure time": "Tiempo expuesto al mercado. Menor exposicion puede explicar menor retorno y menor drawdown.",
}


RESULT_READING_ORDER = [
    "1. Periodo y activo: confirma que la muestra sea suficiente.",
    "2. Benchmark: mira si supera a buy and hold.",
    "3. Drawdown: evalua si sobrevivirias ese peor tramo.",
    "4. Trades: si hay pocos, baja la confianza.",
    "5. Costos: comisiones y slippage pueden cambiar la historia.",
    "6. Robustez: train/test, walk-forward y multi-activo antes de confiar.",
]

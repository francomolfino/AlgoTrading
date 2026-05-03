# AlgoTrading Lab

Proyecto educativo para aprender trading algorítmico construyendo herramientas reales en Python, de forma incremental y prudente.

Este proyecto no promete rentabilidad ni intenta operar dinero real. La idea es aprender a descargar datos, validarlos, analizarlos, backtestear estrategias simples y comparar resultados con cuidado.

## Etapa 1: datos históricos

Incluye:

- Estructura inicial de proyecto Python.
- Descarga de datos históricos con `yfinance`.
- Normalización a columnas simples: `date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`.
- Validación básica de columnas, nulos, fechas duplicadas y consistencia OHLC.
- Guardado en CSV o parquet.
- Tests básicos sin depender de internet.

## Setup en Windows

Desde PowerShell, parado en la carpeta del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

Si PowerShell bloquea la activación del entorno virtual, podés usar:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Descargar datos

Ejemplo con acciones/ETFs y cripto:

```powershell
python scripts\download_data.py --symbols SPY QQQ BTC-USD ETH-USD --start 2018-01-01 --interval 1d --format csv
```

Con fecha final:

```powershell
python scripts\download_data.py --symbols SPY --start 2020-01-01 --end 2024-12-31 --interval 1d
```

Guardar como parquet:

```powershell
python scripts\download_data.py --symbols SPY BTC-USD --start 2021-01-01 --format parquet
```

Los archivos se guardan por defecto en `data/raw/`, por ejemplo:

```text
data/raw/SPY_1D.csv
data/raw/BTC_USD_1D.csv
```

Nota: en Yahoo Finance, para datos diarios, `--end` suele comportarse como fecha exclusiva. Si pedís `--end 2024-12-31`, puede traer datos hasta el día hábil anterior.

## Correr tests

```powershell
python -m pytest
```

## Etapa 2: primer analisis exploratorio

Una vez descargados los datos, podes generar retornos diarios, medias moviles y un grafico de precio/volumen:

```powershell
python scripts\explore_data.py --symbol SPY --windows 20 50 200
```

Para cripto:

```powershell
python scripts\explore_data.py --symbol BTC-USD --windows 20 50 200
```

Tambien podes pasar un archivo directo:

```powershell
python scripts\explore_data.py --input data\raw\SPY_1D.csv --windows 10 50 100
```

Salidas por defecto:

```text
data/processed/SPY_1D_exploration.csv
reports/figures/SPY_1D_exploration.png
```

Que estas viendo:

- `daily_return`: cambio porcentual diario usando `adj_close`.
- `sma_20`, `sma_50`, `sma_200`: medias moviles simples; suavizan el precio para ver tendencia, pero llegan tarde por construccion.
- Panel superior del grafico: precio ajustado y medias moviles.
- Panel inferior: volumen. Sirve para detectar dias con participacion inusual, no para confirmar por si solo que una estrategia sea buena.

Nota prudente: en esta etapa las medias moviles son solo descriptivas. Para backtesting, las senales deberan usar informacion disponible hasta el cierre anterior para evitar lookahead bias.

## Etapa 3: primer backtester simple

El backtester actual es educativo y long-only:

- Entra comprado cuando la senal es `1`.
- Sale a efectivo cuando la senal es `0`.
- Usa todo el capital disponible, sin apalancamiento.
- Aplica comisiones y slippage en basis points.
- Ejecuta la senal con un dia de retraso: `signal[t]` opera en `t+1`.
- Cierra posiciones abiertas al final del periodo para calcular trades completos.

Ejemplo con una senal demo `adj_close > SMA(200)`:

```powershell
python scripts\run_backtest.py --symbol SPY --initial-capital 10000 --commission-bps 1 --slippage-bps 2
```

Cambiar la SMA demo:

```powershell
python scripts\run_backtest.py --symbol QQQ --demo-sma-window 100
```

Usar un archivo con una columna propia `signal`:

```powershell
python scripts\run_backtest.py --input data\processed\SPY_1D_exploration.csv --signal-column signal
```

Salidas:

```text
reports/backtests/SPY_1D_DEMO_SMA_200_equity.csv
reports/backtests/SPY_1D_DEMO_SMA_200_trades.csv
reports/backtests/SPY_1D_DEMO_SMA_200_metrics.json
reports/figures/SPY_1D_DEMO_SMA_200_equity.png
```

Metricas incluidas:

- Retorno total.
- CAGR si el periodo permite calcularlo.
- Sharpe ratio aproximado, sin tasa libre de riesgo.
- Max drawdown.
- Win rate.
- Numero de trades.
- Comisiones totales.

Decision prudente: este backtester no simula liquidez real, spreads variables, impuestos, gaps intradiarios ni ejecucion parcial. Sirve para aprender mecanica y detectar ideas malas rapido, no para operar dinero real.

## Etapa 4: estrategias iniciales

Estrategias incluidas:

- `buy_and_hold`: compra y mantiene.
- `sma_cross`: cruce de medias moviles.
- `rsi`: compra sobreventa y sale en sobrecompra.
- `breakout`: compra ruptura de maximos previos y sale al perder minimos previos.
- `trend_filter`: cruce de medias habilitado solo cuando el precio esta sobre una media larga.

Comparar todas contra el mismo activo:

```powershell
python scripts\compare_strategies.py --symbol SPY
```

Cambiar parametros:

```powershell
python scripts\compare_strategies.py --symbol QQQ --sma-fast 20 --sma-slow 100 --rsi-oversold 35 --rsi-overbought 65 --breakout-entry-window 40 --breakout-exit-window 15
```

Salidas:

```text
reports/strategy_comparison/SPY_1D_summary.csv
reports/strategy_comparison/SPY_1D_BUY_AND_HOLD_equity.csv
reports/strategy_comparison/SPY_1D_BUY_AND_HOLD_trades.csv
reports/strategy_comparison/SPY_1D_BUY_AND_HOLD_metrics.json
reports/figures/SPY_1D_strategy_comparison.png
```

El resumen incluye un comentario breve por estrategia comparando retorno y drawdown contra buy and hold. Ese comentario no es una recomendacion; es una lectura rapida para detectar trade-offs.

Decision prudente: si una estrategia no supera a buy and hold, no significa que sea inutil; puede haber reducido drawdown o exposicion. Pero si solo empeora retorno y drawdown, la descartamos sin romanticismo.

## Etapa 5: controles anti-autoengano

Esta etapa agrega evaluacion train/test y walk-forward simple. Todavia no optimizamos parametros; solo medimos si las estrategias se comportan de forma razonable fuera del periodo completo.

Train/test:

```powershell
python scripts\evaluate_robustness.py --symbol SPY --train-ratio 0.7
```

Train/test + walk-forward:

```powershell
python scripts\evaluate_robustness.py --symbol SPY --train-ratio 0.7 --walk-forward
```

Cambiar ventanas walk-forward, usando filas diarias aproximadas:

```powershell
python scripts\evaluate_robustness.py --symbol SPY --walk-forward --wf-train-rows 756 --wf-test-rows 252 --wf-step-rows 252
```

Salidas:

```text
reports/robustness/SPY_1D_train_test.csv
reports/robustness/SPY_1D_walk_forward.csv
```

Controles incorporados:

- Lookahead bias: el backtester ejecuta `signal[t]` en `t+1`, no en la misma barra.
- Benchmark obligatorio: todas las tablas incluyen comparacion contra `buy_and_hold`.
- Train/test: separa el historial en periodo inicial y periodo posterior.
- Warmup: el test puede usar barras anteriores solo para calcular indicadores, no para contar equity.
- Walk-forward: evalua ventanas de test moviles para mirar estabilidad temporal.
- Guardrail de optimizacion: hay utilidades para limitar el numero de combinaciones de parametros.

Sesgos que todavia requieren criterio:

- Survivorship bias: si hoy probas solo activos que sobrevivieron o fueron exitosos, tus resultados pueden quedar inflados. Por ejemplo, probar solo ETFs actuales grandes no representa todos los activos que existian en 2018.
- Overfitting: si probas demasiados parametros y elegis el maximo retorno, probablemente estes ajustando ruido. En la siguiente etapa vamos a optimizar rangos chicos y mirar robustez, no solo el mejor numero.
- Regimen de mercado: que algo funcione en 2018-2026 no significa que funcione en tasas, inflacion, volatilidad o liquidez distintas.

Regla practica: una estrategia interesante deberia tener una historia razonable en test y en varias ventanas walk-forward. Si solo brilla en un bloque especifico, todavia no merece confianza.

## Etapa 6: optimizacion controlada

Esta etapa prueba rangos chicos de parametros y ordena candidatos por resultados fuera de muestra. No intenta encontrar "el parametro perfecto".

Ejemplo por defecto:

```powershell
python scripts\optimize_parameters.py --symbol SPY
```

Defaults:

```text
SMA fast: 10, 20, 30
SMA slow: 50, 100, 200
RSI thresholds: 30:70, 25:75
```

Probar solo SMA:

```powershell
python scripts\optimize_parameters.py --symbol SPY --strategies sma --sma-fast 10 20 30 --sma-slow 50 100 200
```

Probar solo RSI:

```powershell
python scripts\optimize_parameters.py --symbol SPY --strategies rsi --rsi-windows 14 --rsi-thresholds 30:70 25:75
```

Limitar combinaciones:

```powershell
python scripts\optimize_parameters.py --symbol SPY --max-combinations 12
```

Salidas:

```text
reports/optimization/SPY_1D_optimization_ranking.csv
reports/optimization/SPY_1D_optimization_periods.csv
```

Columnas importantes:

- `test_total_return`: retorno en el periodo de test.
- `test_vs_buy_and_hold_return`: diferencia contra buy and hold en test.
- `abs_train_test_return_gap`: diferencia absoluta entre retorno de train y test; cuanto mas grande, mas sospechoso.
- `test_max_drawdown`: peor caida en test.
- `comment`: lectura rapida del candidato.

Decision prudente: el ranking prioriza test vs buy and hold y estabilidad train/test. Un candidato con retorno enorme en train y flojo en test es una bandera roja, no un descubrimiento.

## Etapa 7: portfolio basico

Esta etapa compara varios activos y construye una cartera equal-weight simple.

Ejemplo:

```powershell
python scripts\analyze_portfolio.py --symbols SPY QQQ BTC-USD ETH-USD
```

Otros activos:

```powershell
python scripts\analyze_portfolio.py --symbols SPY QQQ
python scripts\analyze_portfolio.py --symbols BTC-USD ETH-USD
```

Salidas:

```text
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_prices.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_returns.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_individual_equity.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_equal_weight_equity.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_correlations.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_summary.csv
reports/figures/SPY_QQQ_BTC_USD_ETH_USD_1D_portfolio_equity.png
reports/figures/SPY_QQQ_BTC_USD_ETH_USD_1D_correlations.png
```

Que calcula:

- Retornos diarios por activo.
- Equity curve individual, como si invirtieras el capital inicial completo en cada activo por separado.
- Cartera equal-weight diaria, con el mismo peso en cada activo.
- Correlaciones de retornos diarios.
- Drawdown de la cartera.

Decision prudente: la cartera equal-weight ignora costos de rebalanceo, impuestos y restricciones operativas. Sirve para estudiar diversificacion y correlaciones; todavia no es una simulacion real de ejecucion.

Nota al mezclar ETFs y cripto: se usan fechas comunes entre activos. Los fines de semana de cripto no aparecen como filas separadas cuando tambien hay ETFs, pero su movimiento queda capturado en el siguiente precio disponible en fecha comun.

## Etapa 8: preparacion para paper trading

Esta etapa no conecta dinero real ni un broker real. Crea una arquitectura educativa para separar responsabilidades:

- `HistoricalDataProvider`: emite barras historicas una por una.
- `PaperStrategy`: calcula un peso objetivo con la informacion disponible.
- `RiskManager`: convierte peso objetivo en orden, aplicando reglas long-only.
- `FakeBroker`: simula market orders, comisiones, slippage, cash, posiciones y fills.
- `PaperTradingEngine`: coordina todo y loguea cuenta, ordenes y fills.

Simular paper trading con una estrategia SMA:

```powershell
python scripts\simulate_paper_trading.py --symbol SPY --strategy sma_cross --fast-window 20 --slow-window 200
```

Simular buy and hold:

```powershell
python scripts\simulate_paper_trading.py --symbol SPY --strategy buy_and_hold
```

Cambiar riesgo/costos:

```powershell
python scripts\simulate_paper_trading.py --symbol SPY --max-position-fraction 0.5 --commission-bps 1 --slippage-bps 2 --min-trade-value 50
```

Salidas:

```text
reports/paper_trading/SPY_1D_SMA_CROSS_20_200_account.csv
reports/paper_trading/SPY_1D_SMA_CROSS_20_200_orders.csv
reports/paper_trading/SPY_1D_SMA_CROSS_20_200_fills.csv
reports/paper_trading/SPY_1D_SMA_CROSS_20_200_summary.json
reports/figures/SPY_1D_SMA_CROSS_20_200_paper_equity.png
```

Decision prudente: el motor ejecuta la intencion de la estrategia en la barra siguiente. La estrategia ve la historia hasta hoy, pero la orden recien puede simularse manana. Esto reduce lookahead bias.

Antes de operar dinero real faltaria:

- data provider en vivo y confiable;
- broker adapter real;
- validacion de horarios de mercado;
- control de ordenes abiertas;
- reconciliacion contra cuenta real;
- manejo de errores de red;
- limites de perdida diaria;
- logs auditables persistentes;
- alertas y monitoreo;
- pruebas en paper trading real durante suficiente tiempo.

## Decisión prudente

Usamos `yfinance` porque es gratis y simple para aprender, pero no es una fuente institucional. Para operar con dinero real harían falta controles adicionales: calidad de datos, proveedor confiable, manejo de eventos corporativos, costos realistas, latencia, monitoreo, logs auditables y gestión de riesgo.

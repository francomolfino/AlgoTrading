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
- Permite definir que fraccion del capital usa en cada entrada, sin apalancamiento.
- Aplica comisiones y slippage en basis points.
- Ejecuta la senal con un dia de retraso: `signal[t]` opera en `t+1`.
- Puede aplicar stop loss y take profit simplificados usando precio de cierre.
- Cierra posiciones abiertas al final del periodo para calcular trades completos.
- Agrega un benchmark buy and hold con los mismos costos y sizing.

Ejemplo con una senal demo `adj_close > SMA(200)`:

```powershell
python scripts\run_backtest.py --symbol SPY --initial-capital 10000 --commission-bps 1 --slippage-bps 2
```

Cambiar la SMA demo:

```powershell
python scripts\run_backtest.py --symbol QQQ --demo-sma-window 100
```

Usar solo una parte del capital y stops educativos:

```powershell
python scripts\run_backtest.py --symbol SPY --position-fraction 0.5 --stop-loss-pct 0.10 --take-profit-pct 0.25
```

Usar un archivo con una columna propia `signal`:

```powershell
python scripts\run_backtest.py --input data\processed\SPY_1D_exploration.csv --signal-column signal
```

Por defecto, el backtester falla si `signal` tiene valores faltantes. Si queres tratarlos explicitamente como cash:

```powershell
python scripts\run_backtest.py --input data\processed\SPY_1D_exploration.csv --signal-column signal --allow-missing-signals-as-cash
```

Salidas:

```text
reports/backtests/SPY_1D_DEMO_SMA_200_equity.csv
reports/backtests/SPY_1D_DEMO_SMA_200_trades.csv
reports/backtests/SPY_1D_DEMO_SMA_200_orders.csv
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
- Retorno del benchmark buy and hold.
- Exceso de retorno contra benchmark.

Decision prudente: los stops y take profit usan cierre diario, no precios intradiarios. Este backtester no simula liquidez real, spreads variables, impuestos, gaps intradiarios ni ejecucion parcial. Sirve para aprender mecanica y detectar ideas malas rapido, no para operar dinero real.

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

Rebalanceo con costos simulados:

```powershell
python scripts\analyze_portfolio.py --symbols SPY QQQ BTC-USD ETH-USD --rebalance-frequency monthly --commission-bps 1 --slippage-bps 2
```

Salidas:

```text
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_prices.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_returns.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_individual_equity.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_equal_weight_equity.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_equal_weight_orders.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_correlations.csv
reports/portfolio/SPY_QQQ_BTC_USD_ETH_USD_1D_summary.csv
reports/figures/SPY_QQQ_BTC_USD_ETH_USD_1D_portfolio_equity.png
reports/figures/SPY_QQQ_BTC_USD_ETH_USD_1D_correlations.png
```

Que calcula:

- Retornos diarios por activo.
- Equity curve individual, como si invirtieras el capital inicial completo en cada activo por separado.
- Cartera equal-weight diaria, con el mismo peso en cada activo.
- Ordenes simuladas de rebalanceo, cash, pesos reales y costos.
- Correlaciones de retornos diarios.
- Drawdown de la cartera.

Decision prudente: la cartera equal-weight ahora puede simular rebalanceo, comisiones y slippage simples. Sigue ignorando impuestos, liquidez real, spreads variables y ejecucion parcial, asi que todavia no es una simulacion lista para dinero real.

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

## Etapa 12: sistema de experimentos

Esta etapa permite correr backtests reproducibles desde configs JSON y guardar una carpeta completa por experimento.

Ejemplo:

```powershell
python scripts\run_experiment.py --config configs\experiments\spy_sma_cross.json
```

Comparar experimentos ya corridos:

```powershell
python scripts\compare_experiments.py --experiments-root experiments
```

Cada experimento guarda:

- `config.json`: configuracion exacta usada.
- `metadata.json`: version del proyecto, Python, pandas y commit git si esta disponible.
- `summary.csv`: metricas principales por activo.
- `<SYMBOL>/equity.csv`: equity curve.
- `<SYMBOL>/trades.csv`: trades cerrados.
- `<SYMBOL>/orders.csv`: ordenes simuladas.
- `<SYMBOL>/metrics.json`: metricas completas.
- `figures/`: graficos generados.

Decision prudente: el sistema de experimentos no mejora una estrategia por si solo. Sirve para trazabilidad: poder repetir, comparar y auditar resultados sin depender de memoria o comandos sueltos.

## Etapa 13: reportes automaticos

Cada experimento genera reportes por activo dentro de la carpeta del simbolo:

```text
experiments/<RUN_ID>_<EXPERIMENT_NAME>/SPY/report.md
experiments/<RUN_ID>_<EXPERIMENT_NAME>/SPY/metrics_table.csv
experiments/<RUN_ID>_<EXPERIMENT_NAME>/SPY/monthly_returns.csv
experiments/<RUN_ID>_<EXPERIMENT_NAME>/SPY/period_extremes.csv
experiments/<RUN_ID>_<EXPERIMENT_NAME>/SPY/exposure.csv
experiments/<RUN_ID>_<EXPERIMENT_NAME>/SPY/equity_drawdown.png
```

El reporte incluye:

- equity curve y drawdown;
- tabla de metricas;
- comparacion contra benchmark buy and hold;
- retornos mensuales;
- mejores y peores ventanas;
- exposicion al mercado;
- resumen de trades;
- comentario automatico breve.

Uso:

```powershell
python scripts\run_experiment.py --config configs\experiments\spy_sma_cross.json
```

Decision prudente: el comentario automatico no recomienda operar. Solo resume trade-offs visibles: retorno vs benchmark, drawdown, exposicion y cantidad de trades. Si hay pocos trades o un resultado demasiado llamativo, lo marca como algo a revisar.

## Etapa 14: robustez de estrategias

El diagnostico de robustez combina train/test, walk-forward y comparacion contra buy and hold en una tabla con score y flags.

Un activo:

```powershell
python scripts\evaluate_robustness.py --symbol SPY --walk-forward
```

Varios activos:

```powershell
python scripts\evaluate_robustness.py --symbols SPY QQQ BTC-USD ETH-USD --walk-forward
```

Salidas:

```text
reports/robustness/SPY_1D_train_test.csv
reports/robustness/SPY_1D_walk_forward.csv
reports/robustness/SPY_1D_diagnostics.csv
```

Flags posibles:

- `underperforms_benchmark_in_test`: pierde contra buy and hold en test.
- `large_train_test_gap`: train y test cuentan historias muy distintas.
- `few_trades`: pocos trades para sacar conclusiones fuertes.
- `unstable_walk_forward`: falla en demasiadas ventanas walk-forward.
- `walk_forward_underperforms_benchmark`: pierde contra benchmark en promedio walk-forward.
- `too_good_to_trust`: resultado demasiado llamativo para creerlo sin revisar.
- `high_drawdown`: drawdown muy grande.

La optimizacion controlada tambien guarda sensibilidad de parametros:

```powershell
python scripts\optimize_parameters.py --symbol SPY
```

Salida nueva:

```text
reports/optimization/SPY_1D_parameter_sensitivity.csv
```

Decision prudente: el `robustness_score` no decide por vos. Sirve para ordenar revisiones y detectar fragilidad. Una estrategia con score alto igual necesita validacion fuera de muestra, costos realistas, paper trading y control de riesgo.

## Etapa 15: risk management

Esta etapa agrega reglas explicitas para limitar riesgo en backtesting y paper trading simulado.

Backtest con limites:

```powershell
python scripts\run_backtest.py --symbol SPY --position-fraction 0.5 --max-total-exposure 0.5 --max-drawdown-pct 0.20 --stop-loss-pct 0.10 --take-profit-pct 0.25
```

Backtest con volatility targeting educativo:

```powershell
python scripts\run_backtest.py --symbol SPY --volatility-target-pct 0.15 --volatility-window 20
```

Paper trading simulado con corte por drawdown:

```powershell
python scripts\simulate_paper_trading.py --symbol SPY --max-position-fraction 0.5 --max-total-exposure 0.5 --max-drawdown-pct 0.20 --max-trades-per-day 2
```

Reglas incluidas:

- `position_fraction`: fraccion base de capital por entrada.
- `max_total_exposure`: exposicion maxima total long-only.
- `max_drawdown_pct`: apaga la estrategia y liquida posicion si se alcanza el drawdown limite.
- `max_trades_per_day`: limita cantidad de ordenes simuladas por dia.
- `stop_loss_pct` y `take_profit_pct`: salidas simples usando precio de cierre.
- `volatility_target_pct`: reduce exposicion cuando la volatilidad realizada supera el objetivo.

Columnas nuevas utiles:

- `risk_halted`: indica si la estrategia quedo apagada por riesgo.
- `risk_event`: motivo del evento de riesgo, por ejemplo `max_drawdown`.
- `blocked_reason`: motivo por el que no se envio una orden, por ejemplo `trade_limit`.

Decision prudente: estas reglas no vuelven rentable una estrategia. Sirven para evitar que una idea mala destruya la cuenta simulada sin control. En dinero real faltarian limites diarios, monitoreo, alertas, reconciliacion con broker y manejo de errores operativos.

## Etapa 16: paper trading mas realista

El broker fake ahora registra lifecycle de ordenes y estado persistente.

Modo normal:

```powershell
python scripts\simulate_paper_trading.py --symbol SPY --strategy sma_cross --fast-window 20 --slow-window 200
```

Modo dry-run, sin fills ni cambios de posicion:

```powershell
python scripts\simulate_paper_trading.py --symbol SPY --dry-run --state-path reports\paper_trading\SPY_fake_broker_state.json
```

Salidas nuevas:

```text
reports/paper_trading/SPY_1D_SMA_CROSS_20_200_order_events.csv
reports/paper_trading/SPY_1D_SMA_CROSS_20_200_errors.csv
reports/paper_trading/SPY_fake_broker_state.json
```

Lifecycle registrado:

- `created`
- `submitted`
- `filled`
- `rejected`
- `cancelled`

Que mejora:

- `orders.csv` guarda el estado final de cada orden.
- `order_events.csv` guarda el camino completo de cada orden.
- `errors.csv` guarda rechazos y errores del broker fake.
- `dry-run` permite ver que ordenes intentaria enviar la estrategia sin llenar operaciones.
- `state-path` guarda cash, posiciones, ordenes, fills, eventos y errores en JSON.

Decision prudente: dry-run no es paper trading real con broker. Sirve para auditar intenciones y logging. En un broker real faltarian estados asincronicos, ordenes abiertas, cancelaciones reales, reconexion, reconciliacion de cuenta y manejo de errores de red.

## Etapa 17: preparacion para datos en vivo

Esta etapa no conecta dinero real ni una fuente live real. Prepara contratos para que el proyecto pueda cambiar de datos historicos a eventos de mercado sin reescribir estrategias.

Nuevas piezas:

- `MarketDataProvider`: interfaz para providers que emiten barras OHLCV.
- `MarketEventProvider`: interfaz para providers que emiten eventos.
- `MarketEvent`: evento comun para `bar`, `heartbeat`, `provider_error` y `market_closed`.
- `YahooHistoricalDataProvider`: encapsula yfinance para historico.
- `FakeLiveDataProvider`: reproduce datos historicos como si fueran eventos live.
- `SafeExecutionLoop`: loop defensivo que cuenta eventos, captura errores y corta de forma controlada.

Replay local de eventos usando datos ya descargados:

```powershell
python scripts\replay_market_events.py --symbol SPY --heartbeat-every 50
```

Limitar eventos para una prueba chica:

```powershell
python scripts\replay_market_events.py --symbol SPY --max-events 10
```

Salidas:

```text
reports/live_replay/SPY_1D_market_events.csv
reports/live_replay/SPY_1D_loop_errors.csv
reports/live_replay/SPY_1D_loop_summary.json
```

Decision prudente: el loop live/replay no opera. Solo demuestra como circularian eventos de mercado y donde se enchufarian strategy, execution, broker y risk manager. Antes de conectar un broker real faltan datos live confiables, sincronizacion horaria, calendario de mercado, ordenes asincronicas, reconciliacion de cuenta, monitoreo, alertas, limites diarios y pruebas prolongadas en paper trading real.

## Etapa 18: interfaz local Streamlit

La primera version de la interfaz permite usar el framework desde una app local.

Guia recomendada para aprender los conceptos basicos mientras usas la app:

- [Algorithmic Trading desde cero usando AlgoTrading Lab](docs/algorithmic_trading_desde_cero.md)

Instalar dependencias de UI:

```powershell
python -m pip install -e .[dev,ui]
```

Ejecutar:

```powershell
python -m streamlit run app\streamlit_app.py
```

Pantallas funcionales:

- Home / Overview.
- Data Manager.
- Strategy Lab.
- Backtest Runner.
- Results Dashboard.
- Experiment Explorer.
- Robustness Lab.
- Portfolio Lab.
- Risk Manager.
- Paper Trading Simulator.
- Reports / Export.
- Settings.

La UI permite validar datos, revisar senales, correr backtests, guardar experimentos,
ver metricas, equity curve, drawdown, trades, comparar experimentos guardados,
evaluar robustez, correr portfolios basicos, comparar reglas de riesgo y simular
paper trading sin ordenes reales.

Los graficos de la app usan TradingView Lightweight Charts con datos locales del
laboratorio. Los reportes de backtest guardan `equity_drawdown.html` interactivo
ademas del PNG estatico.

Decision prudente: la app no expone brokers reales ni pide API keys. Paper trading real
queda fuera de esta primera version visual; cualquier pantalla relacionada se muestra
como simulacion o pendiente.

## Decisión prudente

Usamos `yfinance` porque es gratis y simple para aprender, pero no es una fuente institucional. Para operar con dinero real harían falta controles adicionales: calidad de datos, proveedor confiable, manejo de eventos corporativos, costos realistas, latencia, monitoreo, logs auditables y gestión de riesgo.

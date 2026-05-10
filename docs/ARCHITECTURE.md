# Arquitectura

El proyecto esta separado en capas simples:

- `data`: descarga, storage y validacion de datos historicos.
- `strategies`: generacion de senales long-only.
- `backtesting`: simulacion educativa con comisiones, slippage, equity, trades y benchmark.
- `metrics`: calculos de retorno, CAGR, Sharpe aproximado y drawdown.
- `experiments`: ejecucion reproducible desde config JSON.
- `reports`: reportes y tablas derivadas.
- `paper_trading`: broker fake, risk manager, data provider historico y engine barra por barra.
- `ui`: app Streamlit, adapters y componentes visuales.

La UI no deberia contener logica cuantitativa pesada. Cuando necesita correr algo, llama adapters que transforman inputs visuales en requests testeables.

No hay broker real expuesto. Cualquier simulacion de ordenes usa `FakeBroker`.

# Interfaz Streamlit

App local educativa para usar el laboratorio sin tocar codigo constantemente.

## Instalar dependencias

Desde PowerShell, con el venv activado:

```powershell
python -m pip install -e .[dev,ui]
```

## Ejecutar

```powershell
python -m streamlit run app\streamlit_app.py
```

La app abre un servidor local. No conecta brokers reales y no envia ordenes reales.
Los graficos interactivos usan TradingView Lightweight Charts desde CDN, con datos
locales del laboratorio. Si estas sin internet, los reportes PNG siguen quedando
como respaldo estatico.

## Flujo recomendado

Si todavia no conoces lo basico de algorithmic trading, empeza por:

- [Algorithmic Trading desde cero usando AlgoTrading Lab](../docs/algorithmic_trading_desde_cero.md)

1. Abrir **Data Manager** y validar que haya datos locales.
2. Abrir **Strategy Lab** y revisar senales.
3. Abrir **Backtest Runner**, configurar capital, costos y riesgo.
4. Guardar el backtest como experimento.
5. Abrir **Results Dashboard** para revisar metricas, equity, drawdown y lectura critica.
6. Abrir **Experiment Explorer** para comparar experimentos.

## Pantallas incluidas en esta primera version

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

## Pendiente

- Refinamiento visual.
- Comparacion avanzada de configuraciones.
- Delete de experimentos con confirmacion.
- Paper trading paso a paso/pausar/reiniciar.
- Portfolio con contribucion por activo mas detallada.
- Robustez por regimenes de mercado.

## Nota prudente

La interfaz es para research. Los resultados pueden ser irreales si los datos son malos,
el periodo es corto, hay pocos trades o se optimizaron demasiados parametros. Antes de
operar dinero real harian falta broker paper real, datos live confiables, reconciliacion,
monitoreo, alertas y controles operativos.

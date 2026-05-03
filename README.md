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

## Decisión prudente

Usamos `yfinance` porque es gratis y simple para aprender, pero no es una fuente institucional. Para operar con dinero real harían falta controles adicionales: calidad de datos, proveedor confiable, manejo de eventos corporativos, costos realistas, latencia, monitoreo, logs auditables y gestión de riesgo.

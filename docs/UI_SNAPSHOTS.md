# Snapshots visuales de Streamlit

Los snapshots sirven para revisar cambios de UI de forma reproducible. No validan rentabilidad ni logica de trading; ayudan a detectar pantallas rotas, secciones vacias, textos cortados o graficos que no cargan.

## Instalacion

Desde PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[ui,visual]
python -m playwright install chromium
```

`playwright install chromium` descarga el navegador usado para capturar las pantallas.

## Capturar todas las pantallas

```powershell
python scripts\capture_streamlit_snapshots.py
```

El script levanta Streamlit localmente en el puerto `8502`, abre cada pagina con `?page=...` y guarda PNGs en:

```text
reports/ui_snapshots/
```

La carpeta `reports/` esta ignorada por Git porque los snapshots son artefactos locales.

## Capturar pantallas especificas

```powershell
python scripts\capture_streamlit_snapshots.py --pages "Home / Overview" "Results Dashboard" "Paper Trading Simulator"
```

## Usar una app ya abierta

Si ya tenes Streamlit corriendo:

```powershell
python scripts\capture_streamlit_snapshots.py --server-url http://localhost:8501
```

## Ajustar viewport

```powershell
python scripts\capture_streamlit_snapshots.py --width 1440 --height 1100
```

## Que revisar

- Que la navegacion cargue la pagina correcta.
- Que el diagnostico de research aparezca antes de graficos.
- Que tablas y metricas no se corten.
- Que no haya errores visibles de Streamlit.
- Que paper trading muestre claramente que es simulacion.
- Que los graficos no aparezcan vacios.

Esto no reemplaza tests unitarios. Es una revision visual para UX y presentacion.

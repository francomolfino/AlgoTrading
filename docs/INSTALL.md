# Instalacion

AlgoTrading Lab es una herramienta local y educativa de research. No conecta brokers reales ni envia ordenes reales.

## Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev,ui]
```

Para usar calendarios bursatiles mas precisos cuando esten disponibles:

```powershell
python -m pip install -e .[dev,ui,calendars]
```

Si PowerShell bloquea la activacion:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Ejecutar tests

```powershell
python -m pytest
```

## Ejecutar la app

```powershell
python -m streamlit run app\streamlit_app.py
```

La app abre en el navegador local. Todo corre en tu maquina.

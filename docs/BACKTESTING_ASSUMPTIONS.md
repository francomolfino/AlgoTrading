# Supuestos de backtesting

El backtester es educativo y prudente, pero no replica el mercado real.

Supuestos principales:

- Long-only.
- La senal se ejecuta con delay para reducir lookahead bias.
- Comisiones y slippage son configurables en basis points.
- El benchmark principal es buy and hold del mismo activo.
- Stops y take profit usan precios disponibles en la barra simulada.
- No se modelan impuestos, liquidez real, spreads variables, fills parciales ni impacto de mercado.

Antes de operar dinero real faltarian broker real, datos live confiables, reconciliacion, monitoreo, alertas, limites diarios y pruebas prolongadas en paper trading real.

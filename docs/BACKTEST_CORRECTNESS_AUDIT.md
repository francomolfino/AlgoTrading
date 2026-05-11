# Backtest Correctness Audit

Este documento describe que valida la auditoria de correctness del backtester. No intenta demostrar que una estrategia gane dinero. Intenta demostrar algo mas basico: que el motor no infla resultados por errores obvios de ejecucion, costos, cash, posiciones o benchmark.

## Como correrla

```powershell
python scripts\run_backtest_correctness_audit.py
python -m pytest tests\test_backtest_correctness_audit.py
```

El script genera:

```text
reports/backtest_correctness_audit.md
```

`reports/` esta ignorado por git porque es salida local reproducible.

## Supuestos validados

- El backtester es long-only: posicion `0` o `1`, sin shorts.
- Las senales son binarias: `0` cash, `1` long.
- La senal de la barra `t` se ejecuta en `t+1`.
- Por defecto, una senal faltante invalida el backtest.
- Si `allow_missing_signals=True`, una senal faltante se trata como cash.
- Las fechas duplicadas se rechazan.
- La equity se calcula como `cash + shares * precio observado`.
- El drawdown se calcula contra maximos acumulados de equity.
- La compra aplica slippage hacia arriba.
- La venta aplica slippage hacia abajo.
- La comision se descuenta en entrada y salida.
- El benchmark usa el mismo periodo y costos configurados.
- Stop loss y take profit son reglas simplificadas sobre el precio de cierre de la barra.

## Golden tests incluidos

1. **Precio plano sin trades**
   - Senal siempre `0`.
   - Equity constante.
   - Drawdown `0`.
   - Sin ordenes ni trades.

2. **Buy and hold con precio ascendente**
   - Entrada en la barra posterior a la primera senal.
   - Cierre forzado al final del periodo.
   - Retorno esperado calculado como `precio_salida / precio_entrada - 1`.

3. **Una compra y una venta con costos exactos**
   - Comision conocida.
   - Slippage conocido.
   - P&L esperado calculado a mano.
   - Verifica `entry_price`, `exit_price`, comisiones, P&L y equity final.

4. **Senal en t ejecuta en t+1**
   - La barra que contiene la senal no debe ejecutar la orden.
   - La entrada usa el precio de la barra siguiente.
   - Esto protege contra un lookahead bias basico.

5. **Senal con NaN**
   - Por defecto debe fallar.
   - Si se habilita explicitamente el modo cash, no debe abrir trades accidentalmente.

6. **Fechas duplicadas**
   - El backtester debe rechazar datos duplicados para no duplicar operaciones o retornos.

7. **Gap contra stop loss**
   - Si el precio cae por debajo del stop entre barras, el motor sale al precio observado de la barra.
   - Esto documenta una limitacion importante: no hay stop intradiario real.

8. **Capital menor al precio del activo**
   - El motor permite acciones fraccionarias.
   - La orden se dimensiona al cash disponible.
   - No debe quedar cash negativo ni posicion short.

9. **Equity, drawdown y long-only**
   - Verifica la contabilidad fila por fila.
   - Verifica drawdown contra maximos acumulados.
   - Verifica que no haya shares negativos.

10. **Benchmark alineado**
    - El benchmark tiene la misma cantidad de filas que la estrategia.
    - Sus metricas existen y se calculan sobre el mismo periodo.

## Reglas de ejecucion

El motor calcula la posicion deseada para la barra actual usando la senal de la barra anterior:

```text
desired_position[t] = signal[t - 1]
```

Por eso, una senal generada con datos disponibles al cierre de `t` recien puede ejecutarse en `t+1`. Esto es conservador para un laboratorio educativo y evita comprar usando informacion que no estaba disponible al momento de decidir.

## Costos

En una compra:

```text
execution_price = price * (1 + slippage)
entry_notional = cash_asignado / (1 + commission)
entry_commission = entry_notional * commission
shares = entry_notional / execution_price
```

En una venta:

```text
execution_price = price * (1 - slippage)
exit_notional = shares * execution_price
exit_commission = exit_notional * commission
cash_recibido = exit_notional - exit_commission
```

Esto hace que slippage y comisiones empeoren el resultado, nunca lo mejoren.

## Limitaciones conocidas

- No modela liquidez real.
- No modela spreads variables.
- No modela impacto de mercado.
- No modela fills parciales.
- Permite acciones fraccionarias.
- No valida lotes minimos del broker.
- Stop loss y take profit usan cierre de barra, no datos intradiarios.
- No modela impuestos.
- No modela dividendos separados ni eventos corporativos salvo lo que venga incluido en `adj_close`.
- No simula ordenes limit, stop market reales ni colas de ejecucion.

## Que cubre cada test

- `tests/test_backtest_correctness_audit.py`: smoke fuerte de la auditoria y golden tests especificos.
- `tests/test_backtesting.py`: comportamiento general del engine, riesgos, costos y validaciones.
- `tests/test_research_flow.py`: integracion simple de datos normalizados, estrategia y backtester.

## Interpretacion prudente

Si esta auditoria pasa, significa que los supuestos basicos del backtester estan siendo respetados. No significa que una estrategia sea buena. Tampoco significa que el resultado sea operable con dinero real.

Antes de operar en serio faltarian datos institucionales, broker real, paper trading real prolongado, reconciliacion, monitoreo, limites diarios, manejo de errores de red y revision de costos reales.

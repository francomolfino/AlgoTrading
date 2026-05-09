# Algorithmic Trading desde cero usando AlgoTrading Lab

Esta guia es un recorrido practico para aprender los conceptos basicos de
algorithmic trading mientras usas la app local de Streamlit.

No es una promesa de rentabilidad. No es una coleccion de estrategias magicas.
El objetivo es aprender a investigar con cuidado: datos, senales, backtests,
metricas, robustez, portfolio, riesgo y paper trading simulado.

## Como usar esta guia

Abri la app y segui los capitulos en orden.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py
```

La ruta recomendada es:

1. Data Manager.
2. Strategy Lab.
3. Backtest Runner.
4. Results Dashboard.
5. Experiment Explorer.
6. Robustness Lab.
7. Portfolio Lab.
8. Risk Manager.
9. Paper Trading Simulator.

Idea central: no intentes "encontrar una estrategia ganadora" al principio.
Primero aprende a reconocer cuando un resultado es debil, sospechoso o
directamente inutil.

## Mapa mental del sistema

Un sistema de trading algoritmico simple tiene esta cadena:

```text
datos historicos -> indicadores -> senales -> ordenes -> trades -> equity curve -> metricas -> validacion
```

En esta app:

- Data Manager trabaja con datos historicos.
- Strategy Lab transforma datos en senales.
- Backtest Runner convierte senales en una simulacion.
- Results Dashboard muestra la equity curve, drawdown, trades y metricas.
- Robustness Lab pregunta si el resultado sobrevive fuera del ejemplo exacto.
- Portfolio Lab mira varios activos juntos.
- Risk Manager limita exposicion y perdidas.
- Paper Trading Simulator prueba ejecucion simulada, no dinero real.

## 1. Datos OHLCV

Pantalla: Data Manager.

Antes de hablar de estrategias, necesitas entender los datos.

Una barra OHLCV representa un periodo de mercado. En datos diarios, una barra es
un dia.

- `open`: precio de apertura del periodo.
- `high`: precio maximo del periodo.
- `low`: precio minimo del periodo.
- `close`: precio de cierre.
- `adj_close`: cierre ajustado por dividendos y splits cuando la fuente lo provee.
- `volume`: cantidad operada.

Para acciones y ETFs, `adj_close` suele ser mejor para research historico porque
intenta corregir eventos como splits y dividendos. Para cripto puede ser igual o
muy parecido a `close`.

Ejercicio:

1. Abri Data Manager.
2. Descarga `SPY` desde `2015-01-01`.
3. Explora el archivo descargado.
4. Mira fecha inicial, fecha final, cantidad de filas y validacion.
5. Mira el grafico de precio y volumen.

Que estas aprendiendo:

- Si los datos estan vacios, duplicados o con columnas faltantes, el backtest no
  sirve.
- Si el periodo es muy corto, las metricas van a ser fragiles.
- Si hay gaps grandes, no siempre es error, pero hay que entenderlos.

Error comun: descargar datos y correr backtests sin mirar si las columnas son
validas.

## 2. Precio no es rendimiento

Pantalla: Data Manager y Results Dashboard.

El precio solo dice cuanto vale algo. El retorno dice cuanto cambio en porcentaje.

Ejemplo:

```text
100 -> 110 = +10%
1000 -> 1010 = +1%
```

Por eso comparamos estrategias con retornos y equity curves, no solo con precios.

Retorno diario aproximado:

```text
retorno = precio_hoy / precio_ayer - 1
```

Que estas aprendiendo:

- Un activo caro no necesariamente rindio mas.
- Una caida de 50% necesita una suba de 100% para volver al punto inicial.
- Las metricas de riesgo se calculan sobre retornos y equity, no solo sobre el
  precio del activo.

## 3. Que es una senal

Pantalla: Strategy Lab.

Una estrategia no compra directamente. Primero genera una senal.

En esta app usamos long-only al principio:

- `signal = 1`: la estrategia quiere estar comprada.
- `signal = 0`: la estrategia quiere estar fuera del mercado.

Una entrada ocurre cuando la senal pasa de `0` a `1`.
Una salida ocurre cuando pasa de `1` a `0`.

La tabla final de Strategy Lab muestra los datos historicos con columnas
auxiliares de la estrategia y la columna `signal`.

Ejercicio:

1. Abri Strategy Lab.
2. Elegi `SPY`.
3. Elegi `Buy and hold`.
4. Mira que la senal queda casi siempre en `1`.
5. Cambia a `Cruce de medias moviles`.
6. Usa media rapida `50` y media lenta `200`.
7. Mira entradas, salidas y exposicion.

Que estas aprendiendo:

- Strategy Lab no muestra rentabilidad.
- Strategy Lab solo muestra intencion.
- El backtester despues aplica ejecucion, costos, slippage y delay.

Error comun: ver una buena senal visual y asumir que la estrategia gana dinero.

## 4. Benchmark: buy and hold

Pantalla: Backtest Runner y Results Dashboard.

El primer backtest que deberias correr casi siempre es buy and hold.

Buy and hold significa:

```text
comprar al inicio y mantener hasta el final
```

Sirve como benchmark minimo. Si una estrategia activa rinde menos que buy and
hold, tiene que justificar por que existe. Tal vez reduce drawdown, reduce
exposicion o mejora estabilidad. Si no mejora nada importante, probablemente es
ruido.

Ejercicio:

1. Abri Backtest Runner.
2. Activo: `SPY`.
3. Estrategia: `Buy and hold`.
4. Capital inicial: `10000`.
5. Comision: `1 bps`.
6. Slippage: `2 bps`.
7. Guarda el experimento.
8. Revisa Results Dashboard.

Que mirar:

- Retorno total.
- CAGR.
- Max drawdown.
- Equity curve.
- Drawdown curve.

Pregunta importante:

```text
Habria tolerado emocionalmente y financieramente el peor drawdown?
```

## 5. Que es un backtest

Pantalla: Backtest Runner.

Un backtest es una simulacion historica de reglas.

No responde:

```text
Esto va a ganar dinero?
```

Responde algo mas humilde:

```text
Que habria pasado si estas reglas se hubieran aplicado a estos datos,
con estos costos y estos supuestos?
```

En la app, el backtester considera:

- Capital inicial.
- Senales long-only.
- Delay correcto para evitar usar el futuro.
- Comisiones.
- Slippage.
- Tamano de posicion.
- Cash.
- Equity curve.
- Trades.
- Drawdown.
- Benchmark buy and hold.

Terminos clave:

- Comision: costo explicito por operar.
- Slippage: diferencia entre precio esperado y precio ejecutado.
- Position sizing: porcentaje del capital usado por entrada.
- Equity: valor total de la cuenta simulada.
- Cash: dinero no invertido.

Error comun: correr con comision y slippage en cero y creer que ese resultado es
realista.

## 6. Como leer las metricas

Pantalla: Results Dashboard.

Orden recomendado:

1. Datos y periodo.
2. Benchmark.
3. Equity curve.
4. Max drawdown.
5. Numero de trades.
6. CAGR y retorno total.
7. Sharpe.
8. Trades individuales.

Metricas principales:

- Retorno total: cuanto cambio el capital desde inicio a fin.
- CAGR: retorno anualizado aproximado.
- Max drawdown: peor caida desde un maximo hasta un minimo posterior.
- Sharpe: retorno ajustado por volatilidad. Es aproximado y puede enganar.
- Win rate: porcentaje de trades ganadores.
- Numero de trades: tamano de muestra.
- Comisiones totales: cuanto se pago por operar.
- Exposicion: cuanto tiempo estuvo la estrategia en mercado.

Interpretaciones prudentes:

- Retorno alto con pocos trades es sospechoso.
- Sharpe demasiado alto puede indicar overfitting, bug o periodo excepcional.
- Win rate alto no garantiza buen sistema.
- Drawdown alto puede hacer inviable una estrategia aunque el retorno final sea
  bueno.
- Menos drawdown con mucho menos retorno no siempre es mejor; depende del
  objetivo.

Ejemplo:

```text
Estrategia A: +100% con -55% drawdown
Estrategia B: +65% con -18% drawdown
```

La A gano mas, pero pudo ser psicologica o financieramente imposible de sostener.
La B gano menos, pero quizas fue mas operable.

## 7. Primera estrategia activa: cruce de medias

Pantallas: Strategy Lab, Backtest Runner, Results Dashboard.

El cruce de medias moviles es una estrategia de tendencia simple.

Idea:

```text
Si la media rapida esta por encima de la media lenta, estar comprado.
Si no, estar fuera.
```

Parametros:

- Media rapida: reacciona mas rapido.
- Media lenta: define tendencia mas estable.

Ejercicio:

1. Strategy Lab.
2. Activo: `SPY`.
3. Estrategia: `Cruce de medias moviles`.
4. Media rapida: `50`.
5. Media lenta: `200`.
6. Mira las senales.
7. Backtest Runner.
8. Corre el backtest y guarda experimento.
9. Results Dashboard.
10. Comparalo contra buy and hold.

Que suele pasar:

- Puede evitar parte de grandes caidas.
- Puede entrar tarde.
- Puede salir tarde.
- Puede perder en mercados laterales por falsas senales.

Pregunta correcta:

```text
Mejora algo importante frente a buy and hold, o solo cambia la forma del riesgo?
```

## 8. RSI, breakout y filtro de tendencia

Pantalla: Strategy Lab.

RSI basico:

- Busca comprar cuando el activo parece sobrevendido.
- Puede fallar fuerte si el activo sigue cayendo.
- Es mas contrarian que tendencial.

Breakout:

- Compra cuando el precio supera maximos recientes.
- Intenta capturar tendencias nuevas.
- Puede sufrir falsas rupturas.

Filtro de tendencia:

- Usa una condicion extra para operar solo a favor de una tendencia mayor.
- Puede reducir operaciones malas.
- Tambien puede dejarte fuera de rebotes rapidos.

Ejercicio:

1. Proba cada estrategia en Strategy Lab.
2. Antes de correr backtest, mira entradas, salidas y exposicion.
3. Si hay muy pocas entradas, no saques conclusiones fuertes.
4. Corre un backtest por estrategia.
5. Comparalas en Experiment Explorer.

Regla prudente:

```text
No optimices parametros antes de entender como se comporta la estrategia base.
```

## 9. Errores que destruyen backtests

Estos errores son mas importantes que encontrar "la mejor estrategia".

### Lookahead bias

Usar informacion del futuro sin darte cuenta.

Ejemplo malo:

```text
Comprar hoy usando el cierre de hoy, como si lo hubieras conocido antes.
```

La app aplica delay en el backtester para reducir este riesgo, pero igual debes
pensar cada estrategia con cuidado.

### Overfitting

Ajustar parametros hasta que el pasado se vea perfecto.

Ejemplo:

```text
Probar 300 combinaciones y elegir la que mas gano.
```

Eso puede estar capturando ruido historico, no una regla robusta.

### Survivorship bias

Probar solo activos que sobrevivieron o fueron exitosos.

Ejemplo:

```text
Probar solo ETFs grandes actuales e ignorar activos que desaparecieron.
```

Con yfinance gratuito es dificil eliminar este sesgo por completo. Por eso hay
que ser humilde con las conclusiones.

### Costos irreales

Comisiones y slippage en cero suelen inflar resultados.

### Muestra chica

Una estrategia con 3 trades no es una estrategia validada. Es una anecdota.

## 10. Robustez

Pantalla: Robustness Lab.

La robustez pregunta:

```text
El resultado aparece solo en un caso exacto o sobrevive a cambios razonables?
```

Formas de revisar robustez:

- Train/test split.
- Walk-forward.
- Sensibilidad de parametros.
- Prueba multi-activo.
- Prueba por periodos de mercado.
- Comparacion contra benchmark.

In-sample:

```text
Periodo usado para elegir o ajustar parametros.
```

Out-of-sample:

```text
Periodo no usado para elegir parametros. Es mas importante.
```

Ejercicio:

1. Toma una estrategia que parezca buena.
2. Corre Robustness Lab.
3. Mira si funciona en train y test.
4. Mira si pequenas variaciones de parametros destruyen el resultado.

Senal de peligro:

```text
Solo una combinacion exacta funciona y todas las cercanas fallan.
```

## 11. Portfolio y correlaciones

Pantalla: Portfolio Lab.

Un portfolio combina varios activos.

Equal-weight significa:

```text
Mismo peso para cada activo.
```

Ejemplo con 4 activos:

```text
SPY: 25%
QQQ: 25%
BTC-USD: 25%
ETH-USD: 25%
```

Correlacion mide cuanto se mueven juntos dos activos.

- Cerca de `1`: se mueven parecido.
- Cerca de `0`: relacion debil.
- Cerca de `-1`: se mueven en sentido opuesto.

Para que sirve:

- Entender si estas realmente diversificando.
- Detectar activos que parecen distintos pero caen juntos.
- Evaluar riesgo agregado, no solo retorno individual.

Advertencia:

```text
La correlacion historica cambia. No es una ley fisica.
```

Ejercicio:

1. Descarga `SPY`, `QQQ`, `BTC-USD`, `ETH-USD`.
2. Abri Portfolio Lab.
3. Usa equal-weight.
4. Mira equity, drawdown y correlaciones.
5. Pregunta si el portfolio cae menos o solo combina riesgos parecidos.

## 12. Risk management

Pantalla: Risk Manager.

Risk management no convierte una mala estrategia en buena.

Sirve para definir limites:

- Cuanto capital usar por trade.
- Exposicion maxima.
- Drawdown maximo permitido.
- Stop loss.
- Take profit.
- Limite de trades por dia.
- Volatility targeting.

Idea clave:

```text
El objetivo de riesgo no es maximizar retorno, es evitar escenarios que no podes tolerar.
```

Ejercicio:

1. Elegi una estrategia con drawdown alto.
2. Comparala con y sin reglas de riesgo.
3. Mira si baja el drawdown.
4. Mira cuanto retorno resigna.
5. Decide si el intercambio tiene sentido.

Pregunta correcta:

```text
Esta regla reduce un riesgo real o solo esta maquillando el backtest?
```

## 13. Paper trading simulado

Pantalla: Paper Trading Simulator.

Paper trading no demuestra rentabilidad.

Sirve para probar:

- Generacion de senales.
- Creacion de ordenes.
- Estados de ordenes.
- Fills simulados.
- Cash.
- Posiciones.
- Logs.
- Errores.
- Reglas de riesgo.

Estados de orden:

- `created`: orden creada.
- `submitted`: enviada al broker simulado.
- `filled`: ejecutada.
- `rejected`: rechazada.
- `cancelled`: cancelada.

En esta app todo es simulacion. No se conecta dinero real.

Pregunta correcta:

```text
El sistema se comporta de forma trazable y controlada?
```

No preguntes todavia:

```text
Esto gana dinero real?
```

## Ejercicio completo de 90 minutos

Objetivo: aprender el flujo completo sin optimizar.

### Parte A: datos

1. Data Manager.
2. Descarga `SPY` desde `2015-01-01`.
3. Valida datos.
4. Mira precio y volumen.

### Parte B: benchmark

1. Backtest Runner.
2. `Buy and hold`.
3. Capital `10000`.
4. Comision `1 bps`.
5. Slippage `2 bps`.
6. Guarda como `spy_buy_hold_base`.

### Parte C: estrategia activa

1. Strategy Lab.
2. `Cruce de medias moviles`.
3. Rapida `50`, lenta `200`.
4. Mira senales.
5. Backtest Runner.
6. Guarda como `spy_sma_50_200`.

### Parte D: comparacion

1. Experiment Explorer.
2. Compara ambos experimentos.
3. Mira retorno, CAGR, drawdown y trades.
4. Pregunta:

```text
La estrategia activa mejora algo importante contra buy and hold?
```

### Parte E: robustez

1. Robustness Lab.
2. Usa la estrategia SMA.
3. Mira train/test.
4. Mira sensibilidad.
5. Pregunta:

```text
El resultado sobrevive fuera del periodo exacto?
```

### Parte F: conclusion escrita

Escribi 5 lineas:

- Que activo probe.
- Que periodo use.
- Que estrategia compare.
- Que metrica fue mejor.
- Que riesgo o duda queda abierta.

Si no podes escribir esas 5 lineas con claridad, todavia no entendiste el
experimento.

## Checklist antes de creer un backtest

No creas un resultado hasta revisar:

- Datos validos.
- Periodo suficientemente largo.
- Comparacion contra buy and hold.
- Costos no irreales.
- Slippage considerado.
- Numero de trades suficiente.
- Drawdown tolerable.
- Resultado out-of-sample razonable.
- Sensibilidad de parametros razonable.
- Prueba en mas de un activo si aplica.
- Sin optimizar demasiados parametros.
- Sin depender de una sola operacion excepcional.

## Mini glosario

- Activo: instrumento operable, como `SPY`, `QQQ` o `BTC-USD`.
- Barra: una observacion OHLCV de un periodo.
- Benchmark: referencia contra la cual comparas.
- Buy and hold: comprar y mantener.
- CAGR: retorno anualizado aproximado.
- Drawdown: caida desde un maximo previo.
- Equity curve: evolucion del valor de la cuenta.
- Exposicion: porcentaje de tiempo o capital en mercado.
- Indicador: calculo derivado del precio o volumen.
- Long: posicion comprada.
- Overfitting: ajustar demasiado al pasado.
- Paper trading: simulacion operativa sin dinero real.
- Position sizing: tamano de posicion.
- Senal: intencion de estar dentro o fuera.
- Sharpe: retorno ajustado por volatilidad.
- Slippage: diferencia entre precio esperado y ejecutado.
- Trade: entrada y salida completas.
- Walk-forward: evaluacion por ventanas sucesivas.

## Que falta antes de dinero real

Este proyecto sigue siendo educativo.

Antes de operar dinero real harian falta, como minimo:

- Broker paper real durante bastante tiempo.
- Datos live confiables.
- Calendario de mercado.
- Manejo de horarios y zonas horarias.
- Reconciliacion entre sistema y broker.
- Manejo de ordenes parciales.
- Monitoreo y alertas.
- Logs auditables.
- Limites diarios de perdida.
- Plan para fallas de internet, energia o broker.
- Validacion externa de la estrategia.

La habilidad importante no es creer rapido. Es aprender a desconfiar bien.

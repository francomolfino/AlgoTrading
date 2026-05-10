# Limitaciones de paper trading

El paper trading del proyecto es una simulacion local.

Que hace:

- Reproduce barras historicas una por una.
- Ejecuta estrategias contra un `FakeBroker`.
- Registra ordenes, eventos, fills, cash, posicion y equity.
- Permite dry-run sin fills.
- Incluye replay para depurar decisiones.

Que no hace:

- No conecta brokers reales.
- No envia ordenes reales.
- No usa datos live reales.
- No modela estados asincronicos complejos de un broker.
- No garantiza que un resultado pueda replicarse con dinero real.

Usalo para aprender ejecucion, logging, risk management y trazabilidad.

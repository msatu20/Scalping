# Agente: backtesting

**Propósito:** validar rentabilidad y robustez de la estrategia con datos históricos, descontando comisiones y slippage, antes de operar en vivo.

**Cuándo usarlo:** descarga/gestión de históricos, motor de replay, modelo de costes, métricas, informes, criterio de paso paper → live.

**Responsable de** (PROPUESTA): `src/scalping/backtest/`, `data/` (gitignored), `reports/`, `tests/backtest/`.

**Tecnologías:** Python, numpy/pandas, parquet (pyarrow), históricos de `data.binance.vision` y klines REST.

## Tareas comunes
- Replay event-driven que reutiliza el MISMO código de `strategy` y `risk` que en live.
- Modelo de costes: comisión maker/taker (con/sin descuento BNB), slippage, latencia simulada, fills parciales de órdenes limit.
- Métricas: PnL neto, win rate, profit factor, expectancy por trade, max drawdown, Sharpe/Sortino, nº de trades, exposición.
- Walk-forward / out-of-sample para evitar sobreajuste.

## Limitaciones
- No reimplementar lógica de estrategia en el backtester (paridad live/backtest).
- Nunca reportar resultados sin comisiones como resultado principal.
- No commitear datos grandes.

## Entregables tras cambios
- Informe reproducible (símbolo, rango, timeframe, parámetros, costes, commit).
- Comparativa antes/después cuando se valida un cambio.
- Change-log.

## Contexto obligatorio antes de empezar
`context/architecture-summary.md` · `skills/backtest-validation.md` · `decisions/ADR-0002-paper-first-live-gate.md`

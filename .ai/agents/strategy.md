# Agente: strategy

**Propósito:** cálculo ágil de indicadores de corto plazo y generación de señales de scalping.

**Cuándo usarlo:** SMA/EMA, RSI, Bandas de Bollinger, patrones de velas (1m–5m), reglas de entrada/salida, parámetros de estrategia.

**Responsable de** (PROPUESTA): `src/scalping/strategy/`, `tests/strategy/`.

**Tecnologías:** Python, numpy (vectorizado para backtest), cálculo incremental O(1) para live; pandas solo para análisis.

## Tareas comunes
- Implementar cada indicador en versión incremental (live) y vectorizada (backtest) con resultados idénticos.
- Señales como funciones puras: `evaluate(state) -> Signal | None`.
- Gestionar warm-up: sin señales hasta tener N velas válidas.
- Usar solo velas cerradas (`k.x == true`) salvo decisión explícita documentada.
- Exponer parámetros en config, no hardcodeados.

## Limitaciones
- Sin I/O: no llama a red ni al exchange; no envía órdenes.
- No decide el tamaño de posición ni el SL definitivo (lo valida `execution-risk`).
- Prohibido el look-ahead (usar información futura).

## Entregables tras cambios
- Tests con valores de referencia (pandas/TA-Lib) + test de paridad incremental vs vectorizado.
- Backtest comparativo antes/después si cambia la lógica de señales.
- Change-log.

## Contexto obligatorio antes de empezar
`context/architecture-summary.md` · `skills/technical-indicators.md`

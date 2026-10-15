# Infraestructura (T9, T15, T17, T11 parcial) + T20 TREND_BREAKOUT 15m–1h

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún; T18+T14 = `6f376d2`) |
| Agente(s) | execution-risk, strategy, backtesting |

## Archivos cambiados
- **T15** `src/scalping/execution/symbol_filters.py` (+ fixture real `tests/fixtures/binance_futures/exchange_info.json`, tests).
- **T9** `src/scalping/execution/rate_limit.py`; integrado en `market_data/rest_snapshot.py`, `market_data/feed.py` (`feed.rate_limiter`), `fetch_symbol_filters`.
- **T17** `src/scalping/core/broker.py` (Protocol `Broker`); `SimBroker` conforme (chequeo estático mypy + test).
- **T11** `FeedStats.latency_percentile` + p50/p90/p99 en `scripts/smoke_market_data.py`.
- `core/models.py`: `KlineInterval.M15`, `H1`, propiedad `.ms` (elimina 2 diccionarios duplicados); `StrategyType.TREND_BREAKOUT`.
- `strategy/indicators/atr.py` (ATR Wilder bit-idéntico), `strategy/signals/trend_breakout.py`.
- `backtest/store.py`: `resample_klines`, `resample_day`; `backtest/research.py` (helpers de informes).
- Scripts: `research_trend_breakout.py`, `resample_klines.py`.
- `.ai/decisions/ADR-0010-trend-breakout-preregistration.md`; `reports/2026-10-14-t20-trend-breakout-walk-forward.md`.
- Tests: `tests/execution/` (filtros 12, rate limit 7), `test_atr.py`, `test_trend_breakout.py`, `test_research.py`, resample, percentiles, Broker.

## Datos
- klines 1m BTCUSDT/ETHUSDT ampliadas a **2023-10-13..2026-10-12** (0 huecos); funding 3 años (3288 liquidaciones ETH).
- 15m/1h construidas desde 1m: **validación** 1m→5m vs Binance 5m en 12 meses × 2 símbolos: OHLC, tiempos y count **exactos**; volúmenes ±1e-11.

## Resumen técnico
- Filtros reales (BTC tick 0,10 / step 0,001 / minNotional 50; ETH tick 0,01 / minNotional 20); redondeo al lado seguro.
- Rate limiter: presupuesto 80 % de 2400/min, sincroniza con `X-MBX-USED-WEIGHT-1M`, 429 → pausa global (`Retry-After`), 418 → bloqueo + `IpBannedError`; serializa peticiones concurrentes.
- Latencia (red del trabajo): p50 223 · p90 226 · p99 331 · máx 668 ms.
- T20: pre-registro ADR-0010; 16 variantes {15m,1h}×N{20,55}×k{2,3}×R{2,3}; 4 trabajos (símbolo × intervalo) con `run_many`, 1,4 min.

## Resultado T20
| | trades | mean R | PF | t |
|---|---|---|---|---|
| **OOS walk-forward (33 tramos)** | 951 | **+0,023** | 1,03 | +0,41 |
| Mejor in-sample (1h-n20-k2-r3) | 1155 | +0,076 | 1,10 | +1,42 |
| Misma sin costes | 1155 | +0,149 | 1,21 | +2,80 |
- 16/16 variantes positivas sin costes (primera vez); 8/8 de 1 h positivas tras costes in-sample; 15 m negativas tras costes.
- OOS por año: 2024 +0,133 · 2025 −0,004 · 2026 −0,076. Por símbolo: ETH +0,102 · BTC −0,049. 18/33 tramos positivos.
- **No aprobada** (ADR-0008); dirección prometedora con potencia insuficiente (K21) y deterioro temporal (K22).

## Riesgo / impacto
- Ninguno operativo; infraestructura lista para paper trading cuando haya estrategia aprobada.

## Pruebas
- `pytest` → 262 passed · `ruff` OK · `mypy --strict` OK (44 archivos).

## Contexto actualizado
- `module-map`, `current-decisions`, `known-risks` (K3 mitigado, K19, K21, K22), `active-work`, `tasks/backlog.md` (T9/T15/T17/T20 hechos, T11 bloqueada por usuario, T21, T22).

## Tareas de seguimiento
- [ ] T21 — experimento con más potencia (decisión del usuario).
- [ ] T22 — runner de paper trading.
- [ ] T11 — VPS (usuario).
- [ ] Commit + push (pendiente de confirmación).

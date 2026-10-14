# T13 — Simulador de broker y primer backtest real

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún; señal = `73f54ca`) |
| Agente(s) | backtesting, execution-risk |

## Archivos cambiados
- `.ai/decisions/ADR-0007-sim-broker-fill-model.md` — nuevo.
- `src/scalping/backtest/sim_broker.py` — nuevo: `SimBroker`, `CostModel`, `PriceSource`, `TpStyle`, `Liquidity`, `ExitReason`, `Fill`, `ClosedTrade`.
- `src/scalping/backtest/funding.py` — nuevo: `fetch_funding_rates` (REST paginado), `save_funding`, `FundingSchedule`, `FundingEvent`.
- `src/scalping/backtest/engine.py` — nuevo: `Backtester`, `SizingParams`, `position_size`, `BacktestResult`.
- `src/scalping/backtest/metrics.py` — nuevo: `BacktestMetrics`, `compute_metrics`.
- `src/scalping/backtest/__init__.py` — exports.
- `scripts/run_backtest.py` — nuevo. `scripts/download_history.py` — `--funding` (y `--kinds` vacío permitido).
- `tests/backtest/test_sim_broker.py` (15), `tests/backtest/test_engine.py` (5) — nuevos.

## Motivo
T13: backtest con costes reales para evaluar MEAN_REVERSION y futuras estrategias.

## Resumen técnico
- Fills maker/taker diferenciados (0,02 % / 0,05 % desde settings), slippage taker en bps, post-only GTX, maker solo al atravesar, expiración por `expires_at`.
- SL/TP sobre aggTrades (preciso) o klines (pesimista); huecos ejecutan peor que el stop.
- Funding con mark price histórico; PnL neto en `Decimal`.
- Métricas: win rate, expectancy en R, profit factor, drawdown, comisiones/|bruto|, duración media, motivos de salida.
- Detalle de reglas: ADR-0007.

## Riesgo / impacto
- Sin órdenes reales. **Resultado: MEAN_REVERSION por defecto pierde el 99,9 % del capital en 89 días** → descartada en su forma actual (K18 confirmado, K8 materializado).

## Pruebas
- `pytest` → 204 passed (2,6 s) · `ruff` OK · `mypy --strict` OK (34 archivos).
- Tests con PnL exacto en `Decimal`: entrada taker + TP maker, SL con hueco, corto, post-only, maker al atravesar / al tocar, expiración, TP taker, ocupado + cierre final, funding largo/corto (con evento previo ignorado), klines (apertura siguiente, ambigüedad → SL, hueco, sin TP en vela de entrada, SL en vela de entrada, maker), backtest de punta a punta, costes reducen PnL, sizing con tope de apalancamiento, métricas.
- **Backtest real 89 días** (2026-07-16..10-12, BTCUSDT+ETHUSDT, klines, entrada taker, TP maker, 1 bp slippage, 0,5 % riesgo, funding real 267 liquidaciones/símbolo):
  | | BTCUSDT | ETHUSDT | Total (equity compartido) |
  |---|---|---|---|
  | Trades | 862 | 1468 | 2330 |
  | Win rate | 31,4 % | 33,5 % | 32,7 % |
  | Expectancy | −1,30 R | −1,06 R | −1,15 R |
  | Profit factor | 0,29 | 0,36 | 0,33 |
  | Bruto / comisiones / funding | −654,73 / −3745,32 / +4,62 | −771,92 / −4826,34 / +3,12 | −1426,65 / −8571,65 / +7,74 |
  | **Neto** | | | **−9990,56 USDT (−99,9 %)** |
- **Diagnóstico:** distancia mediana al stop 12 bps vs ~8 bps de coste ida y vuelta → comisiones ≈ 0,75 R de mediana por trade. Control sin costes: −0,04 R, PF 0,96 (sin ventaja ni antes de costes).
- **Precisión:** TRADES vs KLINES en 2 días: mismas 64 operaciones; neto −2111,93 vs −2110,93.

## Contexto actualizado
- `module-map`, `architecture-summary`, `current-decisions`, `known-risks` (K8, K18), `active-work`, `tasks/backlog.md`, `skills/backtest-validation.md`.

## Tareas de seguimiento
- [ ] T16 — Rediseño/investigación con walk-forward: stop mínimo ≥ 3× coste ida y vuelta, entradas maker, filtros de régimen, timeframes 3m/5m.
- [ ] T17 — `Broker` Protocol en `core` (sim y real comparten interfaz).
- [ ] T15 — Filtros de símbolo reales.
- [ ] Commit + push (pendiente de confirmación).

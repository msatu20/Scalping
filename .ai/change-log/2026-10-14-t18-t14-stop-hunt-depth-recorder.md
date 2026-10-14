# T18 STOP_HUNT_REBOUND (walk-forward 12 meses) + T14 grabador de depth

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún; T16 = `827d6e6`) |
| Agente(s) | strategy, backtesting, market-data |

## Archivos cambiados
- `.ai/decisions/ADR-0009-stop-hunt-rebound-preregistration.md` — nuevo (pre-registro; cerrado: rechazada).
- `src/scalping/strategy/orderflow.py` — nuevo: `AggressionTracker`.
- `src/scalping/strategy/signals/stop_hunt.py` — nuevo: `StopHuntReboundStrategy`, `StopHuntParams`.
- `src/scalping/backtest/engine.py` — `RunSpec`, `run_many` (N pares estrategia/broker en una pasada); `Backtester` usa `run_many`.
- `src/scalping/backtest/binance_vision.py` — **fix**: el semáforo cubre descarga + parseo + escritura (antes 13 GB de RAM).
- `src/scalping/market_data/feed.py` — `streams` personalizables, `feed.clock` expuesto.
- `src/scalping/market_data/depth_recorder.py` — nuevo: `DepthRecorder`, `RecorderConfig`, `load_depth`.
- `scripts/record_depth.py`, `scripts/research_stop_hunt.py` (reanudable con caché por tarea en `data/research/t18`), `scripts/start_background.ps1`, `scripts/stop_background.ps1` — nuevos.
- `reports/2026-10-14-t18-stop-hunt-walk-forward.md` — nuevo.
- Tests: `tests/strategy/test_stop_hunt.py` (9), `tests/market_data/test_depth_recorder.py` (4), + `run_many` en `test_engine.py`.

## Datos
- aggTrades BTCUSDT + ETHUSDT 2025-10-13..2026-10-12 (730 días, ~10 GB Parquet; ~2–2,6 M trades/día BTC en meses activos).
- Depth propio (top-20 cada 250 ms) desde 2026-10-14 05:13 UTC, con huecos: 07:33–10:42 UTC (reinicio por Windows Update + traslado) y cortes de red breves.

## Resumen técnico
- Hipótesis pre-registrada (ADR-0009): barrido de nivel de N velas + estallido de agresión (10 s vs media 1 h) + recuperación ≤ 60 s; stop ≥ 25 bps; TP = target_r × riesgo. Rejilla 16 variantes.
- Investigación: 24 tareas (símbolo × mes) × 32 specs (16 + control sin costes) con fuente TRADES (precisa); 230 min con 10 procesos.
- Incidencias: reinicio nocturno por Windows Update mató procesos → investigación hecha reanudable (caché por tarea) y scripts de arranque/parada desacoplados de Claude Code.

## Resultado
| | trades | mean R | PF | t |
|---|---|---|---|---|
| **OOS walk-forward (9 meses)** | 6474 | **−0,363** | 0,54 | **−24,48** |
| Mejor in-sample (lb30-k3-r1-maker) | 12147 | −0,329 | 0,57 | −31,20 |
| Misma, sin costes | 12147 | −0,061 | 0,89 | −6,23 |
| Taker sin costes (todas) | — | −0,005 … +0,016 | — | — |
- 9/9 meses de test negativos; 16/16 variantes negativas in-sample.
- **Sin ventaja bruta** (taker ≈ 0 sin costes); maker peor por selección adversa (K20). Costes ≈ 0,3–0,4 R/trade (K19).
- **STOP_HUNT_REBOUND descartada.**

## Riesgo / impacto
- Ninguno operativo. Tercer resultado negativo consistente (T13, T16, T18): la barrera de costes a 1–5 min es estructural → decisión de dirección (T20).

## Pruebas
- `pytest` → 229 passed · `ruff` OK · `mypy --strict` OK (38 archivos).
- Grabador probado en vivo (0 cruces, spread 1 tick, ~253 ms/muestra); `run_many` = backtests individuales (test); caché de investigación probada (2.ª ejecución "cached").

## Contexto actualizado
- `module-map`, `architecture-summary`, `current-decisions`, `known-risks` (K19, K20), `active-work`, `tasks/backlog.md` (T18 hecho, T19, T20).

## Tareas de seguimiento
- [ ] T20 — decidir dirección (usuario).
- [ ] Commit + push (pendiente de confirmación).

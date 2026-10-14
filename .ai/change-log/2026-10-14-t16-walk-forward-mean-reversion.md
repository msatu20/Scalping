# T16 — 12 meses de datos + walk-forward de MEAN_REVERSION

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún; T13 = `06e6941`) |
| Agente(s) | backtesting, strategy |

## Archivos cambiados
- `.ai/decisions/ADR-0008-research-protocol-walk-forward.md` — nuevo (protocolo pre-registrado y criterios para pasar a paper).
- `src/scalping/backtest/walk_forward.py` — nuevo: `TradeRecord`, `Stats` (incl. t-stat), `Fold`, `make_folds`, `add_months`, `walk_forward`.
- `src/scalping/strategy/signals/mean_reversion.py` — `min_stop_bps` (ensancha el stop estructural), filtro de régimen `max_trend_bps` con `EMA(trend_fast/trend_slow)`, rechazos `trend`/`trend_warmup`.
- `src/scalping/backtest/sim_broker.py` — `kline_interval`: el broker usa solo velas 1m como camino de precio.
- `src/scalping/backtest/engine.py` — `strategy_interval` (replay 1m + intervalo de la estrategia), `maker_offset_bps`, `SizingParams.compounding`, descarte `entry_outside_brackets`.
- `scripts/research_mean_reversion.py` — nuevo (24 variantes en paralelo + walk-forward + informe).
- `reports/2026-10-14-t16-mean-reversion-walk-forward.md` — nuevo (informe).
- Tests: `tests/backtest/test_walk_forward.py` (5), + 3 en `test_mean_reversion.py`, + 1 en `test_sim_broker.py`, + 2 en `test_engine.py`.

## Datos
- klines 1m: ampliado a **2025-10-13..2026-10-12** (365 días × 2 símbolos = 1 051 200 velas, **0 huecos**).
- klines 5m: mismo año (210 240 velas). fundingRate: mismo año (1095 liquidaciones/símbolo).

## Motivo
T16 autorizado: variantes con stops más amplios, entradas maker y filtros de régimen, evaluadas fuera de muestra.

## Resumen técnico
- Protocolo pre-registrado (ADR-0008): 24 variantes = {1m, 5m} × {taker, maker −2 bps} × {stop estructural & R:R≥1, stop ≥25 bps & R:R≥0,5, stop ≥40 bps & R:R≥0,5} × {sin filtro, |EMA50−EMA200| ≤ 50 bps}.
- Cada variante se backtestea una vez (12 meses, SimBroker pesimista, costes reales, funding, R sin capitalizar); walk-forward 3 m train → 1 m test, 9 tramos, selección por R medio en train (≥ 30 trades).
- Ejecución: 24 variantes en paralelo (12 procesos) en ~1 min.
- Bug detectado por las validaciones del core durante la investigación: entrada maker desplazada más allá de un stop estructural muy ajustado → ahora se descarta la señal (`entry_outside_brackets`) en vez de abortar.

## Resultado
| | trades | mean R | PF | t |
|---|---|---|---|---|
| **OOS walk-forward (9 meses)** | 2291 | **−0,185** | 0,70 | **−7,91** |
| Mejor in-sample (5m-maker-stop40-range) | 1746 | −0,172 | 0,74 | −5,96 |
| Misma, **sin costes** | 1746 | −0,023 | 0,96 | −0,81 |
- Los 9 tramos de test negativos; las 24 variantes negativas incluso in-sample.
- **Conclusión:** sin capacidad predictiva antes de costes → familia MEAN_REVERSION (RSI+BB) **descartada** según ADR-0008.

## Riesgo / impacto
- Ninguno operativo. Evita invertir más tiempo en optimizar una familia sin ventaja (sobreajuste, K18).

## Pruebas
- `pytest` → 215 passed · `ruff` OK · `mypy --strict` OK (35 archivos).

## Contexto actualizado
- `module-map`, `current-decisions`, `known-risks` (K18), `active-work`, `tasks/backlog.md`, `skills/backtest-validation.md`.

## Tareas de seguimiento
- [ ] Elegir la siguiente hipótesis con información distinta (ver opciones en `active-work.md`).
- [ ] Commit + push (pendiente de confirmación).

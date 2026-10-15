# T21 — TREND_BREAKOUT multi-activo 1h–4h desde 2020

| Campo | Valor |
|---|---|
| Fecha | 2026-10-15 |
| Rama | `main` (sin commit aún; infra + T20 = `8cdc726`) |
| Agente(s) | backtesting, strategy |

## Archivos cambiados
- `.ai/decisions/ADR-0011-multi-asset-trend-preregistration.md` — nuevo (pre-registro; cerrado: no aprobada).
- `src/scalping/backtest/binance_vision.py` — descargas **mensuales** (`monthly=True`, divididas en días; fallback diario), `repair_klines` (taker > volumen, con log).
- `src/scalping/backtest/store.py` — `resample_klines(strict=)`, `resample_day` tolerante a minutos ausentes, `available_segments`.
- `src/scalping/backtest/research.py` — `Criterion`, `evaluate_criteria`, `criteria_table` (veredicto mecánico).
- `src/scalping/core/models.py` — `KlineInterval.H4`.
- `scripts/research_trend_breakout.py` — `--intervals`, `--title`, trabajos por tramo continuo de datos, criterios; `scripts/download_history.py --monthly`; UTF-8 en salida de scripts de investigación; "USDS-M" en ayudas (cp1252).
- `reports/2026-10-15-t21-multi-asset-trend-walk-forward.md` — nuevo.
- Tests: mensual + fallback, reparación de klines, segmentos, resample tolerante, criterios.

## Datos
- Universo (regla en ADR-0011): BTC, ETH, XRP, ADA, LINK, LTC, BCH, TRX, XLM, ETC + EOS (deslistado 2025-05-21). 1m 2020-01..2026-10 (35 M filas nuevas, ~900 ficheros mensuales), funding ~7 400 liquidaciones/activo, 1h/4h remuestreadas.
- Huecos upstream: 2022-02-26..28 y 2022-04-01..02 (XRP, LTC, TRX, XLM) → tramos separados.
- Anomalías upstream reparadas: EOS 2023-11-14 y XRP 2023-11-30 (taker_buy > volumen).

## Resultado
| | trades | mean R | PF | t |
|---|---|---|---|---|
| **OOS walk-forward (78 tramos)** | 4277 | **+0,001** | 1,00 | +0,04 |
| Regla fija 4h-n20-k2-r2 (periodo completo, in-sample) | 4158 | +0,075 | 1,11 | +3,32 |
- Criterios ADR-0011: 2/7 cumplidos → **NO APROBADA**.
- Regla fija 4h-n20-k2-r2: positiva 7/7 años y 10/11 activos; supera Bonferroni (16 variantes). Hipótesis nueva → T23.
- Diagnóstico: la re-selección mensual (3 m train) persigue ruido (K24).

## Riesgo / impacto
- Ninguno operativo. K23 (supervivencia), K24 (selección), K25 (datos) registrados.

## Pruebas
- `pytest` → 266 passed · `ruff` OK · `mypy --strict` OK (44 archivos).

## Contexto actualizado
- `module-map`, `current-decisions`, `known-risks`, `active-work`, `tasks/backlog.md` (T21 hecho, T23).

## Tareas de seguimiento
- [ ] T23 — confirmación de la regla fija en activos no examinados (criterios a acordar con el usuario antes de ejecutar).
- [ ] Commit + push (pendiente de confirmación).

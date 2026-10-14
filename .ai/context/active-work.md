# Active work

## En curso
- (ninguna) — bloque 2026-10-14 sin commit todavía.

## Entorno
- Python 3.12.10 en `.venv` (`.venv/Scripts/python.exe`). Python del sistema = 3.7: usar siempre el del venv.
- Verificación: `.venv/Scripts/python.exe -m pytest` · `.venv/Scripts/ruff.exe check src tests` · `.venv/Scripts/mypy.exe`
- Tras cambiar dependencias: `.venv/Scripts/python.exe -m pip install -e ".[dev]"`

## Siguiente
1. T6 — Order book local (`market_data/order_book.py`): snapshot REST + deltas, validación `pu`, resync en `on_connected`, emisión de `OrderBookImbalance`.
2. T7 — Verificar URLs WS de futuros vigentes; prueba de humo manual contra stream real (solo lectura).
3. T5 — Descarga de históricos (klines 1m + aggTrades) a parquet.
4. `strategy/indicators`: SMA/EMA/RSI/Bollinger incremental + vectorizado.

## Hecho
- 2026-10-14 · T4 + settings + market_data (parser, streams, ws_client) (`change-log/2026-10-14-adr0004-settings-market-data.md`).
- 2026-10-13 · T1, T2, T3: proyecto inicial + modelos core + ADR-0003 (`change-log/2026-10-13-initial-setup-and-core-models.md`).
- 2026-10-13 · Framework `.ai/` + `CLAUDE.md` (`change-log/2026-10-13-bootstrap-ai-framework.md`).

# Active work

## En curso
- (ninguna) — T6 sin commit todavía.

## Entorno
- Python 3.12.10 en `.venv` (`.venv/Scripts/python.exe`). Python del sistema = 3.7: usar siempre el del venv.
- Verificación: `.venv/Scripts/python.exe -m pytest` · `.venv/Scripts/ruff.exe check src tests` · `.venv/Scripts/mypy.exe`
- Tras cambiar dependencias: `.venv/Scripts/python.exe -m pip install -e ".[dev]"`

## Siguiente
1. T10 + T7 — Runner `market_data/feed.py` (WS → cola → `OrderBookManager`) + verificación de URLs y prueba de humo real de solo lectura.
2. T9 — Gestor central de rate limits / ban 418.
3. T5 — Descarga de históricos (klines 1m + aggTrades) a parquet.
4. `strategy/indicators`: SMA/EMA/RSI/Bollinger incremental + vectorizado.

## Hecho
- 2026-10-14 · T6 order book local + manager + fetcher REST (`change-log/2026-10-14-t6-local-order-book.md`).
- 2026-10-14 · T4 + settings + market_data (parser, streams, ws_client) (`change-log/2026-10-14-adr0004-settings-market-data.md`) — commit `78c3364`.
- 2026-10-13 · T1, T2, T3: proyecto inicial + modelos core + ADR-0003 — commit `4dcf2c2`.
- 2026-10-13 · Framework `.ai/` + `CLAUDE.md` (`change-log/2026-10-13-bootstrap-ai-framework.md`).

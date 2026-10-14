# Active work

## En curso
- (ninguna) — bloque T5 sin commit todavía.

## Entorno
- Python 3.12.10 en `.venv` (`.venv/Scripts/python.exe`). Python del sistema = 3.7: usar siempre el del venv.
- Verificación: `.venv/Scripts/python.exe -m pytest` · `.venv/Scripts/ruff.exe check src tests scripts` · `.venv/Scripts/mypy.exe`
- Real (solo lectura, internet): `.venv/Scripts/python.exe -m pytest -m live_readonly` · `.venv/Scripts/python.exe scripts/smoke_market_data.py --seconds 120`
- Históricos: `.venv/Scripts/python.exe scripts/download_history.py --days 30 [--kinds klines|aggTrades]` → `data/futures_um/`
- Tras cambiar dependencias: `.venv/Scripts/python.exe -m pip install -e ".[dev]"`

## Datos disponibles (`data/`, gitignored)
- klines 1m BTCUSDT/ETHUSDT: 2026-07-16..2026-10-12 · aggTrades: 2026-10-11..2026-10-12

## Siguiente
1. `strategy/indicators`: SMA/EMA/RSI/Bollinger incremental + vectorizado (validables ya con las klines descargadas).
2. T12 — Replay de backtest (Parquet → eventos core, paridad con el feed live).
3. T9 — Gestor central de rate limits / ban 418.
4. T11 — Medir latencia desde VPS en Tokio antes de cualquier operativa live (K15).

## Hecho
- 2026-10-14 · T5: históricos a Parquet + validación de datos (ADR-0006, `change-log/2026-10-14-t5-historical-data-parquet.md`).
- 2026-10-14 · T10 + T7: `MarketDataFeed`, WS enrutado (ADR-0005), smoke real 120 s con 0 gaps — commit `0310eb1`.
- 2026-10-14 · T6 order book local + manager + fetcher REST — commit `db33537`.
- 2026-10-14 · T4 + settings + market_data (parser, streams, ws_client) — commit `78c3364`.
- 2026-10-13 · T1, T2, T3: proyecto inicial + modelos core + ADR-0003 — commit `4dcf2c2`.
- 2026-10-13 · Framework `.ai/` + `CLAUDE.md` (`change-log/2026-10-13-bootstrap-ai-framework.md`).

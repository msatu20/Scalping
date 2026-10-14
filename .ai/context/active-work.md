# Active work

## En curso
- (ninguna) — bloque T10+T7 sin commit todavía.

## Entorno
- Python 3.12.10 en `.venv` (`.venv/Scripts/python.exe`). Python del sistema = 3.7: usar siempre el del venv.
- Verificación: `.venv/Scripts/python.exe -m pytest` · `.venv/Scripts/ruff.exe check src tests` · `.venv/Scripts/mypy.exe`
- Real (solo lectura, internet): `.venv/Scripts/python.exe -m pytest -m live_readonly` · `.venv/Scripts/python.exe scripts/smoke_market_data.py --seconds 120`
- Tras cambiar dependencias: `.venv/Scripts/python.exe -m pip install -e ".[dev]"`

## Siguiente
1. T5 — Descarga de históricos (klines 1m + aggTrades) a parquet → base del backtesting.
2. `strategy/indicators`: SMA/EMA/RSI/Bollinger incremental + vectorizado.
3. T9 — Gestor central de rate limits / ban 418.
4. T11 — Medir latencia desde VPS en Tokio antes de cualquier operativa live (K15).

## Hecho
- 2026-10-14 · T10 + T7: `MarketDataFeed`, WS enrutado `/public`+`/market` (ADR-0005), smoke real 120 s con 0 gaps (`change-log/2026-10-14-t10-t7-feed-runner-live-verification.md`).
- 2026-10-14 · T6 order book local + manager + fetcher REST — commit `db33537`.
- 2026-10-14 · T4 + settings + market_data (parser, streams, ws_client) — commit `78c3364`.
- 2026-10-13 · T1, T2, T3: proyecto inicial + modelos core + ADR-0003 — commit `4dcf2c2`.
- 2026-10-13 · Framework `.ai/` + `CLAUDE.md` (`change-log/2026-10-13-bootstrap-ai-framework.md`).

# Active work

## En curso
- **Procesos en segundo plano (desacoplados de Claude Code):**
  - Grabador de depth T14 (`scripts/record_depth.py`, PID en `data/futures_um/depth/recorder.pid`, log `logs/depth_recorder.log`). Parar: crear `data/futures_um/depth/STOP`.
- Arranque/parada de procesos: `scripts/start_background.ps1` / `scripts/stop_background.ps1`.
- T14 + T18 sin commit.

## Entorno
- Python 3.12.10 en `.venv` (`.venv/Scripts/python.exe`). Python del sistema = 3.7: usar siempre el del venv.
- Verificación: `.venv/Scripts/python.exe -m pytest` · `.venv/Scripts/ruff.exe check src tests scripts` · `.venv/Scripts/mypy.exe`
- Real (solo lectura, internet): `.venv/Scripts/python.exe -m pytest -m live_readonly` · `.venv/Scripts/python.exe scripts/smoke_market_data.py --seconds 120`
- Históricos: `.venv/Scripts/python.exe scripts/download_history.py --days 30 [--kinds klines|aggTrades]` → `data/futures_um/`
- Tras cambiar dependencias: `.venv/Scripts/python.exe -m pip install -e ".[dev]"`

## Datos disponibles (`data/`, gitignored)
- klines 1m y 5m + fundingRate BTCUSDT/ETHUSDT: 2025-10-13..2026-10-12 (12 meses, 0 huecos) · aggTrades: 2025-10-13..2026-10-12 (completo, ~10 GB) · depth propio: desde 2026-10-14 05:13 UTC

## Siguiente
1. T20 — Decidir dirección (camino 2 depth / horizonte mayor / reducir costes / consolidar infraestructura) — decisión del usuario.
2. T17 — `Broker` Protocol en core; T15 filtros de símbolo.
3. T9 — Gestor central de rate limits / ban 418.
4. T11 — Medir latencia desde VPS en Tokio antes de cualquier operativa live (K15).

## Hecho
- 2026-10-14 · T18 STOP_HUNT_REBOUND descartada (OOS −0,363 R, t −24,5; sin costes ≈ 0) + T14 grabador de depth en marcha (`change-log/2026-10-14-t18-t14-stop-hunt-depth-recorder.md`).
- 2026-10-14 · T16 MEAN_REVERSION descartada — commit `827d6e6`.
- 2026-10-14 · T13 SimBroker + backtest real — commit `06e6941`.
- 2026-10-14 · Señal MEAN_REVERSION — commit `73f54ca`.
- 2026-10-14 · T12 replay de backtest — commit `fcb8fa6`.
- 2026-10-14 · Indicadores SMA/EMA/RSI/Bollinger bit-idénticos — commit `fe5c295`.
- 2026-10-14 · T5: históricos a Parquet + validación (ADR-0006) — commit `2b41f28`.
- 2026-10-14 · T10 + T7: `MarketDataFeed`, WS enrutado (ADR-0005), smoke real 120 s con 0 gaps — commit `0310eb1`.
- 2026-10-14 · T6 order book local + manager + fetcher REST — commit `db33537`.
- 2026-10-14 · T4 + settings + market_data (parser, streams, ws_client) — commit `78c3364`.
- 2026-10-13 · T1, T2, T3: proyecto inicial + modelos core + ADR-0003 — commit `4dcf2c2`.
- 2026-10-13 · Framework `.ai/` + `CLAUDE.md` (`change-log/2026-10-13-bootstrap-ai-framework.md`).

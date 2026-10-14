# ADR-0001 — Stack Python asyncio + Binance

- **Fecha:** 2026-10-13 · **Estado:** Aceptada

## Contexto
Bot de scalping sobre velas 1m–5m con WS en tiempo real, órdenes maker/taker y backtesting. Repo vacío.

## Decisión
- Python 3.12+ con asyncio; Binance Spot/USDⓈ-M Futures vía REST + WebSocket.
- Módulos: `market_data`, `strategy`, `execution`, `risk`, `backtest`, `config`, `core`.
- Tests con pytest/pytest-asyncio; calidad con ruff + mypy.

## Alternativas
- Rust/Go: menor latencia, mayor coste de desarrollo; innecesario para 1m–5m.
- Node/TS: viable, pero peor ecosistema numérico/backtesting.

## Consecuencias
- Cálculo numérico pesado vectorizado (numpy) en backtest; incremental en live.
- Si la latencia llega a ser cuello de botella → nuevo ADR (uvloop, procesos separados, etc.).

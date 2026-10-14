# Project overview

| Campo | Valor |
|---|---|
| Nombre | Scalping |
| Objetivo | Bot de scalping cripto automatizado sobre Binance (velas 1m–5m) |
| Lenguaje | Python 3.12+ (asyncio) |
| Exchange | Binance USDⓈ-M Futures (REST + WebSocket) — ADR-0003 |
| Pares | `BTCUSDT`, `ETHUSDT` |
| Repo | https://github.com/msatu20/Scalping · local `D:\Scalping` |
| Estado (2026-10-13) | Esqueleto + modelos `core` implementados; resto de módulos vacíos (ver `module-map.md`) |
| Modo por defecto | paper / testnet (ver ADR-0002) |

## Componentes
1. **Market data** — WS en tiempo real: order book, trades, klines; baja latencia.
2. **Strategy** — SMA/EMA, RSI, Bollinger, patrones de velas, imbalance del libro y order flow → señales `MEAN_REVERSION` / `STOP_HUNT_REBOUND` / `ORDER_FLOW_SQUEEZE`.
3. **Execution & Risk** — órdenes maker/taker, SL/TP, rate limits, kill-switch.
4. **Backtesting** — históricos, comisiones/slippage, métricas, gate a live.

## Prioridades
Seguridad del capital > corrección > paridad live/backtest > latencia > features.

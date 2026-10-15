# Current decisions

| ID | Fecha | Decisión | Estado |
|---|---|---|---|
| ADR-0001 | 2026-10-13 | Python 3.12 asyncio + Binance (REST/WS), arquitectura modular market_data/strategy/execution/risk/backtest | Aceptada |
| ADR-0002 | 2026-10-13 | Paper/testnet por defecto; gate explícito para pasar a live | Aceptada |
| — | 2026-10-13 | Agente único `execution-risk` (ejecución y riesgo acoplados) | Aceptada |
| — | 2026-10-13 | Misma lógica de strategy/risk en live y backtest (paridad) | Aceptada |
| ADR-0003 | 2026-10-13 | USDⓈ-M Futures, `BTCUSDT`/`ETHUSDT`, largo+corto, fees ref. 0,02 %/0,05 %, análisis de order book y order flow | Aceptada |
| — | 2026-10-13 | Modelos core = dataclasses frozen+slots; pydantic solo en config/bordes | Aceptada |
| — | 2026-10-13 | Notación de símbolo interna nativa Binance; ccxt solo dentro de `execution` | Aceptada |

| ADR-0004 | 2026-10-14 | ccxt solo para REST (en `execution`); cliente WS nativo `websockets` para market data | Aceptada |
| — | 2026-10-14 | Settings con pydantic-settings; live requiere `LIVE_TRADING_CONFIRMED=true`; apalancamiento ≤ 10 | Aceptada |
| — | 2026-10-14 | Cola WS con backpressure (no descartar deltas de depth) | Aceptada |
| — | 2026-10-14 | Resync solo por hueco/reconexión; latencia alta → libro no operable (no resync) | Aceptada |
| ADR-0005 | 2026-10-14 | WS enrutado: `/public` (depth) y `/market` (aggTrade, kline); una conexión por ruta | Aceptada |
| — | 2026-10-14 | Indicadores: paridad batch/incremental **bit a bit** (sumas izquierda→derecha, funciones de paso compartidas); EMA sembrada con SMA, RSI Wilder, Bollinger ddof=0 | Aceptada |
| — | 2026-10-14 | Replay: interfaz `MarketFeed` común live/backtest; reloj avanzado al consumir el evento; empate en ms → trades antes que kline; klines solo al cierre | Aceptada |
| — | 2026-10-14 | MEAN_REVERSION: setup (cierre fuera de banda + RSI extremo) → trigger re-entrada (CLOSE/TICK); TP = media, SL = extremo ∓ 5 bps; filtros objetivo ≥ 12 bps y R:R ≥ 1. Parámetros por defecto NO validados (K18) | Aceptada (provisional) |
| ADR-0007 | 2026-10-14 | SimBroker pesimista: maker solo al atravesar, SL al precio del trade que lo cruza ∓ slippage, ambigüedad en vela → SL, funding con mark price | Aceptada |
| — | 2026-10-14 | MEAN_REVERSION con parámetros por defecto **descartada** (backtest 89 días: −99,9 %, −1,15 R) | Aceptada |
| ADR-0008 | 2026-10-14 | Investigación: walk-forward pre-registrado (3 m train → 1 m test); criterio a paper: OOS mean R > 0 con t ≥ 2, PF ≥ 1,2, ≥ 200 trades | Aceptada |
| — | 2026-10-14 | **Familia MEAN_REVERSION (RSI+BB) descartada**: OOS −0,185 R (t −7,9); sin costes ≈ 0 R → sin capacidad predictiva | Aceptada |
| ADR-0009 | 2026-10-14 | **STOP_HUNT_REBOUND descartada**: OOS −0,363 R (t −24,5), 9/9 meses negativos; sin costes ≈ 0 R (taker) / −0,07 R (maker, selección adversa) | Aceptada |
| — | 2026-10-14 | Evidencia acumulada (T16+T18): a 1–5 min en BTC/ETH los costes ≈ 0,3–0,4 R/trade con stops 25–40 bps; ninguna señal probada tiene ventaja bruta | Aceptada |
| ADR-0010 | 2026-10-14 | Pre-registro TREND_BREAKOUT 15m–1h (36 meses, 16 variantes, walk-forward ADR-0008) | Aceptada |
| — | 2026-10-14 | Velas 15m/1h se construyen desde 1m (`resample_klines`): OHLC/tiempos/count exactos vs Binance 5m en 12 meses × 2 símbolos | Aceptada |
| — | 2026-10-14 | Paper trading = `SimBroker` (Protocol `Broker`) alimentado por `MarketDataFeed`; broker real solo con aprobación explícita | Aceptada |
| — | 2026-10-14 | **TREND_BREAKOUT no aprobada** (OOS +0,023 R, t +0,41; PF 1,03) pero primera familia con ventaja bruta (16/16 > 0 sin costes); horizonte 1h+ = dirección prometedora, falta potencia estadística | Aceptada |
| ADR-0011 | 2026-10-15 | TREND_BREAKOUT multi-activo 1h–4h 2020–2026: **NO APROBADA** (OOS walk-forward +0,001 R, t +0,04); la re-selección mensual persigue ruido; regla fija 4h-n20-k2-r2 = hipótesis a confirmar fuera de muestra | Aceptada |
| — | 2026-10-15 | Datos: anomalías upstream (taker > volumen) se recortan y se registran al ingerir (`repair_klines`) | Aceptada |
| ADR-0006 | 2026-10-14 | Históricos de data.binance.vision → Parquet diario zstd; float64 round-trip, ms int64; checksum obligatorio; días ausentes = error | Aceptada |

Pendientes de decidir: User Data Stream (ccxt.pro vs WS nativo) · almacenamiento de históricos · apalancamiento máx. · despliegue (VPS/región).

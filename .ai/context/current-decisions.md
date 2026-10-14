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
| ADR-0006 | 2026-10-14 | Históricos de data.binance.vision → Parquet diario zstd; float64 round-trip, ms int64; checksum obligatorio; días ausentes = error | Aceptada |

Pendientes de decidir: User Data Stream (ccxt.pro vs WS nativo) · almacenamiento de históricos · apalancamiento máx. · despliegue (VPS/región).

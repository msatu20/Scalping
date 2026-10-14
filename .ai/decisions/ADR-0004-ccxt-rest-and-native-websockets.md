# ADR-0004 — ccxt para REST, cliente WebSocket nativo para market data

- **Fecha:** 2026-10-14 · **Estado:** Aceptada · **Resuelve:** T4

## Contexto
Dos necesidades con perfiles opuestos:
- **REST** (cuenta, balances, posiciones, órdenes): baja frecuencia, crítico en corrección — firmas, `recvWindow`, rate limits, códigos de error.
- **Streams** (depth, aggTrade, kline): alta frecuencia, crítico en latencia y en control fino (secuencias `U`/`u`/`pu`, reconexión, detección de datos obsoletos).

## Decisión
| Capa | Librería | Ubicación | Motivo |
|---|---|---|---|
| REST | **ccxt** (async, `binanceusdm`) | `src/scalping/execution/` | Firma HMAC, sync de reloj, rate limiter y mapeo de errores probados |
| Market data WS | **`websockets`** nativo | `src/scalping/market_data/` | Sin capas intermedias; control total de reconexión, timeouts y parseo |

- El WS usa streams combinados: `wss://fstream.binance.com/stream?streams=btcusdt@depth@100ms/btcusdt@aggTrade/...`.
- El parser (`market_data/parser.py`) es puro y sin I/O: JSON crudo → modelos `core`. Testeable offline con fixtures.
- Snapshot REST del libro (`/fapi/v1/depth`) se obtiene vía ccxt *raw* (`fapiPublicGetDepth`) o aiohttp y se parsea con `parse_depth_snapshot`.
- Símbolos: notación nativa (`BTCUSDT`) en todo el sistema; la conversión a `BTC/USDT:USDT` queda encapsulada en `execution`.
- User Data Stream (fills): decidir en la fase de `execution` (ccxt `watch*` requiere ccxt.pro, incluido en ccxt ≥4; o WS nativo) → ADR posterior.

## Alternativas
- ccxt.pro para todo: más simple, pero añade abstracción y latencia en el hot path, y oculta `pu` / control de reconexión.
- Cliente REST propio: más control, pero reimplementa firma/rate limits (riesgos K2, K3, K6).
- `python-binance`: mantenimiento irregular, peor tipado.

## Consecuencias
- Dos fuentes de rate limit separadas: ccxt gestiona REST; las conexiones WS se limitan con backoff propio (máx. ~300 intentos de conexión / 5 min por IP).
- Verificar periódicamente las URLs WS de futuros en la documentación oficial (Binance ha anunciado separación de rutas por tipo de stream); se configuran en `config/settings.py`, no en el código.
- Parseo JSON con `json` de stdlib; migrar a `orjson` solo si un benchmark lo justifica (registrado en backlog).

# ADR-0005 — WebSocket enrutado: `/public` (libro) y `/market` (trades, velas)

- **Fecha:** 2026-10-14 · **Estado:** Aceptada · **Resuelve:** T7 · **Modifica:** ADR-0004

## Contexto
Verificación real (T7, 2026-10-14) contra `wss://fstream.binance.com`, contando eventos por ruta durante 8 s:

| URL | depth | aggTrade | kline |
|---|---|---|---|
| `/stream?streams=…` (legacy) | ✅ | ❌ 0 | ❌ 0 |
| `/public/stream?streams=…` | ✅ | ❌ | ❌ |
| `/market/stream?streams=…` | ❌ | ✅ | ✅ |

- La URL legacy **acepta la suscripción sin error pero no entrega** aggTrade ni kline (fallo silencioso).
- Confirmado por Binance, *Important WebSocket Change Notice* (USDⓈ-M Futures): rutas `/public` (bookTicker, depth), `/market` (aggTrade, kline, markPrice, ticker, forceOrder…), `/private` (user data por listenKey + events). Legacy `/ws` y `/stream` retiradas el 2026-04-23; sin ruta solo llega `/public`.
- Testnet (`fstream.binancefuture.com`): acepta legacy y rutas; el diseño enrutado funciona en ambos.

## Decisión
- `streams.route_of()` clasifica cada stream; `routed_stream_urls()` genera **una conexión por ruta**.
- `MarketDataFeed` abre dos `BinanceFuturesWsClient`: `/public` (depth, con `on_connected` → resync de libros) y `/market` (aggTrade, kline). Ambos alimentan la misma cola.
- `combined_stream_url()` rechaza streams mal enrutados (falla ruidosamente en vez de en silencio).
- User Data Stream futuro: `/private/stream?listenKey=…&events=…`.

## Consecuencias
- El orden relativo entre depth y trades no está garantizado (conexiones distintas): usar `event_time`, no orden de llegada.
- Una reconexión de `/market` no resetea libros; una de `/public` sí.
- Si Binance mueve un stream de ruta → `route_of` + test `test_route_of` a actualizar; el smoke test (`scripts/smoke_market_data.py`) lo detecta (contadores a 0).

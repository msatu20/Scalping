# Skill: binance-api

Integración con la API REST/WS de Binance. Verificar siempre contra la documentación oficial vigente (los límites cambian).

## Endpoints base
| Entorno | REST | WS mercado |
|---|---|---|
| Spot live | `https://api.binance.com` | `wss://stream.binance.com:9443` |
| Spot testnet | `https://testnet.binance.vision` | `wss://stream.testnet.binance.vision` |
| USDⓈ-M Futures | `https://fapi.binance.com` | `wss://fstream.binance.com` |
| Futures testnet | `https://testnet.binancefuture.com` | (ver docs) |
- URLs en config, nunca hardcodeadas en la lógica.

## Firma
- Endpoints `SIGNED`: `timestamp` + `recvWindow` (≤5000 ms recomendado) + `signature` HMAC-SHA256 (o Ed25519) sobre el query string.
- Header `X-MBX-APIKEY`. Sincronizar offset de reloj con `GET /api/v3/time`.

## Reglas de símbolo (`exchangeInfo`)
- `PRICE_FILTER.tickSize`, `LOT_SIZE.stepSize`, `NOTIONAL/MIN_NOTIONAL`. Cachear y refrescar periódicamente.
- Redondear con `Decimal.quantize` hacia el lado seguro (cantidad hacia abajo).

## Rate limits
- Headers `X-MBX-USED-WEIGHT-1M`, `X-MBX-ORDER-COUNT-10S/1D`.
- `429` → back-off con `Retry-After`; `418` → baneo IP: detener todo y alertar.
- Preferir WS para datos; REST solo para snapshot, órdenes y reconciliación.

## Órdenes
- Maker: `LIMIT_MAKER` (spot) / `timeInForce=GTX` (futuros). Taker: `MARKET`.
- `newClientOrderId` único e idempotente. Timeout ≠ fallo: consultar estado antes de reintentar.
- User Data Stream (listenKey, keepalive cada ~30 min) para fills y balances.

## Errores típicos
`-1021` timestamp fuera de ventana · `-1013`/`-1111` filtro/precisión · `-2010` saldo insuficiente/rechazo · `-1003` demasiadas peticiones.

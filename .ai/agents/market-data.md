# Agente: market-data

**Propósito:** ingesta de datos de mercado de Binance en tiempo real, con baja latencia y consistencia.

**Cuándo usarlo:** streams WS (depth, trade/aggTrade, kline, bookTicker), order book local, reconexión, heartbeats, medición de latencia, normalización de eventos.

**Responsable de** (PROPUESTA): `src/scalping/market_data/`, `tests/market_data/`.

**Tecnologías:** Python 3.12 asyncio, `websockets`, `orjson`, Binance Spot/USDⓈ-M Futures WS API.

## Tareas comunes
- Añadir o combinar streams (`/stream?streams=a/b/c`).
- Order book local: snapshot REST + diffs con `U`/`u`; detectar huecos y resincronizar.
- Reconexión con backoff exponencial + jitter; reconexión proactiva antes del corte de 24 h.
- Responder ping/pong; medir latencia (`E` del evento vs reloj local sincronizado).
- Publicar eventos tipados (dataclasses) hacia `strategy` mediante colas asyncio acotadas.

## Limitaciones
- Sin lógica de estrategia; nunca envía órdenes.
- No bloquear el event loop (nada de I/O síncrono ni cálculo pesado en el handler).
- No cambiar el contrato de eventos sin coordinar con `strategy` y `backtesting` (contrato compartido).

## Entregables tras cambios
- Tests: parseo, desconexión/reconexión, hueco de secuencia en el order book.
- Change-log; actualizar `context/module-map.md` y `context/architecture-summary.md` si cambia el contrato.

## Contexto obligatorio antes de empezar
`context/architecture-summary.md` · `context/known-risks.md` (MD) · `skills/websocket-streams.md`

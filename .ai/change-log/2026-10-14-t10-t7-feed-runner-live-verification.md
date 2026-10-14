# T10 + T7 — Runner de market data y verificación real (solo lectura)

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún; T6 = `db33537`) |
| Agente(s) | market-data |

## Archivos cambiados
- `.ai/decisions/ADR-0005-routed-ws-public-market.md` — nuevo.
- `src/scalping/market_data/streams.py` — `StreamRoute`, `route_of`, `routed_stream_urls`; `combined_stream_url(base, route, streams)` (**firma cambiada**).
- `src/scalping/market_data/feed.py` — nuevo: `MarketDataFeed`, `FeedStats`, `server_clock_offset_ms`.
- `src/scalping/market_data/ws_client.py` — `ReconnectPolicy.close_timeout_s=1.0`.
- `src/scalping/market_data/__init__.py` — exports.
- `scripts/smoke_market_data.py` — nuevo.
- `tests/market_data/test_streams.py` (reescrito), `test_feed.py` (nuevo), `tests/integration/test_live_binance_readonly.py` (nuevo).
- `pyproject.toml` — marcador `live_readonly`, excluido por defecto.

## Motivo
T10 (unir WS → cola → libros) y T7 (verificar endpoints reales).

## Resumen técnico
- **Hallazgo crítico (T7):** la URL legacy `/stream` solo entrega depth; aggTrade/kline se pierden **sin error**. Binance separó rutas (`/public`, `/market`, `/private`). Sin este cambio, la estrategia se habría quedado sin order flow ni velas → ADR-0005.
- **`MarketDataFeed`**: sincroniza reloj con `/fapi/v1/time` (offset compensando RTT/2), crea fetcher REST + `OrderBookManager`, un WS por ruta (solo `/public` resincroniza libros), consumidor único de la cola (`manager.handle`; resto → `on_event`), `FeedStats` (eventos, resultados de deltas, latencia media/máx, cola máx.), parada limpia con `TaskGroup`.
- **Bug corregido en vivo:** el cierre tardaba 17 s (handshake de cierre de Binance + `close_timeout` 10 s por cliente, en serie) → `close_timeout_s=1.0` y cierre concurrente → 1,0 s.

## Riesgo / impacto
- Solo lectura, sin claves, modo paper forzado en script/test.
- **Latencia observada desde este equipo: media ~365 ms, máx. 831 ms** (event_time → recepción, reloj alineado con el servidor; error del offset ≤ RTT/2). Con `max_latency_ms=500` el libro puede quedar momentáneamente no operable. Para scalping es una limitación seria → K15 / T11.

## Pruebas
- Unitarias/offline: `pytest` → 99 passed (0,8 s) · `ruff` OK · `mypy --strict` OK (19 archivos). Incluye feed de punta a punta contra servidores locales WS (`/public`, `/market`) + REST.
- **Real, solo lectura:** `pytest -m live_readonly` → 1 passed (20 s).
- **Smoke 120 s** (`scripts/smoke_market_data.py --seconds 120`), BTCUSDT + ETHUSDT:
  | Métrica | Valor |
  |---|---|
  | Libros | ambos SYNCED, `tradeable=True` al final |
  | Deltas aplicados / buffered | 2297 / 7 |
  | Gaps de secuencia | **0** |
  | Errores de parseo | **0** |
  | Reconexiones | 0 |
  | Snapshots REST | 2 (uno por símbolo) |
  | aggTrades / klines | 4175 / 567 |
  | Cola máx. | 194 |
  | Latencia media / máx. | 365 ms / 831 ms |

## Contexto actualizado
- `module-map`, `architecture-summary`, `known-risks` (K14 resuelto, K15 nuevo), `current-decisions`, `active-work`, `tasks/backlog.md`, `skills/binance-api.md`, `skills/websocket-streams.md`, `skills/testing.md`.

## Tareas de seguimiento
- [ ] T11 — Medir latencia desde VPS cercano a Binance (AWS ap-northeast-1, Tokio) y ajustar `max_latency_ms`.
- [ ] T9 — Rate limits / ban 418 (sigue pendiente).
- [ ] Commit + push de este bloque (pendiente de confirmación).

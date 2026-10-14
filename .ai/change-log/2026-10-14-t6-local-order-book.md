# T6 — Order book local con resincronización continua

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún) |
| Agente(s) | market-data |

## Archivos cambiados
- `src/scalping/market_data/order_book.py` — nuevo: `LocalOrderBook`, `OrderBookManager`, `ResyncPolicy`, `SyncState`, `DeltaResult`, `BookNotSyncedError`.
- `src/scalping/market_data/rest_snapshot.py` — nuevo: `make_snapshot_fetcher` (aiohttp, `GET /fapi/v1/depth`).
- `src/scalping/market_data/__init__.py` — exports.
- `tests/market_data/test_order_book.py`, `test_order_book_manager.py` — nuevos (21 tests).
- `.ai/skills/websocket-streams.md` — regla de puente para futuros.
- Repo: eliminado `tests/fixtures/.gitkeep` (commit del bloque T4).

## Motivo
T6: libro local fiable para imbalance/order flow; cerrar el riesgo K13 (decisión del usuario: no descartar deltas).

## Resumen técnico
- **`LocalOrderBook`** (sin I/O): máquina de estados `UNSYNCED → AWAITING_BRIDGE → SYNCED`.
  - Bufferiza deltas sin snapshot (buffer acotado, descarta los más antiguos).
  - `apply_snapshot`: descarta deltas con `u < lastUpdateId`; exige `U ≤ lastUpdateId+1` en el primero; si el snapshot es más antiguo que el buffer → `False` (re-fetch) conservando el buffer.
  - Continuidad en vivo por `pu == u_anterior`; hueco o libro cruzado → `reset` + `GAP` + delta al buffer.
  - Duplicados/antiguos → `STALE`. qty 0 elimina nivel. Poda amortizada de niveles lejanos (`max_levels_per_side`).
  - Lecturas (`best_bid/ask`, `snapshot(levels)`, `imbalance(levels)`) lanzan `BookNotSyncedError` si no está `SYNCED`.
- **`OrderBookManager`**: un libro por símbolo; `on_connected` (hook del WS) resetea y resincroniza todos; `handle(event)` aplica deltas y lanza resync si queda `UNSYNCED`; una sola tarea de resync por símbolo, reintentos con backoff+jitter (errores de red/HTTP o snapshot no enlazable).
- **K13:** `is_tradeable(symbol)` = `SYNCED` y latencia (`recv_time − event_time`) ≤ `max_latency_ms` (500 ms por defecto). Resincronizar NO reduce la latencia de un consumidor lento, por eso se bloquea la operativa en lugar de forzar snapshots (que además consumen peso REST, K3).

## Riesgo / impacto
- Sin órdenes. Estrategias deben consultar `is_tradeable` antes de usar el libro (R5).
- 429/418 en snapshot → `ClientResponseError` → backoff (máx. 10 s). Un 418 (ban) aún no detiene todo el sistema → backlog T9.

## Pruebas
- `pytest` → 88 passed (1,05 s) · `ruff check` OK · `ruff format` OK · `mypy --strict` OK (18 archivos).
- Casos: replay desde buffer, snapshot antiguo, espera de puente, hueco `pu`, libro cruzado, hueco durante replay, STALE, poda, buffer acotado, latencia; manager con fetcher falso (gate), errores de red, reconexión; fetcher REST contra servidor aiohttp local (incl. 429).

## Contexto actualizado
- `module-map`, `active-work`, `known-risks` (K13 mitigado), `architecture-summary`, `tasks/backlog.md`, `skills/websocket-streams.md`.

## Tareas de seguimiento
- [ ] T9: gestor central de rate limits/ban (418) compartido REST.
- [ ] T10: runner `market_data` (WS → cola → manager) + prueba de humo real (con T7).
- [ ] Commit + push de T6 (pendiente de confirmación).

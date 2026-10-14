# T12 — Motor de replay de backtest (Parquet → eventos core)

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún; indicadores = `fe5c295`) |
| Agente(s) | backtesting |

## Archivos cambiados
- `src/scalping/backtest/replay.py` — nuevo: `ReplayFeed`, `day_start_ms`.
- `src/scalping/core/feed.py` — nuevo: `MarketFeed` (Protocol `run`/`stop`, runtime-checkable), `EventHandler`.
- `src/scalping/core/clock.py` — `FixedClock.advance_to(ms)` (monótono; `advance` lo usa).
- `src/scalping/core/__init__.py`, `src/scalping/backtest/__init__.py` — exports.
- `tests/backtest/test_replay.py` — nuevo (10 tests).

## Motivo
T12: ejecutar el mismo código de estrategia en backtest y en vivo (paridad, ADR-0001/0002).

## Resumen técnico
- **Misma interfaz que el feed live:** `run()`/`stop()` (Protocol `MarketFeed`, también cumplido por `MarketDataFeed`), `on_event`, `stats: FeedStats`, cola `asyncio.Queue` acotada productor → consumidor. Camino rápido síncrono `replay(on_event)` con el mismo generador de eventos.
- **Orden determinista:** por tiempo; empate en el mismo ms → aggTrades antes que klines (un trade en el último ms de la vela pertenece a ella) → orden de símbolos → fila. `np.lexsort` por día; procesado día a día (memoria acotada).
- **Eventos:** `Kline` cerrada (`is_closed=True`) en `close_time`; `AggregatedTrade` en `transact_time`; `recv_time = event_time + latency_ms` (latencia simulada opcional). Precios `Decimal(repr(float))` = dígitos originales.
- **Integridad temporal:** `FixedClock.advance_to(recv_time)` justo antes de entregar cada evento al handler — en el **consumo**, no en la producción — así la cola nunca filtra tiempo futuro. El reloj no puede retroceder (`ValueError`).
- **Fail-fast:** `check_data()` lanza `MissingDataError` antes de emitir ningún evento.
- `request_stop()` (síncrono, usable desde el handler) / `stop()` (async).
- Sin riesgo de bloqueo: el centinela de fin solo se envía en terminación normal; un error del handler se propaga (`ExceptionGroup`) sin colgar el productor.

## Riesgo / impacto
- Sin efecto en trading. Limitación: sin datos de depth históricos → el replay no alimenta `OrderBookManager` (estrategias de libro requerirán otra fuente, p. ej. grabación propia del feed live).
- Sin actualizaciones intra-vela de klines en el replay (solo cierre); intra-vela vía aggTrades + `peek()`.

## Pruebas
- `pytest` → 172 passed (2,6 s) · `ruff` OK · `mypy --strict` OK (27 archivos).
- Tests: orden y desempates, modelos y Decimals exactos, reloj = `recv_time` en cada evento y monótono, latencia, `run()` async idéntico a `replay()` con cola de 2 (productor adelantado) sin fuga temporal, Protocol cumplido por live y replay, stop desde handler, fail-fast, validaciones, reloj hacia atrás, error del handler sin cuelgue.
- **Datos reales:**
  | Prueba | Resultado |
  |---|---|
  | Replay síncrono 2 días BTC+ETH (klines + aggTrades) | 3 009 805 eventos = filas Parquet, 11,5 s (262k ev/s), 0 violaciones de reloj |
  | Replay async (cola) 1 día | 2 043 434 eventos, 11,1 s (184k ev/s), cola máx. 9 999 |
  | 89 días de klines → `RSI(14)`/`BollingerBands(20,2)` incrementales vs batch sobre Parquet | **bit-idénticos** en BTCUSDT y ETHUSDT (128 160 velas, 1,6 s) |

## Contexto actualizado
- `module-map`, `architecture-summary`, `current-decisions`, `known-risks` (K17), `active-work`, `tasks/backlog.md`, `skills/backtest-validation.md`.

## Tareas de seguimiento
- [ ] T13 — Simulador de broker (`sim_broker`): fills maker/taker, comisiones (ADR-0003), slippage, funding.
- [ ] Primera señal `MEAN_REVERSION` + backtest de punta a punta.
- [ ] Commit + push (pendiente de confirmación).

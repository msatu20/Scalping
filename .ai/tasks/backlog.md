# Backlog técnico

Deuda, bugs detectados y trabajo pendiente. Formato: `templates/task.md`. No arreglar "de paso": registrar aquí.

### T1 — Bootstrap del proyecto Python
- **Área/chunk:** CORE · **Prioridad:** alta · **Origen:** repo vacío (2026-10-13)
- **Descripción:** `git init` + remoto GitHub, `.gitignore`, `pyproject.toml` (ruff, mypy, pytest, pytest-asyncio), `.env.example`, esqueleto `src/scalping/` y `tests/`.
- **Criterio de hecho:** `pytest -q` y `ruff check` pasan en el esqueleto; primer push a `main`.
- **Estado:** hecho (2026-10-13) — 27 tests OK, ruff y mypy limpios, primer push

### T2 — Modelos compartidos (CORE)
- **Área/chunk:** CORE · **Prioridad:** alta
- **Descripción:** `MarketEvent`, `Signal`, `OrderIntent`, protocolo `Broker`, reloj inyectable (ver `context/architecture-summary.md`).
- **Estado:** hecho (2026-10-13) salvo protocolo `Broker` (se define al empezar execution)

### T3 — Decidir spot vs futuros y símbolos iniciales
- **Área/chunk:** CFG · **Prioridad:** alta
- **Descripción:** condiciona tipos de orden, SL (OCO vs STOP_MARKET) y comisiones. Resultado → ADR-0003.
- **Estado:** hecho (2026-10-13) → ADR-0003

### T4 — Decidir cliente Binance (propio vs `python-binance` vs `ccxt`)
- **Área/chunk:** EXE/MD · **Prioridad:** media · Resultado → ADR.
- **Estado:** hecho (2026-10-14) → ADR-0004

### T5 — Descarga de históricos (klines 1m + aggTrades) a parquet
- **Área/chunk:** BT · **Prioridad:** media
- **Estado:** hecho (2026-10-14) → ADR-0006, `backtest/store.py`, `backtest/binance_vision.py`

### T6 — Order book local
- **Área/chunk:** MD · **Prioridad:** alta · **Origen:** change-log 2026-10-14
- **Descripción:** `market_data/order_book.py`: snapshot REST + deltas bufferizados, validación `pu`, resync en `on_connected` o hueco, niveles con qty 0 eliminados, `OrderBookImbalance` top-N.
- **Criterio de hecho:** tests con secuencias válidas, hueco → resync, reconexión → resync.
- **Estado:** hecho (2026-10-14) — `market_data/order_book.py`

### T7 — Verificar URLs WS de USDⓈ-M Futures
- **Área/chunk:** CFG/MD · **Prioridad:** alta · **Origen:** ADR-0004 / K14
- **Descripción:** contrastar `wss://fstream.binance.com/stream` y testnet con la documentación oficial vigente; prueba de humo de solo lectura (marcador `testnet`/manual).
- **Estado:** hecho (2026-10-14) — ver change-log t10-t7

### T8 — Benchmark `json` vs `orjson` en el parser
- **Área/chunk:** MD · **Prioridad:** baja · **Origen:** ADR-0004
- **Descripción:** medir µs/mensaje con fixtures; adoptar `orjson` solo si la mejora es relevante frente a la latencia de red.
- **Estado:** pendiente

### T9 — Gestor central de rate limits / ban (418)
- **Área/chunk:** EXE/MD · **Prioridad:** alta · **Origen:** change-log T6
- **Descripción:** componente compartido que lea `X-MBX-USED-WEIGHT-1M`, respete `Retry-After` y, ante 418, detenga todas las peticiones REST y pause la operativa. Usarlo en `rest_snapshot` y en `execution`.
- **Estado:** pendiente

### T10 — Runner de market data + prueba de humo
- **Área/chunk:** MD · **Prioridad:** alta · **Origen:** change-log T6
- **Descripción:** `market_data/feed.py` que conecte settings → streams → `BinanceFuturesWsClient(on_connected=manager.on_connected)` → cola → `OrderBookManager.handle`, con métricas (latencia, gaps, tamaño de cola). Prueba manual de solo lectura contra Binance (junto con T7).
- **Estado:** hecho (2026-10-14) — ver change-log t10-t7

### T11 — Latencia: medir desde VPS cercano a Binance
- **Área/chunk:** MD/EXE · **Prioridad:** alta (antes de live) · **Origen:** smoke 2026-10-14 (K15)
- **Descripción:** latencia event→recepción desde el equipo local: media ~365 ms, máx. 831 ms. Ejecutar `scripts/smoke_market_data.py --seconds 600` desde un VPS en AWS ap-northeast-1 (Tokio) y comparar; fijar `ResyncPolicy.max_latency_ms` según la distribución (p99).
- **Estado:** pendiente

### T12 — Replay de backtest (Parquet → eventos core)
- **Área/chunk:** BT · **Prioridad:** alta · **Origen:** change-log T5
- **Descripción:** `backtest/replay.py`: lee `HistoricalStore` por rango y emite `Kline` / `AggregatedTrade` (core) fusionados por tiempo, sin look-ahead (kline solo al cierre). Misma interfaz que el feed live (`on_event`) para paridad strategy live/backtest.
- **Estado:** hecho (2026-10-14) — `backtest/replay.py`, ver change-log t12

### T13 — Simulador de broker (sim_broker)
- **Área/chunk:** BT/RSK · **Prioridad:** alta · **Origen:** change-log T12
- **Descripción:** `backtest/sim_broker.py` que reciba `OrderIntent` y simule: fill maker (limit GTX: solo si el precio cruza, cola/probabilidad), fill taker (MARKET con slippage en ticks), SL/TP intra-vela con aggTrades, comisiones de `Settings` (maker 0,02 % / taker 0,05 %), funding cada 8 h. Debe implementar el futuro protocolo `Broker` (T2).
- **Estado:** hecho (2026-10-14) → ADR-0007, `backtest/sim_broker.py`, `engine.py`, `metrics.py`, `funding.py`

### T14 — Grabador de depth live a Parquet
- **Área/chunk:** MD/BT · **Prioridad:** media · **Origen:** K17
- **Descripción:** grabar snapshots + deltas del feed `/public` (o top-N del libro cada X ms) para poder backtestear estrategias de order book.
- **Estado:** en curso (2026-10-14) — grabando desde 05:13 UTC (`scripts/record_depth.py`); falta replay de depth para backtests (T19)

### T15 — Redondeo a filtros del símbolo (tickSize / stepSize / minNotional)
- **Área/chunk:** EXE · **Prioridad:** alta (antes de órdenes) · **Origen:** change-log señal MEAN_REVERSION
- **Descripción:** cargar `exchangeInfo` de USDⓈ-M y redondear precios de `OrderIntent` a `tickSize` (SL/TP hacia el lado seguro) y cantidades a `stepSize`; validar `minNotional`. Las `Signal` llevan precios sin redondear (p. ej. `81778.19045000001`).
- **Estado:** pendiente

### T16 — Investigación de MEAN_REVERSION con walk-forward
- **Área/chunk:** STR/BT · **Prioridad:** media · **Origen:** K18
- **Descripción:** T13 hecho: backtest −99,9 % (stop mediano 12 bps vs 8 bps de coste; sin costes −0,04 R). Separar in-sample / out-of-sample; exigir stop ≥ 3× coste ida y vuelta, entradas maker, filtros de régimen (bandwidth, tendencia EMA), SL por ATR, timeframes 3m/5m. Informe en `reports/`.
- **Estado:** hecho (2026-10-14) — familia descartada, ver `reports/2026-10-14-t16-mean-reversion-walk-forward.md`

### T17 — `Broker` Protocol en core
- **Área/chunk:** CORE/EXE · **Prioridad:** media · **Origen:** ADR-0007 (resto de T2)
- **Descripción:** Protocol común (`submit`, `on_event`/actualización de estado, `is_busy`, posiciones, cierre) que implementen `SimBroker` y el futuro broker real ccxt, para que el runner de estrategia sea idéntico en backtest, paper y live.
- **Estado:** pendiente

### T18 — Siguiente hipótesis de estrategia (información distinta a RSI/BB)
- **Área/chunk:** STR/BT/MD · **Prioridad:** alta · **Origen:** T16
- **Descripción:** elegir y pre-registrar (ADR-0008) una hipótesis basada en microestructura: (a) `STOP_HUNT_REBOUND` / agresión con aggTrades (requiere ampliar aggTrades a ≥ 6–12 meses, ~5–15 GB), o (b) order-book imbalance / `ORDER_FLOW_SQUEEZE` (requiere T14: grabar depth live semanas antes de poder backtestear).
- **Estado:** hecho (2026-10-14) — STOP_HUNT_REBOUND descartada (OOS −0,363 R, t −24,5), ver `reports/2026-10-14-t18-stop-hunt-walk-forward.md`

### T19 — Replay de depth grabado para backtests de order book
- **Área/chunk:** BT/MD · **Prioridad:** media · **Origen:** T14
- **Descripción:** emitir snapshots top-N grabados (`load_depth`) como eventos en `ReplayFeed`, fusionados por tiempo con aggTrades/klines, para backtestear `ORDER_FLOW_SQUEEZE` / imbalance cuando haya ≥ 4–6 semanas grabadas.
- **Estado:** pendiente

### T20 — Decidir dirección tras T16 + T18 (barrera de costes, K19)
- **Área/chunk:** STR · **Prioridad:** alta · **Origen:** T18
- **Descripción:** opciones: (a) camino 2 order-book imbalance con depth grabado (T19, semanas de datos); (b) subir horizonte (15m–4h, stops ≥ 100 bps → costes ≪ R); (c) reducir costes (tier VIP / BNB) y re-evaluar; (d) pausar investigación de señales y consolidar infraestructura (T15, T17, T9, T11).
- **Estado:** pendiente (decisión del usuario)

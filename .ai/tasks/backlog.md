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
- **Estado:** pendiente

### T6 — Order book local
- **Área/chunk:** MD · **Prioridad:** alta · **Origen:** change-log 2026-10-14
- **Descripción:** `market_data/order_book.py`: snapshot REST + deltas bufferizados, validación `pu`, resync en `on_connected` o hueco, niveles con qty 0 eliminados, `OrderBookImbalance` top-N.
- **Criterio de hecho:** tests con secuencias válidas, hueco → resync, reconexión → resync.
- **Estado:** hecho (2026-10-14) — `market_data/order_book.py`

### T7 — Verificar URLs WS de USDⓈ-M Futures
- **Área/chunk:** CFG/MD · **Prioridad:** alta · **Origen:** ADR-0004 / K14
- **Descripción:** contrastar `wss://fstream.binance.com/stream` y testnet con la documentación oficial vigente; prueba de humo de solo lectura (marcador `testnet`/manual).
- **Estado:** pendiente

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
- **Estado:** pendiente

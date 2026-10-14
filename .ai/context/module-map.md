# Module map

Leyenda: ✅ implementado · 🧱 esqueleto (`__init__.py` vacío) · 📐 PROPUESTA (no existe aún)

| Ruta | Estado | Responsabilidad | Agente | Chunk |
|---|---|---|---|---|
| `src/scalping/core/models.py` | ✅ | Enums (`Side`, `ExecutionStyle`, `StrategyType`, `KlineInterval`) y modelos: `Kline`, `PriceLevel`, `OrderBookSnapshot`, `OrderBookDelta`, `AggregatedTrade`, `OrderBookImbalance`, `Signal`, `OrderIntent`, alias `MarketEvent` | orchestrator | CORE |
| `src/scalping/core/clock.py` | ✅ | `Clock` (Protocol), `SystemClock` (offset servidor), `FixedClock` (tests/backtest) | orchestrator | CORE |
| `src/scalping/market_data/` | 🧱 | WS streams, order book local, reconexión | market-data | MD |
| `src/scalping/strategy/indicators/` | 🧱 | SMA/EMA/RSI/Bollinger incremental + vectorizado | strategy | STR |
| `src/scalping/strategy/patterns/` | 🧱 | Patrones de velas, detección de barridos de stops | strategy | STR |
| `src/scalping/strategy/signals.py` | 📐 | Reglas → `Signal` | strategy | STR |
| `src/scalping/execution/` | 🧱 | ccxt/REST firmado, órdenes, user data stream, rate limiter, conversión de símbolos ccxt | execution-risk | EXE |
| `src/scalping/risk/` | 🧱 | Tamaño, SL/TP, apalancamiento, límites, kill-switch | execution-risk | RSK |
| `src/scalping/config/` | 🧱 | Settings (pydantic + dotenv), modos, secretos vía env | execution-risk | CFG |
| `src/scalping/backtest/` | 🧱 | Replay, sim_broker, costes (fees + funding), métricas | backtesting | BT |
| `tests/core/test_models.py` | ✅ | Tests de invariantes de modelos | orchestrator | CORE |
| `tests/<modulo>/` | 🧱 | Espejo de `src/`; `tests/fixtures/` para payloads | (dueño del módulo) | — |
| `pyproject.toml` | ✅ | Dependencias, pytest, ruff, mypy | orchestrator | — |
| `.env.example` | ✅ | Variables requeridas (sin secretos) | execution-risk | CFG |
| `data/`, `reports/` | 📐 | Históricos (gitignored) e informes | backtesting | BT |
| `.ai/` | ✅ | Framework de IA | orchestrator | — |

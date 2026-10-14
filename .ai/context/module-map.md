# Module map

Leyenda: ✅ implementado · 🧱 esqueleto (`__init__.py` vacío) · 📐 PROPUESTA (no existe aún)

| Ruta | Estado | Responsabilidad | Agente | Chunk |
|---|---|---|---|---|
| `src/scalping/core/models.py` | ✅ | Enums (`Side`, `ExecutionStyle`, `StrategyType`, `KlineInterval`) y modelos: `Kline`, `PriceLevel`, `OrderBookSnapshot`, `OrderBookDelta`, `AggregatedTrade`, `OrderBookImbalance`, `Signal`, `OrderIntent`, alias `MarketEvent` | orchestrator | CORE |
| `src/scalping/core/clock.py` | ✅ | `Clock` (Protocol), `SystemClock` (offset servidor), `FixedClock` (tests/backtest; `advance_to` monótono) | orchestrator | CORE |
| `src/scalping/market_data/parser.py` | ✅ | JSON crudo (raw/combinado) → `OrderBookDelta`/`AggregatedTrade`/`Kline`; REST depth → `OrderBookSnapshot`; `ParseError` | market-data | MD |
| `src/scalping/market_data/streams.py` | ✅ | Nombres de streams, `StreamRoute` (`/public` libro, `/market` trades/velas), `route_of`, `routed_stream_urls` (ADR-0005) | market-data | MD |
| `src/scalping/market_data/feed.py` | ✅ | `MarketDataFeed` (runner: reloj alineado, 2 WS por ruta → cola → `OrderBookManager` / `on_event`), `FeedStats` | market-data | MD |
| `scripts/smoke_market_data.py` | ✅ | Smoke test real de solo lectura con informe periódico | market-data | MD |
| `src/scalping/market_data/ws_client.py` | ✅ | `BinanceFuturesWsClient` + `ReconnectPolicy`: backoff+jitter, stale timeout, reconexión 23 h, `on_connected`, cola con backpressure | market-data | MD |
| `src/scalping/market_data/order_book.py` | ✅ | `LocalOrderBook` (estados UNSYNCED/AWAITING_BRIDGE/SYNCED, `pu`, poda, lecturas solo si SYNCED) + `OrderBookManager` (resync con backoff, `on_connected`, `is_tradeable` por latencia) | market-data | MD |
| `src/scalping/market_data/rest_snapshot.py` | ✅ | `make_snapshot_fetcher` (aiohttp, `/fapi/v1/depth`) | market-data | MD |
| `src/scalping/strategy/indicators/` | ✅ | `sma`/`SMA`, `ema`/`EMA`, `rsi`/`RSI`, `bollinger`/`BollingerBands`: batch (numpy) + incremental (`update`/`peek`), bit-idénticos (`_core.py`) | strategy | STR |
| `src/scalping/strategy/patterns/` | 🧱 | Patrones de velas, detección de barridos de stops | strategy | STR |
| `src/scalping/strategy/signals/base.py` | ✅ | Protocol `SignalGenerator.on_event(event) -> Signal \| None` | strategy | STR |
| `src/scalping/strategy/signals/mean_reversion.py` | ✅ | `MeanReversionStrategy` (RSI+BB, setup → re-entrada, modos CLOSE/TICK, filtros fees y R:R) | strategy | STR |
| `scripts/run_signals.py` | ✅ | Señales sobre replay + diagnóstico preliminar de primer toque | strategy | STR |
| `src/scalping/execution/` | 🧱 | ccxt/REST firmado, órdenes, user data stream, rate limiter, conversión de símbolos ccxt | execution-risk | EXE |
| `src/scalping/risk/` | 🧱 | Tamaño, SL/TP, apalancamiento, límites, kill-switch | execution-risk | RSK |
| `src/scalping/config/settings.py` | ✅ | `Settings` (pydantic-settings, inmutable), `TradingMode`, `HARD_MAX_LEVERAGE`=10, URLs por modo, guardas paper/testnet/live | execution-risk | CFG |
| `src/scalping/backtest/store.py` | ✅ | `HistoricalStore` (Parquet diario, escritura atómica, `load` falla si faltan días), `find_kline_gaps` | backtesting | BT |
| `src/scalping/backtest/binance_vision.py` | ✅ | `BinanceVisionDownloader` (checksum SHA-256, reintentos, idempotente), `parse_daily_zip` | backtesting | BT |
| `scripts/download_history.py` | ✅ | CLI de descarga (`--days`, `--start/--end`, `--kinds`) | backtesting | BT |
| `src/scalping/backtest/replay.py` | ✅ | `ReplayFeed`: Parquet → `Kline`/`AggregatedTrade` ordenados; `replay()` síncrono y `run()` con cola (misma interfaz que live); reloj avanzado al consumir | backtesting | BT |
| `src/scalping/core/feed.py` | ✅ | Protocol `MarketFeed` (`run`/`stop`) común a live y replay; `EventHandler` | orchestrator | CORE |
| `src/scalping/backtest/` (sim_broker, métricas) | 📐 | sim_broker, costes (fees + funding), métricas | backtesting | BT |
| `tests/core/test_models.py` | ✅ | Tests de invariantes de modelos | orchestrator | CORE |
| `tests/config/`, `tests/market_data/` | ✅ | Settings; parser (fixtures), streams, ws_client (servidor WS local), order_book + manager + fetcher REST (servidor aiohttp local) | dueño del módulo | CFG/MD |
| `tests/integration/` | ✅ | Tests reales `@pytest.mark.live_readonly` (excluidos por defecto) | market-data | MD |
| `tests/conftest.py` + `tests/fixtures/binance_futures/` | ✅ | Fixture `binance_raw(name)` + payloads reales de ejemplo | market-data | MD |
| `tests/<modulo>/` | 🧱 | Espejo de `src/`; `tests/fixtures/` para payloads | (dueño del módulo) | — |
| `pyproject.toml` | ✅ | Dependencias, pytest, ruff, mypy | orchestrator | — |
| `.env.example` | ✅ | Variables requeridas (sin secretos) | execution-risk | CFG |
| `data/futures_um/` | ✅ | Históricos Parquet (gitignored): klines 1m 2026-07-16..10-12, aggTrades 10-11..10-12 | backtesting | BT |
| `reports/` | 📐 | Informes de backtest | backtesting | BT |
| `.ai/` | ✅ | Framework de IA | orchestrator | — |

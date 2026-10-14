# Module map

Leyenda: ✅ implementado · 🧱 esqueleto (`__init__.py` vacío) · 📐 PROPUESTA (no existe aún)

| Ruta | Estado | Responsabilidad | Agente | Chunk |
|---|---|---|---|---|
| `src/scalping/core/models.py` | ✅ | Enums (`Side`, `ExecutionStyle`, `StrategyType`, `KlineInterval`) y modelos: `Kline`, `PriceLevel`, `OrderBookSnapshot`, `OrderBookDelta`, `AggregatedTrade`, `OrderBookImbalance`, `Signal`, `OrderIntent`, alias `MarketEvent` | orchestrator | CORE |
| `src/scalping/core/clock.py` | ✅ | `Clock` (Protocol), `SystemClock` (offset servidor), `FixedClock` (tests/backtest; `advance_to` monótono) | orchestrator | CORE |
| `src/scalping/market_data/parser.py` | ✅ | JSON crudo (raw/combinado) → `OrderBookDelta`/`AggregatedTrade`/`Kline`; REST depth → `OrderBookSnapshot`; `ParseError` | market-data | MD |
| `src/scalping/market_data/streams.py` | ✅ | Nombres de streams, `StreamRoute` (`/public` libro, `/market` trades/velas), `route_of`, `routed_stream_urls` (ADR-0005) | market-data | MD |
| `src/scalping/market_data/depth_recorder.py` | ✅ | T14: muestrea top-20 del libro sincronizado cada 250 ms → Parquet cada 10 min; parada con fichero `STOP`; `load_depth` | market-data | MD |
| `scripts/record_depth.py` | ✅ | Grabador de depth (proceso desacoplado, log en `logs/depth_recorder.log`) | market-data | MD |
| `scripts/research_stop_hunt.py` | ✅ | T18: 16 variantes × (símbolo, mes) con `run_many`, walk-forward + control sin costes | backtesting | BT |
| `src/scalping/market_data/feed.py` | ✅ | `MarketDataFeed` (runner: reloj alineado, 2 WS por ruta → cola → `OrderBookManager` / `on_event`), `FeedStats` | market-data | MD |
| `scripts/smoke_market_data.py` | ✅ | Smoke test real de solo lectura con informe periódico | market-data | MD |
| `src/scalping/market_data/ws_client.py` | ✅ | `BinanceFuturesWsClient` + `ReconnectPolicy`: backoff+jitter, stale timeout, reconexión 23 h, `on_connected`, cola con backpressure | market-data | MD |
| `src/scalping/market_data/order_book.py` | ✅ | `LocalOrderBook` (estados UNSYNCED/AWAITING_BRIDGE/SYNCED, `pu`, poda, lecturas solo si SYNCED) + `OrderBookManager` (resync con backoff, `on_connected`, `is_tradeable` por latencia) | market-data | MD |
| `src/scalping/market_data/rest_snapshot.py` | ✅ | `make_snapshot_fetcher` (aiohttp, `/fapi/v1/depth`) | market-data | MD |
| `src/scalping/strategy/indicators/` | ✅ | `sma`/`SMA`, `ema`/`EMA`, `rsi`/`RSI`, `bollinger`/`BollingerBands`: batch (numpy) + incremental (`update`/`peek`), bit-idénticos (`_core.py`) | strategy | STR |
| `src/scalping/strategy/patterns/` | 🧱 | Patrones de velas, detección de barridos de stops | strategy | STR |
| `src/scalping/strategy/signals/base.py` | ✅ | Protocol `SignalGenerator.on_event(event) -> Signal \| None` | strategy | STR |
| `src/scalping/strategy/signals/stop_hunt.py` | ✅ | `StopHuntReboundStrategy` (T18, ADR-0009): barrido de nivel + estallido de agresión + recuperación rápida, tick a tick | strategy | STR |
| `src/scalping/strategy/orderflow.py` | ✅ | `AggressionTracker`: notional agresivo por lado en ventana vs media de la última hora, O(1)/trade | strategy | STR |
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
| `src/scalping/backtest/sim_broker.py` | ✅ | `SimBroker` (ADR-0007): maker/taker, slippage, post-only, SL/TP sobre trades o klines (pesimista), funding, PnL `Decimal` | backtesting | BT |
| `src/scalping/backtest/funding.py` | ✅ | Funding histórico (REST, con mark price) → Parquet; `FundingSchedule` | backtesting | BT |
| `src/scalping/backtest/engine.py` | ✅ | `run_many` + `RunSpec` (N estrategia/broker en una pasada del replay), `Backtester` (1 spec), sizing fraccional fijo | backtesting | BT |
| `src/scalping/backtest/metrics.py` | ✅ | `compute_metrics` (R, PF, drawdown, comisiones/bruto) | backtesting | BT |
| `scripts/run_backtest.py` | ✅ | Backtest MEAN_REVERSION por CLI | backtesting | BT |
| `src/scalping/backtest/walk_forward.py` | ✅ | Walk-forward (ADR-0008): `make_folds`, `walk_forward`, `Stats` (R, PF, t-stat) | backtesting | BT |
| `scripts/research_mean_reversion.py` | ✅ | T16: 24 variantes en paralelo + walk-forward + informe en `reports/` | backtesting | BT |
| `reports/` | ✅ | Informes de investigación (versionados), p. ej. T16 | backtesting | BT |
| `tests/core/test_models.py` | ✅ | Tests de invariantes de modelos | orchestrator | CORE |
| `tests/config/`, `tests/market_data/` | ✅ | Settings; parser (fixtures), streams, ws_client (servidor WS local), order_book + manager + fetcher REST (servidor aiohttp local) | dueño del módulo | CFG/MD |
| `tests/integration/` | ✅ | Tests reales `@pytest.mark.live_readonly` (excluidos por defecto) | market-data | MD |
| `tests/conftest.py` + `tests/fixtures/binance_futures/` | ✅ | Fixture `binance_raw(name)` + payloads reales de ejemplo | market-data | MD |
| `tests/<modulo>/` | 🧱 | Espejo de `src/`; `tests/fixtures/` para payloads | (dueño del módulo) | — |
| `pyproject.toml` | ✅ | Dependencias, pytest, ruff, mypy | orchestrator | — |
| `.env.example` | ✅ | Variables requeridas (sin secretos) | execution-risk | CFG |
| `data/futures_um/` | ✅ | Históricos Parquet (gitignored): klines 1m y 5m + fundingRate 2025-10-13..2026-10-12; aggTrades 2026-10-11..12 | backtesting | BT |
| `.ai/` | ✅ | Framework de IA | orchestrator | — |

# Architecture summary

Estado: contratos (`core`) implementados; flujos y módulos aún PROPUESTA.

## Flujo live
```
Binance WS ──► market_data ──(MarketEvent: Kline/Trade/BookUpdate)──► strategy
                                                                        │ Signal
                                                                        ▼
Binance REST ◄── execution ◄──(OrderIntent aprobado)── risk ◄───────────┘
      │                                                  ▲
      └── User Data Stream (fills, balances) ────────────┘ (estado de posiciones/PnL)
```

## Flujo backtest
Datos (✅, ADR-0006): `scripts/download_history.py` → `BinanceVisionDownloader` (checksum) → `HistoricalStore` → `data/futures_um/…/<día>.parquet`; lectura con `HistoricalStore.load(kind, symbol, start, end)`.
```
data/ (parquet) ──► backtest.replay (📐 T12) ──(MarketEvent)──► strategy ──► risk ──► backtest.sim_broker
                                                                              (comisión, slippage, fills)
                                                                    ──► metrics ──► reports/
```
- `strategy` y `risk` son el MISMO código en live y backtest; solo cambian la fuente de eventos y el broker.

## Contratos (`src/scalping/core/models.py` — ✅ implementados)
| Contrato | Productor → Consumidor | Contenido / invariantes |
|---|---|---|
| `MarketEvent` = `Kline \| OrderBookSnapshot \| OrderBookDelta \| AggregatedTrade` | market_data/replay → strategy | ts ms; precios `Decimal` |
| `OrderBookImbalance` | strategy (derivado de snapshot) | `value` ∈ [-1, 1], top-N niveles |
| `Signal` | strategy → risk | `StrategyType`, precio ref., SL/TP validados por lado, `reward_risk` |
| `OrderIntent` | risk → execution/sim_broker | `ExecutionStyle`, qty, entry, **SL+TP obligatorios**, `client_order_id` Binance-válido |
| `Clock` (`core/clock.py`) | todos | `now_ms()`; `FixedClock` en tests/backtest |
| `Broker` (protocolo) | execution / sim_broker | PROPUESTA: `place`, `cancel`, `get_order`, `positions` |

## Concurrencia
- Un event loop asyncio; colas acotadas entre etapas; nada bloqueante en handlers.
- Tareas: ws_market, ws_user, strategy_loop, risk_monitor (kill-switch), rate_limiter.

## Market data (✅ parcial)
`MarketDataFeed` (`feed.py`, ✅):
```
/public WS (depth) ──┐                    ┌─► OrderBookManager.handle (deltas)
                     ├─► asyncio.Queue ───┤
/market WS (aggTrade,┘                    └─► on_event (klines, aggTrades → strategy)
          kline)
```
- Rutas obligatorias (ADR-0005): legacy `/stream` solo entrega depth.
- Solo el WS `/public` llama `manager.on_connected` (reset + resync de libros).
- Reloj alineado con `/fapi/v1/time` al arrancar (latencia = `recv_time − event_time`).
- Snapshot REST vía `rest_snapshot.make_snapshot_fetcher` (aiohttp).
- Strategy lee `manager.books[s].imbalance(n)` / `snapshot(n)` solo si `manager.is_tradeable(s)`.
- Orden entre depth y trades no garantizado (dos conexiones): ordenar por `event_time`.

## Configuración (✅)
- `config/settings.py`: `pydantic-settings` + `.env` (gitignored). `TRADING_MODE = paper | testnet | live`; ver ADR-0002.

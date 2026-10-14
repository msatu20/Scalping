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
```
data/ (parquet) ──► backtest.replay ──(MarketEvent)──► strategy ──► risk ──► backtest.sim_broker
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
`ws_client` (URL combinada de `streams`) → `parse_message` → `asyncio.Queue[MarketEvent]` → (pendiente: `order_book` local + strategy).
- `on_connected` = punto de resync del libro tras cada (re)conexión.

## Configuración (✅)
- `config/settings.py`: `pydantic-settings` + `.env` (gitignored). `TRADING_MODE = paper | testnet | live`; ver ADR-0002.

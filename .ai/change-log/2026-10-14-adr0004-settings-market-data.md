# ADR-0004, settings y módulo market_data (parser + cliente WS)

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún) |
| Agente(s) | market-data, execution-risk (config) |

## Archivos cambiados
- `.ai/decisions/ADR-0004-ccxt-rest-and-native-websockets.md` — nuevo.
- `pyproject.toml` — añade `pydantic-settings>=2.7`.
- `.env.example` — variables de settings completas.
- `src/scalping/config/settings.py`, `config/__init__.py` — nuevos.
- `src/scalping/market_data/parser.py`, `streams.py`, `ws_client.py`, `__init__.py` — nuevos.
- `tests/conftest.py`, `tests/config/test_settings.py`, `tests/market_data/test_parser.py`, `test_streams.py`, `test_ws_client.py` — nuevos.
- `tests/fixtures/binance_futures/*.json` (4) — payloads de ejemplo.

## Motivo
T4 (cliente Binance) + configuración + inicio del módulo de market data.

## Resumen técnico
- **ADR-0004:** ccxt solo REST (en `execution`); WS nativo con `websockets` para depth/aggTrade/kline.
- **Settings** (pydantic-settings, inmutable): `TRADING_MODE` (paper|testnet|live), claves `SecretStr` (`BINANCE_SECRET` aceptado como alias), `SYMBOLS` CSV validado, `MAKER_FEE`/`TAKER_FEE` como fracción `Decimal` (<1 %), `MAX_LEVERAGE` ≤ `HARD_MAX_LEVERAGE`=10. Guardas: testnet/live exigen claves; live exige `LIVE_TRADING_CONFIRMED=true`. URLs REST/WS por modo.
- **Parser** puro: JSON crudo (raw o envoltorio combinado) → `OrderBookDelta`, `AggregatedTrade`, `Kline`; REST depth → `OrderBookSnapshot`. Frames de control y eventos no soportados → `None`; payload inválido → `ParseError`. Números solo desde string (`_dec`): rechaza floats JSON.
- **Streams:** nombres (`btcusdt@depth@100ms`, `@aggTrade`, `@kline_1m`) y URL combinada (máx. 200 streams).
- **WS client:** reconexión con backoff exponencial + jitter (se resetea solo si la sesión recibió datos), detección de stream obsoleto (`stale_timeout_s`), reconexión proactiva a las 23 h, callback `on_connected` para resincronizar el libro, `stop()` cierra el socket al instante, errores de parseo contados sin tumbar el stream, backpressure en la cola (no descarta deltas).

## Riesgo / impacto
- Sin envío de órdenes. Settings refuerza R7 (paper por defecto, doble confirmación para live) y límite de apalancamiento (K11).
- Bug evitado: `Decimal(float)` habría introducido error binario si Binance (o un fixture) enviara números JSON → ahora `ParseError`.
- Backpressure: si el consumidor es lento, el WS deja de leer y la latencia crece (K13).

## Pruebas
- `pytest` → 67 passed (0,6 s) · `ruff check` OK · `ruff format --check` OK · `mypy --strict` OK (16 archivos).
- Tests de WS contra servidor local 127.0.0.1 (sin internet): eventos, reconexión, errores de parseo, stop.

## Contexto actualizado
- `module-map`, `active-work`, `current-decisions`, `known-risks`, `architecture-summary`; `tasks/backlog.md`.

## Tareas de seguimiento
- [ ] Order book local (snapshot + deltas, resync en `on_connected` / hueco `pu`) — T6.
- [ ] Verificar URLs WS de futuros vigentes contra docs oficiales (posible separación de rutas) — T7.
- [ ] Benchmark `json` vs `orjson` en el parser — T8.
- [ ] Commit + push de este bloque (pendiente de confirmación).

# Setup inicial del proyecto y modelos core

| Campo | Valor |
|---|---|
| Fecha | 2026-10-13 |
| Rama | `main` (git init local; remoto `origin` configurado, sin push) |
| Agente(s) | orchestrator |

## Archivos cambiados
- `.gitignore`, `pyproject.toml`, `.env.example` — nuevos.
- `src/scalping/**/__init__.py`, `tests/**/__init__.py`, `tests/fixtures/.gitkeep` — esqueleto.
- `src/scalping/core/models.py`, `src/scalping/core/clock.py`, `src/scalping/core/__init__.py` — nuevos.
- `tests/core/test_models.py` — nuevo.
- `.ai/decisions/ADR-0003-futures-usdt-and-orderbook-analysis.md` — nuevo.
- `.ai/context/*`, `.ai/tasks/*`, `.ai/README.md` — actualizados.

## Motivo
Tareas T1 (bootstrap), T2 (modelos compartidos) y T3 (decisión de mercado) del backlog.

## Resumen técnico
- Mercado: Binance USDⓈ-M Futures, `BTCUSDT`/`ETHUSDT`, fees ref. maker 0,02 % / taker 0,05 % (ADR-0003).
- Modelos como `@dataclass(frozen=True, slots=True)` (rendimiento en hot path); pydantic queda para config/bordes.
- Microestructura: `OrderBookSnapshot` (validación de orden y libro cruzado, mid/spread), `OrderBookDelta` (`is_continuation_of` con `pu` en futuros / `U` en spot), `AggregatedTrade` (`aggressor_side`, `notional`), `OrderBookImbalance` (`value` ∈ [-1, 1], `from_snapshot`).
- `Signal` con `StrategyType` (`MEAN_REVERSION`, `STOP_HUNT_REBOUND`, `ORDER_FLOW_SQUEEZE`) y SL/TP validados por lado.
- `OrderIntent`: SL/TP obligatorios (sin default), validación SL < entry < TP (BUY) / inversa (SELL), `Decimal` obligatorio, `client_order_id` con regex de Binance, `risk_amount`, `from_signal`.
- `Clock` inyectable (`SystemClock` con offset, `FixedClock`).
- Dependencias: ccxt, websockets, aiohttp, numpy, pandas, pydantic, python-dotenv. TA-Lib como extra opcional `[talib]` (requiere librería C; solo referencia en tests). pytest y pytest-asyncio en extra `[dev]`.

## Riesgo / impacto
- Sin efecto en trading (no hay ejecución). `OrderIntent` refuerza R1 (SL/TP desde la creación) y R6 (`Decimal`).
- Riesgos nuevos registrados: K11 (liquidación), K12 (funding).

## Pruebas
- Entorno: Python 3.12.10 (winget, scope usuario) + `.venv` + `pip install -e .[dev]`.
- `pytest` → 27 passed · `ruff check src tests` → OK · `ruff format --check` → OK · `mypy` (strict, `src/scalping`) → sin errores.

## Contexto actualizado
- `module-map`, `active-work`, `current-decisions`, `known-risks`, `project-overview`, `architecture-summary`; `tasks/backlog.md`.

## Tareas de seguimiento
- [x] Instalar Python 3.12+ y ejecutar la suite.
- [x] Primer commit + push a `origin/main` (autorizado por el usuario).
- [ ] T4: decidir uso de ccxt (REST) vs cliente propio; WS propio con `websockets`.
- [ ] Protocolo `Broker` y modelos de estado de orden/posición → al empezar `execution`.

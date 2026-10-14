# Indicadores: SMA, EMA, RSI, Bollinger (batch + incremental, bit-idénticos)

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún; T5 = `2b41f28`) |
| Agente(s) | strategy |

## Archivos cambiados
- `src/scalping/strategy/indicators/_core.py` — nuevo: contrato de paridad, sumas de ventana izquierda→derecha (numpy y escalar), validación.
- `src/scalping/strategy/indicators/moving_average.py` — `sma`/`SMA`, `ema`/`EMA`.
- `src/scalping/strategy/indicators/rsi.py` — `rsi`/`RSI` (Wilder).
- `src/scalping/strategy/indicators/bollinger.py` — `bollinger`/`BollingerBands`, `BollingerValue` (`bandwidth`, `percent_b`).
- `src/scalping/strategy/indicators/__init__.py` — exports.
- `tests/strategy/test_indicators.py` — nuevo (51 tests).
- `tests/fixtures/binance_futures/btcusdt_1m_closes.csv` — 3000 cierres reales BTCUSDT 1m (68 KB).

## Motivo
Primer bloque de `strategy`: indicadores de corto plazo con paridad live/backtest.

## Resumen técnico
- **Batch** (`sma`, `ema`, `rsi`, `bollinger`): array → array float64, NaN en warm-up.
- **Incremental** (`SMA`, `EMA`, `RSI`, `BollingerBands`): `update(x)` por vela cerrada, `peek(x)` valor hipotético intra-vela sin mutar estado (tick a tick), `None` en warm-up, `ready`.
- **Contrato de paridad bit a bit:** ambos caminos ejecutan las mismas operaciones IEEE-754 en el mismo orden:
  - SMA/Bollinger: sumas de ventana estrictamente izquierda→derecha (numpy vectoriza sobre ventanas; nunca `np.sum`/`np.mean`, cuyo orden pairwise difiere). Sin suma acumulada móvil → sin deriva numérica.
  - EMA/RSI: recurrencias; el batch es un bucle que comparte la función de paso (`ema_step`, `wilder_step`, `rsi_value`) con la clase incremental.
- Convenciones: EMA `alpha=2/(n+1)` sembrada con SMA(n) (TA-Lib); RSI Wilder sembrado con media simple, `100·G/(G+L)`, plano → 50; Bollinger σ poblacional (ddof=0).
- Entradas `Decimal` aceptadas (conversión `float` correctamente redondeada); NaN/inf → `ValueError`.

## Riesgo / impacto
- Sin efecto en trading. Base para señales `MEAN_REVERSION` (RSI + Bollinger) y filtros de tendencia (EMA).

## Pruebas
- `pytest` → 162 passed (2,1 s) · `ruff` OK · `mypy --strict` OK (25 archivos).
- Paridad bit a bit (comparación de bits `int64`, más estricta que `==`): datos reales (8 periodos × 3 indicadores + Bollinger 4×3), propiedad hypothesis (300 series aleatorias), `peek == update` (150 series).
- Referencias independientes: pandas `rolling`/`ewm` (rtol 1e-12), RSI textbook `100−100/(1+RS)` (rtol 1e-10), valores exactos a mano.
- **89 días reales (128 160 velas × 2 símbolos):**
  | Indicador | Batch | Incremental | Bit-idéntico |
  |---|---|---|---|
  | SMA(20) | 1,6 ms | 0,59 µs/vela | ✅ |
  | EMA(20) | 14,9 ms | 0,16 µs/vela | ✅ |
  | RSI(14) | 51 ms | 0,45 µs/vela | ✅ |
  | BB(20,2) | 5,7 ms | 2,0 µs/vela | ✅ |

## Contexto actualizado
- `module-map`, `current-decisions`, `active-work`, `skills/technical-indicators.md`, `tasks/backlog.md`.

## Tareas de seguimiento
- [ ] Patrones de velas (`strategy/patterns/`) y señales (`strategy/signals.py`).
- [ ] T12 — Replay de backtest.
- [ ] Commit + push (pendiente de confirmación).

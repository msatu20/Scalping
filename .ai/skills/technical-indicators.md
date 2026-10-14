# Skill: technical-indicators

Implementados en `src/scalping/strategy/indicators/` (SMA, EMA, RSI, Bollinger). Seguir el mismo patrón para nuevos indicadores.

## Reglas
- Doble implementación: función batch (`nombre(values, ...)` → array, NaN en warm-up) + clase incremental (`update(x)`, `peek(x)`, `value`, `ready`; `None` en warm-up).
- **Paridad bit a bit obligatoria** (no basta `allclose`):
  - Sumas de ventana con `_core.window_sums` / `scalar_sum` (izquierda→derecha). Nunca `np.sum`/`np.mean` ni suma acumulada móvil.
  - Recurrencias: una función de paso compartida por batch e incremental.
  - Test: comparar `array.view(np.int64)` (ver `assert_bit_identical` en `tests/strategy/test_indicators.py`).
- `peek(x)` no muta estado y debe igualar al siguiente `update(x)` (test de propiedad).
- Entrada: velas cerradas para `update`; `peek` para valor intra-vela. Sin look-ahead.
- `float64` en indicadores; `Decimal` solo al generar precios de orden. Rechazar NaN/inf.

## Convenciones implementadas
| Indicador | Definición | Notas |
|---|---|---|
| SMA(n) | suma de ventana izquierda→derecha / n | sin deriva numérica |
| EMA(n) | `α=2/(n+1)`; `ema=α·x+(1-α)·ema_prev` | semilla = SMA(n) de las primeras n |
| RSI(n) | Wilder `(prev·(n-1)+x)/n`; `RSI=100·G/(G+L)` | semilla media simple; L=0 → 100; plano → 50; n=14 |
| Bollinger(n,k) | `mid=SMA(n)`; `±k·std` poblacional (ddof=0) | n=20, k=2; `bandwidth`, `percent_b(price)` |

## Rendimiento de referencia (128k velas 1m)
Batch: SMA 1,6 ms · BB 6 ms · EMA 15 ms · RSI 51 ms. Incremental: 0,2–2 µs/vela.

## Patrones de velas (1m–5m)
- Definir umbrales relativos (p. ej. % del rango o ATR), nunca absolutos en precio.
- Documentar cada patrón con su condición exacta en el docstring.

## Tests
- Paridad bit a bit (datos reales `btcusdt_1m_closes.csv` + hypothesis) · referencia independiente (pandas / textbook) · casos borde: serie plana, warm-up, n > len, Decimal, NaN/inf.

# Skill: technical-indicators

## Reglas
- Doble implementación: incremental O(1) por vela (live) + vectorizada numpy (backtest). Test de paridad obligatorio.
- Entrada: velas cerradas. Salida `None`/NaN durante warm-up.
- Sin look-ahead: el valor en t solo usa datos ≤ t.
- `float64` es aceptable en indicadores; convertir a `Decimal` solo al generar precios de orden.

## Fórmulas de referencia
| Indicador | Definición | Notas |
|---|---|---|
| SMA(n) | media de n cierres | ventana deslizante con suma acumulada |
| EMA(n) | `α=2/(n+1)`; `ema=α·x+(1-α)·ema_prev` | semilla = SMA(n) de las primeras n |
| RSI(n) | Wilder: `avg_gain/avg_loss` con suavizado `(prev·(n-1)+x)/n`; `RSI=100-100/(1+RS)` | n=14 por defecto; avg_loss=0 → 100 |
| Bollinger(n,k) | `mid=SMA(n)`; `±k·σ` poblacional (ddof=0) | n=20, k=2; %B y ancho útiles para scalping |

## Patrones de velas (1m–5m)
- Definir umbrales relativos (p. ej. % del rango o ATR), nunca absolutos en precio.
- Documentar cada patrón con su condición exacta en el docstring.

## Tests
- Valores contra pandas/TA-Lib en serie fija (fixture). · Casos borde: serie constante, gaps, n > len.

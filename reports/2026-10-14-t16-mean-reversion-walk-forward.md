# T16 — MEAN_REVERSION: variantes con walk-forward

Generado 2026-10-14 05:04 UTC por `scripts/research_mean_reversion.py` (1.1 min). Datos 2025-10-13..2026-10-12, BTCUSDT, ETHUSDT.

## Protocolo (pre-registrado)

- 24 variants = timeframe {1m, 5m} x entry {taker, maker -2 bps}
  x stops {structural & R:R >= 1, min 25 bps & R:R >= 0.5, min 40 bps & R:R >= 0.5}
  x regime filter {off, |EMA50 - EMA200| <= 50 bps}.
- Each variant is backtested once over the full period (klines, pessimistic SimBroker,
  real fees + 1 bp slippage + funding, 0.5 % risk without compounding -> results in R).
- Walk-forward: train 3 months -> test 1 month, 9 folds; pick the best train mean R
  (>= 30 train trades); the concatenated test months are the out-of-sample estimate.

## Resultado fuera de muestra (walk-forward)

| | trades | mean R | total R | win | PF | max DD (R) | t |
|---|---|---|---|---|---|---|---|
| **OOS (9 meses de test)** | 2291 | -0.185 | -424.9 | 47.4% | 0.70 | 435.9 | -7.91 |
| Mejor a posteriori (5m-maker-stop40-range, IN-SAMPLE, sesgada) | 1746 | -0.172 | -301.1 | 44.3% | 0.74 | 305.0 | -5.96 |

## Tramos

| Train | Test | Variante elegida | Train: trades / mean R | Test: trades / mean R / total R |
|---|---|---|---|---|
| 2025-10-13..2026-01-12 | 2026-01-13..2026-02-12 | 5m-maker-stop40-range | 417 / -0.176 | 110 / -0.085 / -9.4 |
| 2025-11-13..2026-02-12 | 2026-02-13..2026-03-12 | 5m-maker-stop40-range | 388 / -0.100 | 152 / -0.067 / -10.1 |
| 2025-12-13..2026-03-12 | 2026-03-13..2026-04-12 | 5m-maker-stop40-range | 416 / -0.102 | 148 / -0.089 / -13.1 |
| 2026-01-13..2026-04-12 | 2026-04-13..2026-05-12 | 5m-maker-stop40-range | 410 / -0.080 | 168 / -0.196 / -32.8 |
| 2026-02-13..2026-05-12 | 2026-05-13..2026-06-12 | 5m-maker-stop40-all | 764 / -0.116 | 237 / -0.173 / -41.0 |
| 2026-03-13..2026-06-12 | 2026-06-13..2026-07-12 | 5m-maker-stop40-all | 728 / -0.133 | 258 / -0.381 / -98.2 |
| 2026-04-13..2026-07-12 | 2026-07-13..2026-08-12 | 1m-maker-stop40-range | 1539 / -0.185 | 366 / -0.184 / -67.3 |
| 2026-05-13..2026-08-12 | 2026-08-13..2026-09-12 | 1m-maker-stop40-range | 1434 / -0.202 | 424 / -0.188 / -79.8 |
| 2026-06-13..2026-09-12 | 2026-09-13..2026-10-12 | 1m-maker-stop40-range | 1325 / -0.189 | 428 / -0.171 / -73.0 |

## Todas las variantes, periodo completo (IN-SAMPLE: solo descriptivo)

| Variante | señales | trades | mean R | total R | win | PF | max DD (R) | t |
|---|---|---|---|---|---|---|---|---|
| 5m-maker-stop40-range | 2243 | 1746 | -0.172 | -301.1 | 44.3% | 0.74 | 305.0 | -5.96 |
| 5m-maker-stop40-all | 3553 | 2794 | -0.183 | -510.3 | 41.6% | 0.74 | 512.0 | -7.55 |
| 1m-maker-stop40-range | 9170 | 6316 | -0.197 | -1242.3 | 49.6% | 0.68 | 1248.7 | -14.81 |
| 1m-maker-stop40-all | 10968 | 7685 | -0.201 | -1543.1 | 48.1% | 0.68 | 1548.8 | -16.17 |
| 5m-taker-stop40-all | 3553 | 3160 | -0.241 | -761.6 | 44.7% | 0.66 | 762.8 | -10.92 |
| 5m-taker-stop40-range | 2243 | 2026 | -0.247 | -500.0 | 47.4% | 0.63 | 504.9 | -9.66 |
| 1m-taker-stop40-range | 9170 | 7797 | -0.253 | -1976.3 | 54.2% | 0.57 | 1976.3 | -22.53 |
| 5m-maker-stop25-range | 2471 | 1948 | -0.255 | -496.2 | 39.1% | 0.67 | 497.9 | -8.22 |
| 5m-maker-stop25-all | 3789 | 3017 | -0.256 | -771.5 | 37.0% | 0.68 | 773.0 | -9.70 |
| 1m-taker-stop40-all | 10968 | 9296 | -0.256 | -2377.6 | 52.7% | 0.58 | 2379.4 | -24.02 |
| 1m-maker-stop25-all | 15278 | 10641 | -0.306 | -3259.3 | 42.6% | 0.60 | 3259.3 | -25.34 |
| 1m-maker-stop25-range | 13392 | 9151 | -0.312 | -2859.2 | 43.6% | 0.58 | 2859.2 | -24.75 |
| 5m-taker-stop25-all | 3789 | 3440 | -0.332 | -1142.0 | 40.5% | 0.59 | 1143.1 | -13.97 |
| 5m-taker-stop25-range | 2471 | 2284 | -0.350 | -800.1 | 42.8% | 0.56 | 800.8 | -12.95 |
| 1m-taker-stop25-all | 15278 | 13351 | -0.383 | -5109.5 | 48.9% | 0.48 | 5111.6 | -38.26 |
| 1m-taker-stop25-range | 13392 | 11716 | -0.388 | -4551.4 | 50.1% | 0.46 | 4551.4 | -37.58 |
| 5m-maker-struct-all | 3283 | 2679 | -0.509 | -1363.9 | 29.0% | 0.54 | 1365.4 | -11.51 |
| 5m-maker-struct-range | 2114 | 1702 | -0.549 | -934.7 | 30.0% | 0.52 | 938.2 | -9.77 |
| 5m-taker-struct-all | 3283 | 3089 | -0.605 | -1868.8 | 32.6% | 0.48 | 1869.8 | -14.09 |
| 5m-taker-struct-range | 2114 | 2025 | -0.672 | -1360.5 | 34.0% | 0.44 | 1360.9 | -12.00 |
| 1m-taker-struct-all | 13801 | 13173 | -0.929 | -12239.3 | 34.0% | 0.33 | 12241.0 | -52.76 |
| 1m-maker-struct-all | 13801 | 10177 | -0.967 | -9838.9 | 26.6% | 0.37 | 9838.9 | -21.94 |
| 1m-taker-struct-range | 12109 | 11625 | -0.968 | -11256.5 | 34.4% | 0.31 | 11256.5 | -52.19 |
| 1m-maker-struct-range | 12109 | 8785 | -1.028 | -9026.8 | 26.6% | 0.35 | 9031.9 | -20.75 |

R = PnL neto / riesgo planificado (0,5 % de 10 000 USDT, sin capitalizar). t = media / error estándar (|t| < 2: no distinguible de 0).
## Control sin costes (periodo completo)

| Variante | Costes | trades | mean R | PF | t |
|---|---|---|---|---|---|
| 5m-maker-stop40-range | reales | 1746 | -0.172 | 0.74 | -5.96 |
| 5m-maker-stop40-range | **cero** | 1746 | **-0.023** | 0.96 | -0.81 |
| 1m-maker-stop40-range | reales | 6316 | -0.197 | 0.68 | -14.81 |
| 1m-maker-stop40-range | **cero** | 6316 | **-0.042** | 0.92 | -3.31 |

## Conclusión

- **OOS −0,185 R/trade (t = −7,9), negativo en los 9 meses de test.** No cumple ningún criterio de ADR-0008.
- Las 24 variantes son negativas incluso in-sample: el walk-forward no oculta nada.
- Las lecciones de T13 funcionan en la dirección esperada (maker > taker, stop 40 > 25 > estructural, 5m > 1m, filtro de rango ≥ sin filtro) y reducen la pérdida de −1,15 R a ≈ −0,17 R, pero no crean ventaja.
- **Sin costes la mejor variante es ≈ 0 R (t = −0,8): la señal RSI + Bollinger no tiene capacidad predictiva** en BTCUSDT/ETHUSDT a 1m/5m en este año. Los costes (~0,15 R/trade) convierten "neutro" en "pérdida segura".
- **Decisión:** familia MEAN_REVERSION (RSI + BB, re-entrada) descartada. Seguir afinando sus parámetros sería sobreajuste. La siguiente hipótesis debe aportar **información distinta** (order flow / microestructura), no otra combinación de los mismos indicadores.

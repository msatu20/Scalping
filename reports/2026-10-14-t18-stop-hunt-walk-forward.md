# T18 — STOP_HUNT_REBOUND: walk-forward (pre-registrado en ADR-0009)

Generado 2026-10-14 16:49 UTC por `scripts/research_stop_hunt.py` (230.4 min). Datos 2025-10-13..2026-10-12, BTCUSDT, ETHUSDT, fuente de precio TRADES (aggTrades).

## Resultado fuera de muestra

| | trades | mean R | total R | win | PF | max DD (R) | t |
|---|---|---|---|---|---|---|---|
| **OOS walk-forward (9 meses)** | 6474 | -0.363 | -2352.9 | 40.6% | 0.54 | 2354.2 | -24.48 |
| Mejor a posteriori (lb30-k3-r1-maker, IN-SAMPLE, sesgada) | 12147 | -0.329 | -3991.6 | 43.3% | 0.57 | 3992.8 | -31.20 |
| La misma sin costes (control) | 12147 | -0.061 | -739.2 | 43.3% | 0.89 | 748.3 | -6.23 |

## Tramos

| Test | Variante elegida | Train trades / mean R | Test trades / mean R / total R |
|---|---|---|---|
| 2026-01-13..2026-02-12 | lb30-k6-r1-maker | 2531 / -0.326 | 1051 / -0.381 / -400.6 |
| 2026-02-13..2026-03-12 | lb120-k6-r1-maker | 1854 / -0.327 | 726 / -0.368 / -267.3 |
| 2026-03-13..2026-04-12 | lb120-k3-r2-maker | 2090 / -0.311 | 640 / -0.468 / -299.4 |
| 2026-04-13..2026-05-12 | lb30-k3-r1-maker | 3962 / -0.336 | 760 / -0.349 / -264.9 |
| 2026-05-13..2026-06-12 | lb30-k3-r1-maker | 3272 / -0.327 | 1029 / -0.305 / -313.9 |
| 2026-06-13..2026-07-12 | lb30-k6-r1-maker | 2307 / -0.307 | 709 / -0.335 / -237.5 |
| 2026-07-13..2026-08-12 | lb120-k3-r1-maker | 1764 / -0.303 | 363 / -0.331 / -120.0 |
| 2026-08-13..2026-09-12 | lb120-k3-r1-maker | 1623 / -0.289 | 518 / -0.403 / -208.8 |
| 2026-09-13..2026-10-12 | lb30-k3-r1-maker | 2338 / -0.305 | 678 / -0.355 / -240.4 |

## Variantes, periodo completo (IN-SAMPLE, descriptivo)

| Variante | trades | mean R | total R | win | PF | max DD (R) | t | sin costes: mean R |
|---|---|---|---|---|---|---|---|---|
| lb30-k3-r1-maker | 12147 | -0.329 | -3991.6 | 43.3% | 0.57 | 3992.8 | -31.20 | -0.061 |
| lb30-k6-r1-maker | 9393 | -0.337 | -3165.4 | 42.9% | 0.56 | 3166.0 | -28.19 | -0.070 |
| lb120-k3-r1-maker | 7494 | -0.339 | -2539.0 | 42.8% | 0.56 | 2541.3 | -25.31 | -0.072 |
| lb30-k3-r2-maker | 10970 | -0.346 | -3796.0 | 29.1% | 0.64 | 3802.3 | -23.29 | -0.054 |
| lb120-k6-r1-maker | 6591 | -0.347 | -2286.9 | 42.4% | 0.55 | 2287.9 | -24.36 | -0.080 |
| lb120-k3-r2-maker | 7142 | -0.350 | -2497.0 | 28.9% | 0.63 | 2503.4 | -19.02 | -0.059 |
| lb120-k6-r2-maker | 6314 | -0.353 | -2226.6 | 28.8% | 0.63 | 2226.6 | -18.07 | -0.063 |
| lb30-k6-r2-maker | 8654 | -0.363 | -3145.7 | 28.5% | 0.62 | 3151.2 | -21.87 | -0.073 |
| lb120-k3-r1-taker | 11730 | -0.388 | -4551.3 | 49.9% | 0.47 | 4553.5 | -38.97 | +0.005 |
| lb30-k3-r1-taker | 19864 | -0.389 | -7724.2 | 50.1% | 0.47 | 7724.2 | -50.80 | +0.006 |
| lb120-k6-r1-taker | 10433 | -0.393 | -4103.1 | 49.6% | 0.47 | 4106.0 | -37.27 | -0.001 |
| lb30-k6-r1-taker | 15395 | -0.399 | -6142.6 | 49.5% | 0.46 | 6143.0 | -45.91 | -0.005 |
| lb30-k3-r2-taker | 15955 | -0.403 | -6436.4 | 33.7% | 0.59 | 6438.5 | -34.13 | +0.016 |
| lb120-k3-r2-taker | 10571 | -0.404 | -4271.6 | 33.6% | 0.58 | 4282.7 | -27.86 | +0.014 |
| lb120-k6-r2-taker | 9460 | -0.407 | -3854.6 | 33.4% | 0.58 | 3858.8 | -26.61 | +0.010 |
| lb30-k6-r2-taker | 12842 | -0.413 | -5309.3 | 33.3% | 0.58 | 5311.6 | -31.49 | +0.004 |

## Conclusión

- **OOS −0,363 R/trade (t = −24,5, PF 0,54), negativo en los 9 meses de test.** No cumple ningún criterio de ADR-0008.
- Las 16 variantes son negativas incluso in-sample (mejor: −0,329 R).
- **Control sin costes:**
  - Entradas **taker ≈ 0 R** (−0,005 … +0,016; win rate ≈ 50 % con R:R 1): la señal **no tiene capacidad predictiva**.
  - Entradas **maker −0,06 … −0,08 R** sin costes: **selección adversa** (la limit solo se llena cuando el precio vuelve en contra).
- Costes ≈ 0,3–0,4 R/trade con stops de 25–40 bps: cualquier ventaja a esta escala temporal debe superar esa barrera.
- `busy` = 46 249 señales descartadas por posición abierta (las señales llegan en rachas).
- **Decisión:** STOP_HUNT_REBOUND (definición ADR-0009) **descartada**.

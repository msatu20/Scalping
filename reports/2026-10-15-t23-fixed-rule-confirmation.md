# T23 — Confirmación fuera de muestra: TREND_BREAKOUT 4h-n20-k2-r2

Generado 2026-10-15 15:36 UTC por `scripts/confirm_fixed_rule.py` (3.1 min). Regla fija `TrendBreakoutParams(interval=<KlineInterval.H4: '4h'>, channel=20, trend_ema=200, atr_period=14, atr_mult=2.0, target_r=2.0)`; activos SOLUSDT, ZECUSDT, NEARUSDT, DOGEUSDT, BNBUSDT, UNIUSDT, AVAXUSDT, FILUSDT, AAVEUSDT, DOTUSDT, ALPHAUSDT, DGBUSDT, OCEANUSDT, OMGUSDT; 2020-02-01..2026-09-30; broker sobre velas 1m (pesimista), costes reales + funding. Pre-registro: ADR-0012.

## Resultado

| | trades | mean R | total R | win | PF | max DD (R) | t |
|---|---|---|---|---|---|---|---|
| **Regla fija (todos los activos)** | 4472 | +0.083 | +372.6 | 37.0% | 1.13 | 114.0 | +3.84 |
| Control sin costes | 4472 | +0.102 | +455.4 | 37.0% | 1.16 | 106.5 | +4.70 |

## Criterios pre-registrados

| Criterio | Observado | Cumple |
|---|---|---|
| Mean R > 0 y t ≥ 2 | +0.083 R, t +3.84 | ✅ |
| Profit factor ≥ 1,2 | 1.13 | ❌ |
| Años positivos ≥ 70% | 5/7 | ✅ |
| Activos positivos ≥ 60% | 13/14 | ✅ |
| ≥ 200 trades | 4472 | ✅ |

Veredicto: **NO APROBADA**

### Por activo

| activo | trades | mean R | total R | win | PF | max DD (R) | t |
|---|---|---|---|---|---|---|---|
| AAVEUSDT | 361 | +0.049 | +17.5 | 35.7% | 1.07 | 19.0 | +0.64 |
| ALPHAUSDT | 238 | +0.080 | +19.1 | 36.6% | 1.12 | 12.8 | +0.85 |
| AVAXUSDT | 391 | +0.080 | +31.1 | 36.8% | 1.12 | 22.1 | +1.08 |
| BNBUSDT | 420 | +0.055 | +23.2 | 36.4% | 1.08 | 22.8 | +0.78 |
| DGBUSDT | 111 | +0.141 | +15.6 | 38.7% | 1.23 | 9.4 | +1.01 |
| DOGEUSDT | 384 | +0.099 | +38.1 | 37.5% | 1.15 | 31.6 | +1.34 |
| DOTUSDT | 337 | +0.092 | +31.1 | 37.7% | 1.14 | 14.6 | +1.16 |
| FILUSDT | 319 | +0.135 | +43.1 | 38.6% | 1.22 | 31.0 | +1.65 |
| NEARUSDT | 372 | +0.117 | +43.6 | 38.2% | 1.19 | 17.1 | +1.55 |
| OCEANUSDT | 184 | -0.058 | -10.6 | 32.6% | 0.92 | 20.8 | -0.55 |
| OMGUSDT | 260 | +0.082 | +21.4 | 36.9% | 1.13 | 16.9 | +0.92 |
| SOLUSDT | 357 | +0.131 | +46.8 | 38.9% | 1.21 | 19.1 | +1.70 |
| UNIUSDT | 365 | +0.077 | +28.0 | 36.7% | 1.12 | 18.2 | +1.01 |
| ZECUSDT | 373 | +0.065 | +24.4 | 36.2% | 1.10 | 16.6 | +0.87 |

### Por año

| año | trades | mean R | total R | win | PF | max DD (R) | t |
|---|---|---|---|---|---|---|---|
| 2020 | 232 | -0.013 | -3.1 | 34.1% | 0.98 | 35.8 | -0.14 |
| 2021 | 826 | +0.146 | +120.5 | 39.5% | 1.23 | 40.6 | +2.86 |
| 2022 | 634 | +0.176 | +111.7 | 39.9% | 1.29 | 33.3 | +3.01 |
| 2023 | 811 | +0.042 | +34.3 | 35.6% | 1.06 | 60.6 | +0.84 |
| 2024 | 813 | +0.076 | +61.7 | 36.7% | 1.12 | 42.4 | +1.49 |
| 2025 | 677 | +0.073 | +49.3 | 36.5% | 1.11 | 40.4 | +1.31 |
| 2026 | 479 | -0.004 | -1.8 | 34.2% | 0.99 | 114.0 | -0.06 |

R = PnL neto / riesgo planificado (0,5 % de 10 000 USDT, sin capitalizar).

## Conclusión

- **Veredicto pre-registrado (ADR-0012): NO APROBADA** — falla un único criterio: **profit factor 1,13 < 1,2**. No se relaja (decisión del usuario antes de ejecutar).
- **El efecto se replica fuera de muestra** en 14 activos nunca examinados: +0,083 R/trade (in-sample T21: +0,075), **t +3,84**, 13/14 activos positivos (incluidos 3 de 4 deslistados), 5/7 años positivos, 4 472 trades. Sin costes +0,102 R: los costes a 4 h solo restan ≈ 0,02 R/trade.
- **Por qué el PF se queda corto (diagnóstico, no excusa):** con objetivo 2R y win rate ≈ 37 %, el PF bruto máximo es ≈ 0,37·2 / 0,63 ≈ 1,17; tras costes ≈ 1,13. Con esta regla, PF ≥ 1,2 exige acertar ≥ 38–39 %. Es una propiedad de la regla que se conoce ahora; el criterio se mantiene.
- **Riesgos visibles:** 2026 plano (−0,004 R) y 2020 ligeramente negativo; **max drawdown agregado 114 R** = 57 % del capital con 0,5 % de riesgo por trade en 14 activos simultáneos → el sizing de cartera debe reducirse (K26).
- **Siguiente paso (ADR-0012, consecuencias):** prueba forward en **paper trading en tiempo real** con la regla fija sin cambios (decisión del usuario).

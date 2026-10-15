# ADR-0012 — Pre-registro: confirmación fuera de muestra de la regla fija 4h-n20-k2-r2 (T23)

- **Fecha:** 2026-10-15 · **Estado:** Cerrado — **NO APROBADA** (solo falla PF 1,13 < 1,2); efecto replicado: +0,083 R, t +3,84, 13/14 activos, 5/7 años (ver informe T23). Pre-registrado antes de descargar ningún precio de estos activos · **Protocolo:** ADR-0008 · **Antecedente:** ADR-0011 (hallazgo in-sample, K24)

## Hipótesis
La regla fija `TREND_BREAKOUT 4h-n20-k2-r2` (identificada in-sample en T21: +0,075 R, t +3,32, 7/7 años, 10/11 activos) tiene ventaja estructural y la mantiene en activos **nunca examinados**.

## Regla (sin ningún ajuste)
`TrendBreakoutParams(interval=4h, channel=20, trend_ema=200, atr_period=14, atr_mult=2.0, target_r=2.0)`; entrada taker; broker sobre velas 1m (pesimista, ADR-0007); costes reales (0,02/0,05 %) + 1 bp slippage + funding histórico; 0,5 % de riesgo por trade sin capitalizar; una posición por activo. **Sin walk-forward ni selección**: una sola regla, evaluada en todo el periodo disponible.

## Universo (regla basada solo en metadatos, decidida antes de ver precios)
Perpetuos USDT de Binance con `onboardDate` entre 2020-02-01 y 2021-06-30, excluidos los 11 de T21 (88 en total: 64 cotizando, 24 deslistados):
- **10 cotizando con mayor volumen 24 h** (2026-10-15): SOL, ZEC, NEAR, DOGE, BNB, UNI, AVAX, FIL, AAVE, DOT.
- **4 deslistados** por muestreo aleatorio con semilla fija `random.Random(20261015).sample(sorted(24 deslistados), 4)`: ALPHA, DGB, OCEAN, OMG (≈ proporción de deslistados de la cohorte, 27 %; mitiga sesgo de supervivencia).
- Limitación: el ranking por volumen actual favorece activos que siguen siendo relevantes (K23).

## Periodo
Desde el primer dato de cada activo (con calentamiento de la EMA200 de 4 h dentro de los datos) hasta 2026-09-30 o el deslistado.

## Criterios de aprobación (fijados por el usuario antes de ejecutar; todos obligatorios)
1. Mean R > 0 **y** t ≥ 2 (agregado de todos los activos).
2. **Profit factor ≥ 1,2** (ADR-0008; no se relaja aunque in-sample fuera 1,11).
3. **Años positivos ≥ 70 %** (años naturales con ≥ 30 trades).
4. **Activos positivos ≥ 60 %** (activos con ≥ 30 trades).
5. Validez muestral: ≥ 200 trades (requisito de ADR-0008).
- Diagnóstico (no criterio): control sin costes, desglose por activo y año.

## Consecuencias
- Aprobada → candidata a paper trading (T22) con la regla fija.
- No aprobada → siguiente paso: paper trading en tiempo real como prueba forward (decisión del usuario), sin cambiar la regla.

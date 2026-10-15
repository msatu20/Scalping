# ADR-0010 — Pre-registro: TREND_BREAKOUT (15 min – 1 h)

- **Fecha:** 2026-10-14 · **Estado:** Cerrado — **no aprobada** (OOS +0,023 R, t +0,41) pero con **ventaja bruta** (16/16 positivas sin costes); ver `reports/2026-10-14-t20-trend-breakout-walk-forward.md`. Pre-registrado antes de ver resultados · **Protocolo:** ADR-0008 · **Tarea:** T20

## Contexto
T16 y T18 mostraron que a 1–5 min los costes (≈ 0,3–0,4 R/trade) dominan y que las señales probadas no tienen ventaja bruta (K19). Subir el horizonte hace que el stop sea grande frente a los costes: con stops de 2–3 × ATR(1 h) (≈ 100–300 bps) los costes bajan a ≈ 0,03–0,08 R.

## Hipótesis
Las rupturas de un canal de N velas **a favor de la tendencia** de fondo tienen continuación (momentum de series temporales), efecto documentado en cripto. Información distinta a T16 (reversión) y T18 (microestructura): **persistencia de tendencia a horas/días**.

## Definición (implementación: `strategy/signals/trend_breakout.py`)
- Velas cerradas del intervalo de la estrategia.
- Canal: máximo/mínimo de las N velas **anteriores** (la vela actual no cuenta).
- Largo si `close > máximo del canal` y `close > EMA(200)`; corto si `close < mínimo` y `close < EMA(200)`.
- Stop = `k × ATR(14)` desde el cierre; objetivo = `target_r × riesgo`.
- Entrada taker (K20: maker sufre selección adversa); la orden expira al cerrar la siguiente vela.
- Una posición por símbolo (las rupturas con posición abierta se descartan).

## Rejilla (16 variantes, fija)
intervalo {15m, 1h} × N {20, 55} × k {2, 3} × target_r {2, 3}.

## Evaluación
- **36 meses** (2023-10-13..2026-10-12), BTCUSDT + ETHUSDT; camino de precio del broker = velas 1m (SimBroker pesimista, ADR-0007); costes reales + 1 bp slippage + funding; 0,5 % de riesgo sin capitalizar (R).
- Walk-forward ADR-0008: 3 m train → 1 m test (33 tramos), selección por R medio en train con ≥ 30 trades.
- Criterio de candidata a paper (ADR-0008): OOS mean R > 0 con t ≥ 2, PF ≥ 1,2, ≥ 200 trades OOS, mayoría de tramos positivos.
- Controles: rejilla sin costes; resultado por símbolo y por año (estabilidad de régimen).

## Consecuencias
- Si cumple: siguiente paso paper trading (SimBroker + feed live) con T15/T9 ya listos.
- Cualquier cambio tras ver resultados = nuevo experimento con nuevo ADR.

# ADR-0009 — Pre-registro: STOP_HUNT_REBOUND (order flow con aggTrades)

- **Fecha:** 2026-10-14 · **Estado:** Cerrado — hipótesis **rechazada** (OOS −0,363 R, t −24,5; sin costes ≈ 0 R taker), ver `reports/2026-10-14-t18-stop-hunt-walk-forward.md`. Pre-registrado antes de ver resultados · **Protocolo:** ADR-0008 · **Tarea:** T18

## Hipótesis
Un barrido de liquidez más allá de un extremo reciente, impulsado por un estallido de flujo agresivo en la dirección del barrido y **recuperado rápidamente**, marca el agotamiento de una caza de stops; el precio tiende a volver al rango previo. Información nueva respecto a T16: **agresión (taker side) y dinámica tick a tick**, no indicadores de precio de cierre.

## Definición (implementación: `strategy/signals/stop_hunt.py`)
- Nivel = mínimo/máximo de las últimas `lookback_min` velas 1m cerradas.
- Barrido: trade > `sweep_bps`=3 más allá del nivel (una a la vez; re-armado al volver al nivel).
- Estallido: agresión del lado del barrido en 10 s ≥ `burst_k` × su media por 10 s en la última hora.
- Ruptura (descartada): extremo > `max_depth_bps`=100 del nivel.
- Recuperación en ≤ `reclaim_s`=60 s: trade > 1 bp dentro del nivel → señal al precio de ese trade.
- Stop: extremo ∓ 5 bps, mínimo 25 bps (lección T13). Objetivo: `target_r` × riesgo. Enfriamiento 300 s por lado. Expiración de la orden 30 s.

## Rejilla (16 variantes, fija)
`lookback_min` {30, 120} × `burst_k` {3, 6} × `target_r` {1,0, 2,0} × entrada {taker, maker −2 bps}.

## Evaluación
- 12 meses (2025-10-13..2026-10-12), BTCUSDT + ETHUSDT, **fuente de precio TRADES** (SimBroker preciso sobre aggTrades, ADR-0007), costes reales + 1 bp slippage + funding, 0,5 % de riesgo sin capitalizar (R).
- Ejecución por ventanas mensuales y símbolo con 1 día de calentamiento; trades atribuidos por hora de entrada.
- Walk-forward idéntico a T16: 3 m train → 1 m test, 9 tramos, selección por R medio en train (≥ 30 trades).
- Criterio de candidata a paper (ADR-0008): OOS mean R > 0 con t ≥ 2, PF ≥ 1,2, ≥ 200 trades OOS, mayoría de tramos positivos.
- Controles obligatorios: misma rejilla sin costes; recuento de rechazos (barridos sin estallido, rupturas, expirados).

## Consecuencias
- Cualquier cambio de definición o rejilla tras ver resultados = nuevo experimento con nuevo ADR.

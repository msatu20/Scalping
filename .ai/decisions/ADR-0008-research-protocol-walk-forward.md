# ADR-0008 — Protocolo de investigación de estrategias: walk-forward pre-registrado

- **Fecha:** 2026-10-14 · **Estado:** Aceptada · **Contexto:** T16, K18

## Contexto
Con 12 meses de datos y un backtester rápido es trivial encontrar parámetros que "funcionan" en el pasado (sobreajuste / p-hacking). Las decisiones de operar deben basarse en resultados **fuera de muestra**.

## Decisión
1. **Pre-registro:** la rejilla de variantes, la métrica de selección y los criterios se fijan por escrito (script + este ADR) **antes** de ver resultados. Cambiarlos tras verlos = nuevo experimento, documentado como tal.
2. **Rejilla pequeña y motivada** por hipótesis (lecciones de T13), no búsqueda masiva de parámetros.
3. **Walk-forward:** entrenamiento 3 meses → test 1 mes, avance mensual. Selección en train = mayor R medio con ≥ 30 operaciones. Métrica principal = **R neto concatenado de los meses de test (OOS)**.
4. **Unidades:** R multiples con sizing sin capitalización (0,5 % de 10 000 USDT por operación); costes reales (comisiones de settings, 1 bp de slippage, funding), SimBroker pesimista (ADR-0007), fuente KLINES 1m para el broker.
5. **Criterio para considerar una estrategia candidata a paper trading** (todos):
   - OOS mean R > 0 y **t-stat ≥ 2** (≈ 95 % de que la media no es cero);
   - profit factor OOS ≥ 1,2 con ≥ 200 operaciones OOS;
   - resultado positivo en la mayoría de los tramos de test;
   - robustez: la variante elegida no cambia en cada tramo de forma errática.
6. **Informe** en `reports/` con OOS, tramos y la tabla in-sample marcada como descriptiva/sesgada.

## Consecuencias
- Resultados menos espectaculares pero creíbles; muchas ideas se descartarán.
- Cada nueva hipótesis = nuevo experimento con su propio pre-registro.

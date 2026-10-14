# ADR-0002 — Paper primero y gate explícito a live

- **Fecha:** 2026-10-13 · **Estado:** Aceptada

## Contexto
El scalping tiene márgenes pequeños; comisiones y errores operativos pueden anular la ventaja. El código maneja dinero real.

## Decisión
- `TRADING_MODE` por defecto = `paper`. Valores: `paper | testnet | live`.
- Para pasar a `live`:
  1. Backtest out-of-sample positivo neto de costes (`skills/backtest-validation.md`).
  2. ≥ 2 semanas en paper/testnet con métricas coherentes con el backtest.
  3. Invariantes R1–R8 de `skills/risk-guardrails.md` cubiertas por tests.
  4. Aprobación explícita del usuario. La IA nunca activa `live` por iniciativa propia.
- Claves de API: sin permiso de retirada, con whitelist de IP.

## Consecuencias
- Necesario un `sim_broker` compartido entre paper y backtest.

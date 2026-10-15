# T23 — Confirmación fuera de muestra de la regla fija 4h-n20-k2-r2

| Campo | Valor |
|---|---|
| Fecha | 2026-10-15 |
| Rama | `main` (sin commit aún; T21 = `3930125`) |
| Agente(s) | backtesting, strategy |

## Archivos cambiados
- `.ai/decisions/ADR-0012-fixed-trend-rule-confirmation.md` — nuevo (pre-registro con criterios del usuario; cerrado: no aprobada).
- `src/scalping/backtest/research.py` — `evaluate_fixed_rule`, `fixed_rule_report`.
- `scripts/confirm_fixed_rule.py` — nuevo.
- `reports/2026-10-15-t23-fixed-rule-confirmation.md` — nuevo.
- Test de `evaluate_fixed_rule` / `fixed_rule_report`.

## Diseño (fijado antes de descargar precios)
- Universo por metadatos: perpetuos USDT listados 2020-02-01..2021-06-30 fuera de T21 (88; 64 cotizando, 24 deslistados) → top-10 por volumen 24 h (SOL, ZEC, NEAR, DOGE, BNB, UNI, AVAX, FIL, AAVE, DOT) + 4 deslistados por muestreo con semilla 20261015 (ALPHA, DGB, OCEAN, OMG).
- Regla fija sin selección; criterios del usuario: PF ≥ 1,2 (no relajado), t ≥ 2, años ≥ 70 %, activos ≥ 60 %, ≥ 200 trades.
- Datos: 44,7 M velas 1m nuevas (mensuales), funding, 4h remuestreadas; 26 tramos de datos; 3,1 min de cómputo.

## Resultado
| | trades | mean R | PF | t |
|---|---|---|---|---|
| **Regla fija** | 4472 | **+0,083** | **1,13** | **+3,84** |
| Control sin costes | 4472 | +0,102 | 1,16 | +4,70 |
- Criterios: 4/5 — falla PF (1,13 < 1,2) → **NO APROBADA**.
- Replicación: +0,083 R vs +0,075 R in-sample (T21); 13/14 activos positivos (3/4 deslistados); años: 2020 −0,013 · 2021 +0,146 · 2022 +0,176 · 2023 +0,042 · 2024 +0,076 · 2025 +0,073 · 2026 −0,004.
- Diagnóstico PF: con 2R y win ≈ 37 % el PF bruto máximo ≈ 1,17 (K27).
- Max drawdown agregado 114 R (57 % con 0,5 %/trade en 14 activos) → sizing de cartera necesario (K26).

## Riesgo / impacto
- Ninguno operativo. Primera evidencia replicada fuera de muestra de una ventaja positiva tras costes.

## Pruebas
- `pytest` → 267 passed · `ruff` OK · `mypy --strict` OK.

## Contexto actualizado
- `module-map`, `current-decisions`, `known-risks` (K26, K27), `active-work`, `tasks/backlog.md` (T23 hecho, T22 candidato).

## Tareas de seguimiento
- [ ] T22 — paper trading forward con la regla fija sin cambios + sizing de cartera (decisión del usuario).
- [ ] Commit + push (pendiente de confirmación).

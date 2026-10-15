# ADR-0011 — Pre-registro: TREND_BREAKOUT multi-activo 1h–4h desde 2020 (T21)

- **Fecha:** 2026-10-15 · **Estado:** Cerrado — **NO APROBADA** (OOS +0,001 R, t +0,04, 4 277 trades); hallazgo in-sample de la regla fija 4h-n20-k2-r2 pendiente de confirmación (ver informe T21). Pre-registrado antes de ver resultados · **Protocolo:** ADR-0008 · **Antecedente:** ADR-0010, K21, K22

## Contexto
ADR-0010 mostró ventaja bruta (16/16 variantes > 0 sin costes) pero sin potencia estadística (951 trades OOS, t +0,41) y con deterioro temporal. Este experimento gana potencia con más activos y años, y exige estabilidad.

## Universo (regla fijada antes de ver resultados)
Perpetuos USDT-M de Binance con velas 1m en data.binance.vision **desde 2020-01**, entre los candidatos históricos revisados el 2026-10-15: BTC, ETH, XRP, ADA, LINK, LTC, BCH, TRX, XLM, ETC (cotizando) + **EOS (deslistado; incluido hasta su último dato para reducir el sesgo de supervivencia)**. 11 activos.
- **Limitación declarada (K23):** el universo se eligió con información de hoy (activos que existen desde 2020 y siguen siendo conocidos); sesgo de supervivencia residual.

## Estrategia
Idéntica a ADR-0010 (`TrendBreakoutStrategy`): ruptura de canal N a favor de EMA(200), stop k × ATR(14), objetivo R × riesgo, entrada taker. Sin cambios de definición.

## Rejilla (16 variantes, fija)
intervalo {1h, 4h} × N {20, 55} × k {2, 3} × target_r {2, 3}. **Misma variante para todos los activos** (sin ajuste por activo).

## Datos y simulación
- 2020-01-01..2026-09-30; velas 1h/4h remuestreadas desde 1m; broker sobre 1m (pesimista, ADR-0007); costes reales (0,02/0,05 %) + 1 bp slippage + funding histórico; 0,5 % de riesgo por trade sin capitalizar; una posición por activo, activos simultáneos permitidos.

## Walk-forward
ADR-0008: 3 m train → 1 m test; selección por R medio **agregado de todos los activos** en train (≥ 30 trades).

## Criterios de aprobación (todos obligatorios)
1. OOS agregado: mean R > 0 **y** t ≥ 2; PF ≥ 1,2; ≥ 200 trades (ADR-0008).
2. Mayoría de tramos de test con R total > 0.
3. **Estabilidad temporal:** mean R OOS > 0 en ≥ 70 % de los años naturales con ≥ 30 trades OOS, y ningún año de esos con mean R < −0,10.
4. **Amplitud:** mean R OOS > 0 en ≥ 60 % de los activos con ≥ 30 trades OOS.
5. Control sin costes informado (no es criterio, es diagnóstico).

## Consecuencias
- Aprobada → T22 paper trading con la variante/selección que indique el walk-forward.
- No aprobada → se documenta; nuevas ideas = nuevo ADR.

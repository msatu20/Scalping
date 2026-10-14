# Skill: risk-guardrails

Invariantes que NINGÚN cambio puede romper. Cambiar cualquier valor requiere confirmación del usuario + ADR.

## Invariantes
| # | Regla |
|---|---|
| R1 | Toda posición abierta tiene SL (y TP) registrado en el exchange o gestionado con fallback verificable. |
| R2 | Riesgo por trade ≤ `max_risk_per_trade` (% del equity) — tamaño = riesgo / distancia al SL. |
| R3 | Pérdida diaria ≥ `max_daily_loss` → kill-switch: cancelar órdenes, cerrar posiciones, bloquear nuevas entradas. |
| R4 | Nº máx. de posiciones simultáneas y exposición máx. por símbolo. |
| R5 | N errores consecutivos de API / datos obsoletos (> X s sin ticks) → pausa de entradas. |
| R6 | Cantidades/precios con `Decimal`, redondeados a filtros del símbolo. |
| R7 | Modo por defecto `paper`; `live` solo con flag explícito. |
| R8 | Estado desconocido de una orden (timeout) → consultar antes de reintentar; nunca duplicar. |

## Checklist al tocar execution/risk
- [ ] ¿Se mantienen R1–R8? Test que lo demuestre.
- [ ] Simulación de fallo: 429, desconexión WS, fill parcial, rechazo de SL.
- [ ] Backtest de regresión sin empeoramiento no explicado de drawdown.
- [ ] Sección "Riesgo/impacto" del change-log completa.

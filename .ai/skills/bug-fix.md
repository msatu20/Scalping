# Skill: bug-fix

## Pasos
1. Reproducir: test que falla (o script mínimo) antes de tocar código.
2. Localizar causa raíz con `code-inspection`; no parchear el síntoma.
3. Fix mínimo, dentro del módulo afectado.
4. El test del paso 1 pasa; ejecutar la suite del módulo (y `risk`/`execution` si se tocan).
5. Si afecta a señales, órdenes o riesgo → backtest de regresión (`backtest-validation`).
6. Change-log (Motivo = síntoma + causa raíz). Bugs relacionados no corregidos → `tasks/backlog.md`.

## Reglas
- Nunca debilitar validaciones de riesgo ni borrar tests para que pase.
- Bugs con impacto potencial en dinero real: avisar al usuario antes de aplicar.

# Token budget guidelines

Presupuesto orientativo de lectura de contexto/código por tarea (sin contar la salida).

| Tipo de tarea | Presupuesto | Lectura permitida |
|---|---|---|
| Pregunta / explicación | ≤ 8k | context/ + Grep; ≤ 2 archivos parciales |
| Bug localizado | ≤ 20k | 1 chunk + test asociado |
| Feature en un módulo | ≤ 35k | 1 chunk + CORE (contratos) |
| Feature transversal | ≤ 60k | chunks en secuencia; soltar los ya terminados |
| Cambio en execution/risk | ≤ 45k | EXE+RSK+skills; no recortar revisión de riesgo |
| Revisión de backtest | ≤ 25k | informe resumido + BT; nunca CSV completo |
| Mantenimiento `.ai/` | ≤ 15k | archivos `.ai/` afectados |

## Ahorro
- Base fija por sesión: `CLAUDE.md` + orchestrator + project-overview + active-work (~4k).
- Grep con `-n` y contexto corto antes de Read; Read con `offset/limit`.
- No re-leer lo ya leído; no pegar código en respuestas, referenciar `ruta:línea`.
- Búsquedas amplias → subagente de exploración (solo vuelve la conclusión).
- Logs/datos: `tail`, `head`, `wc -l`, esquema parquet.

## Si se excede
Detenerse, resumir lo aprendido en 5 viñetas y registrar en `tasks/ai-framework-improvements.md` (posible chunk demasiado grande o contexto ausente).

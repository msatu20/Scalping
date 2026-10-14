# AI framework improvements

Registro de fricción con el framework `.ai/`. Cualquier asistente debe añadir una fila cuando detecte un patrón (ver `agents/orchestrator.md` §7). Revisar mensualmente o cada ~10 change-logs.

## Categorías
| Código | Señal |
|---|---|
| FAIL | Patrón de fallo recurrente de la IA (supuesto falso, ruta obsoleta, test roto repetido) |
| BLOAT | Archivo de contexto > ~150 líneas, o chunk que excede el presupuesto de tokens |
| STALE | Contexto que no coincide con el código |
| SKILL | Secuencia repetida ≥3 veces sin skill |
| AGENT | Módulo sin agente dueño / agente que nunca se usa |
| REPEAT | Tarea manual repetitiva automatizable (script, hook, comando) |

## Registro
| Fecha | Cat. | Observación | Propuesta | Estado |
|---|---|---|---|---|
| 2026-10-13 | STALE | Todo el contexto es `PROPUESTA` (repo sin código) | Verificar y quitar marcas tras T1/T2 | parcial: `core` actualizado (2026-10-13); `module-map` usa leyenda ✅/🧱/📐 |
| 2026-10-13 | AGENT | `core/` sin agente propio (lo cubre orchestrator) | Reevaluar si crece > ~500 líneas | abierto |
| 2026-10-13 | REPEAT | Change-log y context-update son manuales | Valorar hook de Claude Code que recuerde el change-log al cerrar sesión | abierto |

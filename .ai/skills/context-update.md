# Skill: context-update

Ejecutar al cerrar cualquier cambio significativo (ver `agents/orchestrator.md` §3).

## Pasos
1. Crear `change-log/YYYY-MM-DD-<descripcion>.md` desde `templates/change-log.md`.
2. Actualizar solo los archivos de `context/` afectados (tabla en orchestrator §3). Editar líneas; no añadir párrafos.
3. `context/active-work.md`: mover la tarea a "Hecho" o actualizar estado.
4. Si hubo decisión → `decisions/ADR-NNNN-*.md` (plantilla `templates/adr.md`) + línea en `context/current-decisions.md`.
5. Deuda detectada → `tasks/backlog.md`. Fricción con el framework → `tasks/ai-framework-improvements.md`.
6. Comprobar duplicados: el hecho nuevo debe estar en un único archivo.

## Límites
- Cada archivo de `context/` ≤ ~150 líneas. Si se excede → registrar mejora y podar.

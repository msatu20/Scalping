# Framework de IA — Scalping

Infraestructura local para colaborar con asistentes de IA (Claude Code) en este repo.
Objetivo: máximo contexto útil con el mínimo de tokens, y seguridad en código de trading.

## Orden de lectura
| # | Archivo | Cuándo |
|---|---|---|
| 1 | `agents/orchestrator.md` | Siempre (reglas globales) |
| 2 | `context/project-overview.md` | Siempre |
| 3 | `context/active-work.md` | Siempre |
| 4 | `chunks/chunk-map.md` | Para decidir qué cargar |
| 5 | `agents/<agente>.md` + `skills/<skill>.md` | Según la tarea |

`CLAUDE.md` (raíz) lo carga Claude Code automáticamente y apunta aquí.

## Estructura
| Carpeta | Contenido |
|---|---|
| `agents/` | Orquestador + agentes por dominio (market-data, strategy, execution-risk, backtesting) |
| `skills/` | Procedimientos reutilizables y cortos |
| `context/` | Estado compacto del proyecto (fuente única de verdad para la IA) |
| `chunks/` | Estrategia de fragmentación, mapa de chunks, presupuesto de tokens |
| `decisions/` | ADRs (`ADR-NNNN-titulo.md`) |
| `change-log/` | `YYYY-MM-DD-descripcion.md` por cambio significativo |
| `tasks/` | Backlog técnico (`backlog.md`) y mejoras del propio framework |
| `templates/` | Plantillas: change-log, ADR, agente, skill, tarea |

## Uso con Claude Code (ejemplos de prompt)
- "Actúa como `market-data` y añade el stream aggTrades." → agente + `skills/websocket-streams.md`.
- "Corrige el bug del RSI." → `strategy` + `skills/bug-fix.md` + `skills/technical-indicators.md`.
- "Valida la estrategia antes de pasar a live." → `backtesting` + `skills/backtest-validation.md`.
- "Revisa el framework .ai." → `tasks/ai-framework-improvements.md`.

## Mantenimiento del contexto
1. Cambio significativo → entrada en `change-log/` (plantilla `templates/change-log.md`) — skill `context-update`.
2. Decisión de arquitectura → nuevo ADR + línea en `context/current-decisions.md`.
3. Deuda/bug detectado y no corregido → `tasks/backlog.md`.
4. Fricción con el framework (contexto inflado, skill faltante, tarea repetitiva) → `tasks/ai-framework-improvements.md`.
5. Editar, no duplicar. Si un archivo de `context/` supera ~150 líneas, dividir o podar.
6. Cuando exista código real, quitar las marcas `PROPUESTA` y verificar rutas.

## Estado
2026-10-13: esqueleto + modelos `core` implementados. Lo marcado `PROPUESTA` o 📐 en `context/module-map.md` aún no existe.

# Bootstrap del framework de IA

| Campo | Valor |
|---|---|
| Fecha | 2026-10-13 |
| Rama | — (repo local sin git; remoto GitHub vacío) |
| Agente(s) | orchestrator |

## Archivos cambiados
- `CLAUDE.md` — punto de entrada para Claude Code.
- `.ai/README.md`, `.ai/agents/*` (5), `.ai/skills/*` (9), `.ai/context/*` (7), `.ai/chunks/*` (3), `.ai/decisions/*` (2), `.ai/templates/*` (5), `.ai/tasks/*` (2), este change-log.

## Motivo
Crear la infraestructura de colaboración con IA antes de escribir código de negocio.

## Resumen técnico
- Repo vacío: arquitectura documentada como `PROPUESTA` (Python asyncio + Binance).
- Agentes: orchestrator, market-data, strategy, execution-risk, backtesting.
- Protocolo de seguridad live (orchestrator §8) + invariantes de riesgo R1–R8.

## Riesgo / impacto
- Ninguno sobre código (no existe). Solo documentación.

## Pruebas
- No aplica (sin código).

## Contexto actualizado
- Todos los archivos de `context/` creados.

## Tareas de seguimiento
- [ ] T1–T5 en `tasks/backlog.md`.
- [ ] Quitar marcas `PROPUESTA` al existir el código.

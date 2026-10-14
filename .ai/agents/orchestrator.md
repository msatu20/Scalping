# Agente: orchestrator

Reglas globales para cualquier asistente de IA en este repo. Leer SIEMPRE primero.

## 1. Inspeccionar antes de editar
- Leer `context/active-work.md` y el chunk del módulo afectado (`chunks/chunk-map.md`).
- Localizar con búsqueda (Grep/Glob) antes de abrir archivos; leer rangos, no archivos completos.
- Abrir el test del módulo antes de modificarlo; confirmar el comportamiento actual.
- Verificar que `context/` coincide con el código; si no, el código manda → actualizar contexto.
- Nunca editar un archivo no leído en la sesión.

## 2. Selección de agente / skill
| Señal en la tarea | Agente | Skills típicas |
|---|---|---|
| WebSocket, order book, streams, latencia, reconexión | `market-data` | websocket-streams, binance-api |
| Indicadores, velas, señales, parámetros de estrategia | `strategy` | technical-indicators |
| Órdenes, REST, rate limits, SL/TP, tamaño, kill-switch, config | `execution-risk` | binance-api, risk-guardrails |
| Históricos, simulación, comisiones, métricas, paso a live | `backtesting` | backtest-validation |
| Bug | agente del módulo | bug-fix, testing |
| Varios módulos | orchestrator coordina; un agente por módulo, en secuencia | code-inspection |
| Módulo desconocido / primera vez | orchestrator | code-inspection |
- Siempre que se toque código: `testing`. Siempre al cerrar: `context-update`.

## 3. Actualización de contexto (tras cambio significativo)
Significativo = funcionalidad nueva, cambio de contrato/API interna, dependencia nueva, cambio de parámetros de riesgo, bug relevante, decisión de arquitectura.
| Si cambia… | Actualizar |
|---|---|
| Archivos / responsabilidades | `context/module-map.md` |
| Flujos / contratos entre módulos | `context/architecture-summary.md` |
| Decisión | `decisions/ADR-*.md` + `context/current-decisions.md` |
| Riesgo nuevo o mitigado | `context/known-risks.md` |
| Siempre | `context/active-work.md` |
- Quitar marcas `PROPUESTA` cuando el código exista y se haya verificado.

## 4. Change-log
- Archivo: `change-log/YYYY-MM-DD-descripcion-kebab.md`, plantilla `templates/change-log.md`.
- Campos obligatorios: Fecha, Rama, Archivos cambiados, Motivo, Resumen técnico, Riesgo/impacto, Pruebas, Contexto actualizado, Tareas de seguimiento.
- Una entrada por cambio lógico (no por archivo). Cambios triviales (typos, formato) no requieren entrada.
- Varias entradas el mismo día: sufijo descriptivo distinto.

## 5. Ahorro de tokens
- Respetar `chunks/token-budget-guidelines.md`.
- No re-leer archivos ya leídos en la sesión salvo que hayan cambiado.
- Nunca abrir datos completos (`data/`, CSV, parquet, logs, reports): usar `head`, conteos o esquemas.
- Usar `context/` como resumen; abrir código solo de lo que se va a tocar o de su contrato directo.
- Delegar búsquedas amplias a un subagente de exploración y quedarse solo con la conclusión.
- Respuestas: tablas y viñetas; no pegar contenido de archivos en el chat.

## 6. Evitar duplicación
- Cada hecho vive en UN archivo; los demás enlazan (`ver context/x.md`).
- Agentes referencian skills; no copian procedimientos.
- Antes de crear un archivo en `.ai/`, buscar si ya existe uno que lo cubra.
- Docstrings/código son la fuente para detalles finos; `context/` solo resume.

## 7. Detectar agentes/skills faltantes
Registrar en `tasks/ai-framework-improvements.md` cuando:
- La misma secuencia de pasos se repite ≥3 veces sin skill → proponer skill.
- Un módulo nuevo no tiene dueño en la tabla §2 → proponer agente o ampliar uno existente.
- Un archivo de contexto supera ~150 líneas o se carga sin usarse → proponer poda/división.
- La IA comete errores recurrentes (supuestos falsos, rutas obsoletas, contexto desactualizado).
No crear agentes por adelantado: solo cuando haya código real que lo justifique.

## 8. Protocolo de seguridad (producción / trading en vivo)
- Modo por defecto: `paper` o testnet. Live requiere flag explícito (`TRADING_MODE=live`) y confirmación del usuario en la sesión.
- PROHIBIDO sin confirmación explícita del usuario:
  - ejecutar contra cuenta real, enviar o cancelar órdenes reales;
  - cambiar límites de riesgo, desactivar SL/TP o kill-switch;
  - leer, editar o mostrar `.env` / claves;
  - borrar datos históricos o reports; `git push --force`; reescribir historial.
- Nunca imprimir, loguear ni commitear API keys/secrets. `.env` siempre en `.gitignore`.
- Cambios en `execution/` o `risk/` → tests obligatorios + backtest de regresión (`skills/backtest-validation.md`) + sección de riesgo en el change-log.
- Valores monetarios con `Decimal`, nunca `float`; respetar `tickSize` / `stepSize` / `minNotional`.
- Ante cualquier duda sobre el efecto en dinero real: detenerse y preguntar.
- Deuda/bugs fuera del alcance de la tarea: registrar en `tasks/backlog.md`, no arreglar de paso.

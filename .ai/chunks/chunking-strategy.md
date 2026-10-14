# Chunking strategy

Objetivo: cargar solo el fragmento mínimo de contexto/código para cada tarea.

## Unidades de chunk
| Chunk | Contenido | Dueño |
|---|---|---|
| CORE | modelos compartidos, reloj, logging | orchestrator |
| MD | `market_data/` + tests + skill websocket-streams | market-data |
| STR | `strategy/` + tests + skill technical-indicators | strategy |
| EXE | `execution/` + tests + skill binance-api | execution-risk |
| RSK | `risk/` + tests + skill risk-guardrails | execution-risk |
| CFG | `config/`, `.env.example` (nunca `.env`) | execution-risk |
| BT | `backtest/` + tests + skill backtest-validation | backtesting |

## Reglas de segmentación
1. **Por módulo** (por defecto): cargar el chunk del módulo + CORE (solo contratos usados).
2. **Por feature transversal** (p. ej. "nuevo tipo de orden"): cadena de chunks según `chunk-map.md`, en orden del flujo; leer cada uno, actuar, soltar.
3. **Por contrato**: si solo cambia una interfaz, cargar la definición + sus consumidores (Grep), no los módulos completos.
4. **Datos**: nunca como chunk; solo esquema/primeras filas.
5. Dentro de un chunk: primero `context/module-map.md` → firmas (Grep `def |class `) → cuerpo solo de lo que se edita.

## Cuándo re-chunkear
- Un módulo supera ~1500 líneas o tiene >10 archivos → dividir en sub-chunks (p. ej. EXE-REST, EXE-UDS) y actualizar `chunk-map.md`.

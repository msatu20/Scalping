# Chunk map

## Dependencias entre chunks
```
            CFG
             │ (settings)
             ▼
MD ──► CORE ◄── STR ──► RSK ──► EXE
             ▲           ▲
             └── BT ─────┘  (BT reutiliza STR + RSK; sustituye EXE por sim_broker)
```
- Flecha `A ──► B`: A depende de B (cambiar B puede romper A).

## Qué cargar por tipo de tarea
| Tarea | Chunks | Contexto | Skills |
|---|---|---|---|
| Nuevo stream WS / fix de reconexión | MD, CORE | architecture-summary, known-risks | websocket-streams |
| Nuevo indicador / ajuste de señal | STR, CORE | architecture-summary | technical-indicators, testing |
| Nuevo tipo de orden / rate limit | EXE, RSK, CORE | known-risks | binance-api, risk-guardrails |
| Cambio de límites de riesgo | RSK, CFG | known-risks, current-decisions | risk-guardrails (+ confirmación usuario) |
| Validar estrategia | BT, STR | current-decisions | backtest-validation |
| Cambio de contrato (`Signal`, `OrderIntent`…) | CORE + consumidores | architecture-summary | code-inspection |
| Feature end-to-end | MD→STR→RSK→EXE→BT (secuencial) | architecture-summary | según chunk |
| Trabajo en el framework `.ai/` | — | README, tasks/ai-framework-improvements | context-update |

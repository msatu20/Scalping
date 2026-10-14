# Backlog técnico

Deuda, bugs detectados y trabajo pendiente. Formato: `templates/task.md`. No arreglar "de paso": registrar aquí.

### T1 — Bootstrap del proyecto Python
- **Área/chunk:** CORE · **Prioridad:** alta · **Origen:** repo vacío (2026-10-13)
- **Descripción:** `git init` + remoto GitHub, `.gitignore`, `pyproject.toml` (ruff, mypy, pytest, pytest-asyncio), `.env.example`, esqueleto `src/scalping/` y `tests/`.
- **Criterio de hecho:** `pytest -q` y `ruff check` pasan en el esqueleto; primer push a `main`.
- **Estado:** hecho (2026-10-13) — 27 tests OK, ruff y mypy limpios, primer push

### T2 — Modelos compartidos (CORE)
- **Área/chunk:** CORE · **Prioridad:** alta
- **Descripción:** `MarketEvent`, `Signal`, `OrderIntent`, protocolo `Broker`, reloj inyectable (ver `context/architecture-summary.md`).
- **Estado:** hecho (2026-10-13) salvo protocolo `Broker` (se define al empezar execution)

### T3 — Decidir spot vs futuros y símbolos iniciales
- **Área/chunk:** CFG · **Prioridad:** alta
- **Descripción:** condiciona tipos de orden, SL (OCO vs STOP_MARKET) y comisiones. Resultado → ADR-0003.
- **Estado:** hecho (2026-10-13) → ADR-0003

### T4 — Decidir cliente Binance (propio vs `python-binance` vs `ccxt`)
- **Área/chunk:** EXE/MD · **Prioridad:** media · Resultado → ADR.
- **Estado:** pendiente — ccxt ya añadido a dependencias por decisión del usuario; falta ADR

### T5 — Descarga de históricos (klines 1m + aggTrades) a parquet
- **Área/chunk:** BT · **Prioridad:** media
- **Estado:** pendiente

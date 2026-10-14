# Active work

## En curso
- (ninguna)

## Entorno
- Python 3.12.10 en `.venv` (`.venv/Scripts/python.exe`). Python del sistema = 3.7: usar siempre el del venv.
- Verificación: `.venv/Scripts/python.exe -m pytest` · `.venv/Scripts/ruff.exe check src tests` · `.venv/Scripts/mypy.exe`

## Siguiente
1. T4 — cliente REST (ccxt ya en dependencias) vs WS propio para market data → ADR-0004.
2. `config/settings.py` (TRADING_MODE, símbolos, comisiones, apalancamiento máx.).
3. `market_data`: parser de payloads de futuros → modelos `core` (con fixtures JSON reales).
4. T5 — descarga de históricos (klines 1m + aggTrades) a parquet.

## Hecho
- 2026-10-13 · T1, T2, T3: proyecto inicial + modelos core + ADR-0003 (`change-log/2026-10-13-initial-setup-and-core-models.md`).
- 2026-10-13 · Framework `.ai/` + `CLAUDE.md` (`change-log/2026-10-13-bootstrap-ai-framework.md`).

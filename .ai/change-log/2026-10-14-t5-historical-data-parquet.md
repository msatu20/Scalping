# T5 — Descarga de históricos (klines 1m + aggTrades) a Parquet

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún; T7+T10 = `0310eb1`) |
| Agente(s) | backtesting |

## Archivos cambiados
- `.ai/decisions/ADR-0006-historical-data-parquet.md` — nuevo.
- `src/scalping/backtest/store.py` — nuevo: `HistoricalStore`, `DataKind`, `MissingDataError`, `day_range`, `find_kline_gaps`.
- `src/scalping/backtest/binance_vision.py` — nuevo: `BinanceVisionDownloader`, `parse_daily_zip`, `verify_checksum`, `daily_url`, `DownloadResult/Status`, `ChecksumError`.
- `src/scalping/backtest/__init__.py` — exports.
- `scripts/download_history.py` — nuevo (CLI).
- `tests/backtest/test_binance_vision.py` — nuevo (17 tests).
- `pyproject.toml` — `pyarrow>=17` (runtime), `pandas-stubs` (dev).

## Motivo
T5: base de datos histórica para backtesting de indicadores y estrategias.

## Resumen técnico
- Descarga concurrente (semáforo, 4 por defecto) desde data.binance.vision; reintentos con backoff en red/5xx/429; 404 → `MISSING`.
- SHA-256 contra `.CHECKSUM` antes de parsear; nada se escribe si falla.
- CSV con y sin cabecera (los ficheros antiguos no la tienen); cabecera validada; µs → ms; `is_buyer_maker` booleano; parseo y escritura en hilo (`asyncio.to_thread`) para no bloquear el event loop.
- Parquet diario zstd con escritura atómica; `load` falla ante días ausentes.
- CLI: `--days N` o `--start/--end`, `--kinds`, `--symbols`, `--interval`; exit 1 solo si faltan días con más de 2 días de antigüedad.

## Riesgo / impacto
- Sin efecto en trading. `data/` gitignored.
- Precisión: float64 round-trip; conversión a `Decimal` solo vía `str()`.

## Pruebas
- `pytest` → 111 passed (1,6 s) · `ruff` OK · `mypy --strict` OK (21 archivos).
- Tests offline: parseo con/sin cabecera (filas reales), µs→ms, cambio de esquema, filas desordenadas, checksum, rutas, `MissingDataError`, huecos de klines, descargador contra servidor local (503 → reintento, 404, idempotencia, checksum corrupto sin escritura).
- **Descarga real:**
  | Dataset | Rango | Filas | Disco |
  |---|---|---|---|
  | klines 1m BTCUSDT+ETHUSDT | 2026-07-16..2026-10-12 (89 días) | 256 320 | 15 MB |
  | aggTrades BTCUSDT+ETHUSDT | 2026-10-11..2026-10-12 | 3 004 045 | 25 MB |
  - 2026-10-13 aún no publicado (normal).
- **Validación de datos:** 0 huecos / 0 OHLC inválidos / 0 duplicados en klines; volumen diario aggTrades = klines exacto; diferencias por minuto compensadas (frontera). Ver ADR-0006.

## Contexto actualizado
- `module-map`, `architecture-summary`, `current-decisions`, `known-risks` (K16), `active-work`, `tasks/backlog.md`, `skills/backtest-validation.md`.

## Tareas de seguimiento
- [ ] Ampliar aggTrades (p. ej. 30 días ≈ 400–600 MB en disco) cuando haya estrategia que backtestear.
- [ ] T12 — Replay de backtest: Parquet → eventos `core` (`Kline`, `AggregatedTrade`) ordenados por tiempo.
- [ ] Commit + push (pendiente de confirmación).

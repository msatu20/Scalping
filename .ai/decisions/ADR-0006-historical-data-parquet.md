# ADR-0006 — Históricos desde data.binance.vision en Parquet diario

- **Fecha:** 2026-10-14 · **Estado:** Aceptada · **Resuelve:** T5

## Contexto
El backtesting necesita klines 1m y aggTrades de USDⓈ-M Futures con integridad verificable, rápidos de leer con numpy/pandas y descargables de forma incremental.

## Decisión
- **Fuente:** `https://data.binance.vision/data/futures/um/daily/{klines/<SYM>/<int>|aggTrades/<SYM>}/…zip` + `.CHECKSUM` (SHA-256). Público, sin claves, sin consumir rate limits de la API.
- **Granularidad:** un fichero por símbolo y día UTC → descargas incrementales e idempotentes (días existentes se saltan).
- **Formato:** Parquet + zstd. Layout `data/futures_um/klines/<interval>/<SYM>/<YYYY-MM-DD>.parquet` y `data/futures_um/aggTrades/<SYM>/<YYYY-MM-DD>.parquet` (`data/` en `.gitignore`).
- **Tipos:** timestamps `int64` ms UTC (µs → ms si Binance cambia la unidad); precios/cantidades `float64` parseados con `float_precision="round_trip"` → `Decimal(str(x))` reproduce el string original. `Decimal` solo en la frontera de órdenes (R6 sigue aplicando a `OrderIntent`).
- **Integridad:** checksum obligatorio antes de parsear; cabecera validada (cambio de esquema → error); filas ordenadas; sin nulos; escritura atómica (`.tmp` + `os.replace`).
- **Huecos:** `HistoricalStore.load` lanza `MissingDataError` si falta algún día; `find_kline_gaps` detecta minutos ausentes dentro de los días.

## Validación (2026-10-14)
- 89 días de klines 1m × 2 símbolos: 128 160 filas/símbolo, 0 huecos, 0 OHLC incoherentes, 0 duplicados.
- aggTrades 2026-10-12: volumen diario reconstruido = volumen de klines **exacto** (BTC 141 916,123; ETH 3 696 195,100). Diferencias por minuto se compensan (efecto frontera: un aggTrade agrupa fills con un solo timestamp). High/low por minuto coinciden 99,8–99,9 %.
- Los trade IDs de futuros **no son contiguos** (≈10–13k discontinuidades/día): `last_trade_id − first_trade_id + 1` no es un conteo fiable de trades.

## Alternativas
- Klines por REST: consume peso de API y es lento para meses de datos.
- Un único Parquet por símbolo: reescrituras costosas al añadir días.
- `decimal128` en Parquet: exacto pero lento en numpy/pandas.

## Consecuencias
- Velas de 1m: usar klines como fuente de verdad del volumen por vela; aggTrades para order flow (agresión, barridos).
- Los días se publican con unas horas de retraso: el script trata los 2 últimos días ausentes como "no publicado aún".
- `AggregatedTrade.trade_count` (core) hereda la limitación de IDs no contiguos → no usar como métrica exacta.

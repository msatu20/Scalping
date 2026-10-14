# ADR-0007 — Modelo de fills del simulador de broker (backtest)

- **Fecha:** 2026-10-14 · **Estado:** Aceptada · **Resuelve:** T13

## Contexto
El backtest debe ser **pesimista por diseño**: cualquier ambigüedad se resuelve en contra de la estrategia. Disponemos de aggTrades (pocos días) y de klines 1m (meses).

## Decisión
- **Dos fuentes de precio:** `TRADES` (cada aggTrade es un punto del camino, preciso) y `KLINES` (fallback, pesimista). Mismas reglas de órdenes.
- **Entradas:**
  - TAKER (MARKET): primer precio posterior a la orden (siguiente trade / siguiente apertura) ± `taker_slippage_bps` (1 bp por defecto); comisión taker.
  - MAKER (LIMIT GTX): rechazada si cruzaría al enviarse (post-only); se llena **al precio límite solo si el mercado lo atraviesa** (tocar no basta: posición en la cola desconocida; `maker_fill_on_touch` opcional); cancelada en `expires_at` de la señal; comisión maker.
- **Salidas:**
  - SL = STOP_MARKET (taker): primer precio en o más allá del stop; fill **a ese precio** ∓ slippage → los huecos ejecutan peor que el stop.
  - TP = límite maker (por defecto, misma regla de "atravesar") o TAKE_PROFIT_MARKET taker.
  - Klines: SL y TP en la misma vela → SL; tras entrar dentro de una vela solo se evalúa el SL en esa vela; hueco en la apertura → fill a la apertura.
- **Funding:** en cada liquidación con posición abierta, `−lado · qty · markPrice · rate` (histórico REST `/fapi/v1/fundingRate`, con mark price).
- **Contabilidad:** `Decimal`; PnL neto = bruto − comisiones (entrada + salida) + funding. Una posición por símbolo (one-way); señales con símbolo ocupado se descartan.
- **Sizing de backtest:** fraccional fijo (0,5 % del equity por trade / distancia al stop), tope de apalancamiento de settings, `qty_step` 0,001 (filtros reales: T15).
- **Orden por evento:** broker procesa el evento antes que la estrategia → una orden solo puede llenarse con eventos posteriores.

## Validación
- Control sin costes reproduce el diagnóstico preliminar de la señal (−0,04 R vs −0,07 R de primer toque).
- `KLINES` vs `TRADES` en 2026-10-11..12: mismas 64 operaciones y salidas; neto −2110,93 vs −2111,93 → el modo pesimista con velas es fiable para esta estrategia.

## Alternativas
- Fills al tocar el límite: optimista (ignora la cola).
- Fill de SL al precio del stop: ignora huecos (optimista).
- Simulación de libro completo: requiere depth histórico (K17, T14).

## Consecuencias
- Resultados conservadores; estrategias que dependan de fills maker optimistas parecerán peores que en la realidad (preferible al revés).
- No hay `Broker` Protocol en `core` todavía: `SimBroker` define la interfaz de facto (`submit`, `on_event`, `is_busy`, `close_all`) → T17.

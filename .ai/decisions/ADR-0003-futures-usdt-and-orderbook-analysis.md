# ADR-0003 — Binance USDT-M Futures + análisis de order book / order flow

- **Fecha:** 2026-10-13 · **Estado:** Aceptada · **Resuelve:** T3

## Contexto
El scalping vive de márgenes de pocos bps: las comisiones deciden la viabilidad (K8). Además, las estrategias objetivo necesitan operar en ambos sentidos y leer microestructura (profundidad, agresión, barridos de stops), no solo velas.

## Decisión
- **Mercado:** Binance **USDⓈ-M Futures** (perpetuos lineales en USDT).
- **Comisiones de referencia (VIP 0, sin descuento BNB):** Maker **0,02 %** · Taker **0,05 %**. Verificar el tier real de la cuenta antes de cada backtest/live; el modelo de costes las toma de config.
  - Coste ida y vuelta: maker/maker 0,04 % · taker/taker 0,10 % → preferir entradas maker (post-only `GTX`).
- **Sentido:** largo y corto (permite operar squeezes en ambas direcciones).
- **Pares iniciales:** `BTCUSDT`, `ETHUSDT` (máxima liquidez y spread mínimo).
  - Notación interna: formato nativo Binance (`BTCUSDT`). ccxt usa `BTC/USDT:USDT`; la conversión vive solo en la capa `execution`.
- **Datos de mercado requeridos** (modelos en `src/scalping/core/models.py`):
  | Fuente WS (futuros) | Modelo | Uso |
  |---|---|---|
  | `<s>@kline_1m` / `_5m` | `Kline` | indicadores (SMA/EMA, RSI, Bollinger) |
  | REST `depth` + `<s>@depth@100ms` | `OrderBookSnapshot` / `OrderBookDelta` | libro local (`U`/`u`/`pu`) |
  | `<s>@aggTrade` | `AggregatedTrade` | agresión compradora/vendedora, picos de volumen, barridos de stops |
  | derivado del libro | `OrderBookImbalance` | presión compra/venta en N niveles |
- **Familias de estrategia** (`StrategyType`): `MEAN_REVERSION`, `STOP_HUNT_REBOUND`, `ORDER_FLOW_SQUEEZE`.

## Alternativas
- Spot: comisiones mayores (0,10 % VIP 0), sin cortos nativos → descartado como mercado principal.
- COIN-M: margen en cripto, PnL no lineal en USDT → descartado.

## Consecuencias / riesgos nuevos
- **Apalancamiento y liquidación:** riesgo de liquidación → limitar apalancamiento en config y comprobar distancia SL ≪ distancia a liquidación (K11).
- **Funding** cada 8 h: impacto pequeño en scalping pero se modela en backtest (K12).
- SL/TP vía órdenes `STOP_MARKET` / `TAKE_PROFIT_MARKET` con `reduceOnly`/`closePosition`.
- Order book de futuros usa `pu` para validar continuidad (ver `skills/websocket-streams.md`).
- Usar modo de posición one-way inicialmente (hedge mode → nuevo ADR si se necesita).

# Primera señal: MEAN_REVERSION (RSI + Bollinger)

| Campo | Valor |
|---|---|
| Fecha | 2026-10-14 |
| Rama | `main` (sin commit aún; T12 = `fcb8fa6`) |
| Agente(s) | strategy |

## Archivos cambiados
- `src/scalping/core/models.py` — `Signal`: + `expires_at` (invalidación temporal, validada > `created_at`), + `features` (Mapping), + `is_expired(now)`.
- `src/scalping/strategy/signals/base.py` — nuevo: Protocol `SignalGenerator.on_event(event) -> Signal | None`, `SignalHandler`.
- `src/scalping/strategy/signals/mean_reversion.py` — nuevo: `MeanReversionStrategy`, `MeanReversionParams`, `TriggerMode`.
- `src/scalping/strategy/signals/__init__.py` — exports.
- `scripts/run_signals.py` — nuevo: ejecuta la señal sobre el replay y resume.
- `tests/strategy/test_mean_reversion.py` — nuevo (12 tests).

## Motivo
Primera estrategia de punta a punta sobre feed (live o replay) + reloj inyectado.

## Resumen técnico
- **Setup** (vela cerrada): `close < BB lower` y `RSI ≤ 30` (largo) / simétrico en corto. Rastrea extremo de precio y de RSI; re-armado por nueva vela extrema; caduca tras `max_setup_bars` (5).
- **Trigger** re-entrada en banda: `CLOSE` (vela cerrada, indicadores comprometidos) o `TICK` (cada aggTrade con `peek()`, máx. 1 señal por vela; el extremo se actualiza con precios de trades).
- **Niveles:** TP = banda media; SL = extremo del setup ∓ 5 bps. Filtros: objetivo ≥ 12 bps (> 10 bps de ida y vuelta taker, K8) y reward/risk ≥ 1,0. Rechazos contabilizados en `stats(symbol)`; el setup sigue armado tras un rechazo.
- **Signal:** `created_at = clock.now_ms()` (reloj inyectado), `expires_at = +60 s`, `confidence` heurística ∈ [0,1] (½ extremidad RSI + ½ penetración en banda), `features` (rsi, extremos, bandas, %B, bandwidth, R/R, target bps, barras de setup).
- Precios de la señal en `Decimal` sin redondear a tick: el redondeo a `tickSize` corresponde a `execution` (T15).

## Riesgo / impacto
- Sin ejecución de órdenes. **Diagnóstico preliminar desfavorable** (ver abajo): no apta para operar; requiere backtest real (T13) y revisión de diseño/parámetros con out-of-sample (K18).

## Pruebas
- `pytest` → 184 passed (2,6 s) · `ruff` OK · `mypy --strict` OK (30 archivos).
- Tests: mercado tranquilo/warm-up sin señales, BUY por re-entrada (created_at = reloj, expires_at, TP = media batch, SL = extremo − 5 bps), SELL simétrico, caducidad del setup, filtro R/R por defecto, 1 señal por setup, modo tick (extremo por trades, 1 por vela), modo close ignora trades, símbolo/intervalo ajenos, Protocol, validaciones, **misma secuencia de señales vía ReplayFeed que alimentando eventos directamente**.
- **Replay real 89 días (2026-07-16..10-12), trigger CLOSE:**
  | | BTCUSDT | ETHUSDT |
  |---|---|---|
  | Señales (BUY/SELL) | 1283 (615/668) | 1541 (756/785) |
  | Por día | 14,4 | 17,3 |
  | Semanas con señales | todas (46–135/semana) | todas (69–153/semana) |
  | Mediana confidence / R:R / objetivo | 0,26 / 1,92 / 20,2 bps | 0,27 / 1,73 / 23,8 bps |
  | Rechazos (target<fees / R:R / niveles) | 5204 / 462 / 622 | 3064 / 866 / 435 |
  | 1er toque TP vs SL en 60 velas (sin costes) | 32,3 % TP | 32,3 % TP |
- Trigger TICK (2 días con aggTrades): 61 / 69 señales, 20,7 % / 31,3 % TP (vs CLOSE mismos días: 34 / 32 señales, 25,0 % / 32,3 %).
- **Lectura:** con R:R mediano ~1,8–1,9 y ~32 % de TP primero, la expectativa ≈ 0,32·1,9 − 0,68·1 ≈ −0,07 R **antes de comisiones** → negativa tras costes. Diagnóstico simplificado (ambos toques en la misma vela = SL), no un backtest.

## Contexto actualizado
- `module-map`, `architecture-summary`, `current-decisions`, `known-risks` (K18), `active-work`, `tasks/backlog.md`.

## Tareas de seguimiento
- [ ] T13 — `sim_broker` y backtest real con comisiones/slippage.
- [ ] T16 — Investigación de la señal con walk-forward (filtros de régimen/tendencia, TP parcial, SL por ATR) — solo tras T13.
- [ ] T15 — Redondeo de precios a `tickSize` (exchangeInfo) en `execution`.
- [ ] Commit + push (pendiente de confirmación).

# Skill: backtest-validation

## Protocolo
0. Datos: `scripts/download_history.py --days N` (o `--start/--end`); cargar con `HistoricalStore.load` (falla si faltan días) y revisar `find_kline_gaps` (ADR-0006).
   Ejecutar la estrategia con `ReplayFeed(store, symbols, start, end).replay(on_event)` usando el `feed.clock` como reloj: mismo código que en live, sin batch paralelo.
1. Fijar: símbolo(s), timeframe, rango in-sample y out-of-sample, parámetros, commit.
2. Costes realistas: comisión maker/taker del tier actual, slippage (ticks), latencia, probabilidad de fill de limit.
3. Ejecutar baseline (código actual) y candidato (cambio) con los mismos datos.
4. Comparar métricas netas de costes.
5. Guardar informe en `reports/YYYY-MM-DD-<tema>.md` (+ CSV de trades; no commitear si es grande).

## Métricas mínimas
PnL neto · nº trades · win rate · profit factor · expectancy/trade (en bps y en comisiones) · max drawdown · Sharpe/Sortino · tiempo medio en posición.

## Señales de alerta
- Expectancy por trade < 2× coste por trade → frágil.
- Gran diferencia in-sample vs out-of-sample → sobreajuste.
- Pocos trades (< ~200) → no concluyente.
- Mejora que desaparece con +1 tick de slippage.

## Gate paper → live (ver ADR-0002)
Out-of-sample positivo neto de costes + ≥2 semanas en paper/testnet con métricas coherentes + aprobación explícita del usuario.

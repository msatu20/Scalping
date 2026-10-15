# Known risks

| ID | Área | Riesgo | Mitigación |
|---|---|---|---|
| K1 | RSK | Posición sin SL por fallo al colocarlo | R1: verificar SL tras fill; si falla → cerrar posición |
| K2 | EXE | Órdenes duplicadas por reintento tras timeout | `newClientOrderId` idempotente + consulta de estado (R8) |
| K3 | EXE | Baneo IP por rate limits (429→418) | ✅ T9: `RateLimiter` compartido (presupuesto 80 %, 429 pausa global, 418 bloqueo + `is_banned`); preferir WS |
| K4 | MD | Order book desincronizado (huecos de secuencia) | Validación `U/u`, resync automático |
| K5 | MD | Datos obsoletos tras desconexión silenciosa | Timeout de inactividad + pausa de entradas (R5) |
| K6 | EXE | `-1021` por desfase de reloj | Sync con `/time`, `recvWindow` |
| K7 | BT | Backtest optimista (sin costes, look-ahead, sobreajuste) | `backtest-validation`, OOS, paridad de código |
| K8 | STR | Comisiones superan la ventaja por trade (típico en scalping). **Materializado:** stops de 12 bps vs 8 bps de coste → comisiones ≈ 0,75 R/trade, 6× el bruto | Stop mínimo ≥ 3× coste ida y vuelta; preferir maker; medir `fee_to_gross_ratio` en todo backtest |
| K9 | CFG | Fuga de API keys | Solo env vars, `.env` gitignored, claves sin permiso de retirada + whitelist IP |
| K10 | EXE | Errores de precisión (float) | `Decimal` + filtros de símbolo (modelos core rechazan `float`) |
| K11 | RSK | Liquidación en futuros por apalancamiento excesivo | Apalancamiento máx. en config; distancia SL ≪ distancia a liquidación |
| K12 | BT | Funding (cada 8 h) ignorado en backtest | Modelar funding en el modelo de costes |
| K13 | MD | Consumidor lento → backpressure en WS → datos con latencia creciente | ✅ Mitigado (T6): `OrderBookManager.is_tradeable` = SYNCED y latencia ≤ `max_latency_ms`; no se descartan deltas |
| K14 | MD | URLs/rutas WS de futuros cambian (Binance) → datos perdidos en silencio | ✅ T7/ADR-0005: rutas `/public`+`/market`; `combined_stream_url` rechaza streams mal enrutados; smoke test detecta contadores a 0 |
| K16 | BT/STR | Trade IDs de futuros no contiguos → `trade_count` (last−first+1) inexacto; volumen por minuto desde aggTrades difiere de klines en fronteras | Klines = verdad para volumen por vela; no usar `trade_count` como métrica exacta (ADR-0006) |
| K18 | STR | **Cerrado (T16):** MEAN_REVERSION sin ventaja: 24 variantes negativas, OOS −0,185 R (t −7,9), sin costes ≈ 0 R. Riesgo genérico: sobreajustar al buscar variantes | Familia descartada; toda hipótesis nueva sigue ADR-0008 (pre-registro + walk-forward) |
| K17 | BT | Sin depth histórico: estrategias basadas en order book (imbalance, `ORDER_FLOW_SQUEEZE`) no se pueden backtestear con data.binance.vision | Grabar el feed live (`/public` depth) a Parquet para backtests futuros; mientras, validar en paper |
| K19 | STR | **Barrera de costes estructural** a 1–5 min (T20: a 1 h baja a ≈ 0,07 R/trade): comisiones+slippage ≈ 0,3–0,4 R/trade (stops 25–40 bps). Dos familias sin ventaja bruta (T16, T18) | Exigir ventaja bruta ≫ 0,4 R o subir horizonte (stops ≥ 100 bps) / bajar costes (tier VIP, BNB) antes de nuevas hipótesis |
| K20 | STR/BT | Entradas maker sufren selección adversa (T18: −0,07 R sin costes vs ≈ 0 taker) | No asumir que maker mejora una señal; medirlo siempre con control sin costes |
| K21 | STR/BT | Potencia estadística insuficiente: efectos de ~+0,05 R requieren ~4 000 trades OOS para t ≥ 2; con 2 activos × 3 años a 1 h hay ~950 → riesgo de aceptar ruido o rechazar un efecto real | Ampliar activos (top líquidos USDT-M) y años (desde 2020) antes de decidir; no afinar parámetros sobre muestras pequeñas |
| K22 | STR | Deterioro temporal del efecto tendencia (OOS 2024 +0,13 R → 2026 −0,08 R) | Evaluar por año/régimen en todo experimento; exigir estabilidad, no solo media |
| K23 | BT | Sesgo de supervivencia en el universo (activos elegidos con información de hoy); EOS deslistado incluido para mitigar | Confirmaciones con activos no usados; declarar universo antes de mirar resultados |
| K24 | BT/STR | Re-selección frecuente de variantes con ventanas cortas persigue ruido (T21: OOS 0 vs regla fija +0,075 R in-sample) | Preferir reglas fijas pre-declaradas; si se selecciona, ventanas de train largas y pocas variantes |
| K25 | BT | Anomalías en datos de Binance (taker_buy > volumen en 2 velas 1m) | `repair_klines` en la ingesta, con log; validaciones del core las detectan |
| K15 | MD/EXE | Latencia geográfica alta (~365 ms media, 831 ms máx. desde el equipo local) → señales tardías, libro intermitentemente no operable | T11: medir desde VPS en Tokio (ap-northeast-1); ajustar `max_latency_ms`; no operar live desde el equipo local sin medirlo |

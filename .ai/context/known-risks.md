# Known risks

| ID | Área | Riesgo | Mitigación |
|---|---|---|---|
| K1 | RSK | Posición sin SL por fallo al colocarlo | R1: verificar SL tras fill; si falla → cerrar posición |
| K2 | EXE | Órdenes duplicadas por reintento tras timeout | `newClientOrderId` idempotente + consulta de estado (R8) |
| K3 | EXE | Baneo IP por rate limits (429→418) | Rate limiter por headers; preferir WS |
| K4 | MD | Order book desincronizado (huecos de secuencia) | Validación `U/u`, resync automático |
| K5 | MD | Datos obsoletos tras desconexión silenciosa | Timeout de inactividad + pausa de entradas (R5) |
| K6 | EXE | `-1021` por desfase de reloj | Sync con `/time`, `recvWindow` |
| K7 | BT | Backtest optimista (sin costes, look-ahead, sobreajuste) | `backtest-validation`, OOS, paridad de código |
| K8 | STR | Comisiones superan la ventaja por trade (típico en scalping) | Expectancy ≥ 2× coste; preferir maker |
| K9 | CFG | Fuga de API keys | Solo env vars, `.env` gitignored, claves sin permiso de retirada + whitelist IP |
| K10 | EXE | Errores de precisión (float) | `Decimal` + filtros de símbolo (modelos core rechazan `float`) |
| K11 | RSK | Liquidación en futuros por apalancamiento excesivo | Apalancamiento máx. en config; distancia SL ≪ distancia a liquidación |
| K12 | BT | Funding (cada 8 h) ignorado en backtest | Modelar funding en el modelo de costes |
| K13 | MD | Consumidor lento → backpressure en WS → datos con latencia creciente | ✅ Mitigado (T6): `OrderBookManager.is_tradeable` = SYNCED y latencia ≤ `max_latency_ms`; no se descartan deltas |
| K14 | MD | URLs/rutas WS de futuros cambian (Binance) → datos perdidos en silencio | ✅ T7/ADR-0005: rutas `/public`+`/market`; `combined_stream_url` rechaza streams mal enrutados; smoke test detecta contadores a 0 |
| K16 | BT/STR | Trade IDs de futuros no contiguos → `trade_count` (last−first+1) inexacto; volumen por minuto desde aggTrades difiere de klines en fronteras | Klines = verdad para volumen por vela; no usar `trade_count` como métrica exacta (ADR-0006) |
| K15 | MD/EXE | Latencia geográfica alta (~365 ms media, 831 ms máx. desde el equipo local) → señales tardías, libro intermitentemente no operable | T11: medir desde VPS en Tokio (ap-northeast-1); ajustar `max_latency_ms`; no operar live desde el equipo local sin medirlo |

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
| K13 | MD | Consumidor lento → backpressure en WS → datos con latencia creciente | Monitorizar `recv_time - event_time` y tamaño de cola; pausar entradas si supera umbral |
| K14 | MD | URLs WS de futuros cambian (Binance) → sin datos | URLs en `config/settings.py`; T7 verificación; stale timeout reconecta y alerta |

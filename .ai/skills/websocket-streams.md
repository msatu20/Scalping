# Skill: websocket-streams

## Checklist de un stream robusto
- [ ] Conexión combinada `/stream?streams=` cuando haya varios símbolos/streams (respetar límite de streams por conexión).
- [ ] Ping/pong según docs; timeout de inactividad → reconectar.
- [ ] Reconexión: backoff exponencial + jitter, tope máx.; reconexión proactiva antes de 24 h.
- [ ] Al reconectar: resincronizar estado (order book snapshot, últimas velas por REST).
- [ ] Parseo rápido (`orjson`), conversión a dataclasses tipadas; precios como `Decimal` o enteros escalados.
- [ ] Handler no bloqueante; trabajo pesado fuera (cola acotada; política de descarte documentada).
- [ ] Métricas: latencia evento→recepción, mensajes/s, reconexiones, huecos.

## Order book local (diff depth) — implementado en `market_data/order_book.py`
1. Abrir WS `<symbol>@depth@100ms` y bufferizar.
2. Snapshot REST `/fapi/v1/depth?limit=1000` (peso 20).
3. Descartar eventos con `u < lastUpdateId`; el primero aplicado debe cumplir `U <= lastUpdateId+1` y `u >= lastUpdateId` (futuros: `U <= lastUpdateId <= u`).
4. Cada evento siguiente: futuros `pu == prev_u` (spot `U == prev_u + 1`); si no → resincronizar.
5. Cantidad 0 → eliminar nivel. Libro cruzado tras aplicar → resincronizar.
6. Nunca leer el libro si no está SYNCED; no operar si la latencia supera el umbral.

## Tests mínimos
- Parseo de payload real (fixture JSON). · Hueco de secuencia → resync. · Desconexión simulada → reconexión y estado coherente.

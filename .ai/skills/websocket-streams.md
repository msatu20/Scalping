# Skill: websocket-streams

## Checklist de un stream robusto
- [ ] Conexión combinada `/stream?streams=` cuando haya varios símbolos/streams (respetar límite de streams por conexión).
- [ ] Ping/pong según docs; timeout de inactividad → reconectar.
- [ ] Reconexión: backoff exponencial + jitter, tope máx.; reconexión proactiva antes de 24 h.
- [ ] Al reconectar: resincronizar estado (order book snapshot, últimas velas por REST).
- [ ] Parseo rápido (`orjson`), conversión a dataclasses tipadas; precios como `Decimal` o enteros escalados.
- [ ] Handler no bloqueante; trabajo pesado fuera (cola acotada; política de descarte documentada).
- [ ] Métricas: latencia evento→recepción, mensajes/s, reconexiones, huecos.

## Order book local (diff depth)
1. Abrir WS `<symbol>@depth@100ms` y bufferizar.
2. Snapshot REST `depth?limit=1000`.
3. Descartar eventos con `u <= lastUpdateId`; primero válido debe cumplir `U <= lastUpdateId+1 <= u`.
4. Cada evento siguiente: `U == prev_u + 1` (futuros: `pu == prev_u`); si no → resincronizar.
5. Cantidad 0 → eliminar nivel.

## Tests mínimos
- Parseo de payload real (fixture JSON). · Hueco de secuencia → resync. · Desconexión simulada → reconexión y estado coherente.

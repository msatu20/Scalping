# Skill: testing

## Stack (definido en pyproject.toml)
`pytest` · `pytest-asyncio` · `hypothesis` (propiedades de indicadores/redondeo) · fixtures JSON de payloads reales en `tests/fixtures/`.

## Reglas
- Tests espejo de `src/`: `tests/<modulo>/test_<archivo>.py`.
- Sin red en tests unitarios: mockear REST/WS (exchange simulado). Tests contra testnet marcados `@pytest.mark.testnet`, fuera del run por defecto.
- Nunca usar claves reales en tests.
- Tiempo determinista (inyectar reloj); semillas fijas.
- Bug corregido = test de regresión.

## Comandos
- `pytest -q tests/<modulo>` — módulo afectado.
- `pytest -q` — suite completa antes de cerrar la tarea.
- `pytest -m testnet` — solo con autorización del usuario.
- `pytest -m live_readonly` — streams públicos reales (sin claves); smoke largo: `scripts/smoke_market_data.py --seconds 120`.

## Salida en el change-log
Comando ejecutado + resultado (n pasados/fallidos). Si se omitió algún test, decirlo.

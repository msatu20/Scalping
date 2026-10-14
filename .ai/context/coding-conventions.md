# Coding conventions (propuestas iniciales; ajustar con el primer código)

## Estilo
- Python 3.12+, PEP 8, type hints obligatorios; `ruff` (lint+format) y `mypy --strict` en `src/`.
- Nombres: módulos/funciones `snake_case`, clases `PascalCase`, constantes `UPPER_SNAKE`.
- Código e identificadores en inglés; documentación `.ai/` en español.
- Docstrings breves (qué y por qué), sin repetir el tipo.

## Dominio
- Dinero/cantidades: `decimal.Decimal` (nunca `float`). Indicadores: `float64` permitido.
- Timestamps: `int` ms UTC (como Binance); conversión a datetime solo en logs/informes.
- Símbolos en mayúsculas (`BTCUSDT`); lado `BUY`/`SELL` como `Enum`.
- Modelos de datos: `@dataclass(frozen=True, slots=True)` o pydantic en bordes (config, API).

## Async
- `asyncio` en todo I/O; sin `time.sleep`, sin `requests`.
- Cancelación limpia (`TaskGroup`); timeouts explícitos en toda llamada de red.

## Errores y logs
- Excepciones propias por dominio (`ExchangeError`, `RiskViolation`…). No `except Exception: pass`.
- Logging estructurado (JSON); nunca loguear claves ni firmas.

## Git
- Ramas `feat/…`, `fix/…`, `chore/…`; commits en imperativo. `main` protegido.
- `.gitignore`: `.env`, `data/`, `reports/*.csv`, `__pycache__/`, `.venv/`.

from collections.abc import Callable
from pathlib import Path

import pytest

BINANCE_FIXTURES = Path(__file__).parent / "fixtures" / "binance_futures"


@pytest.fixture
def binance_raw() -> Callable[[str], str]:
    """Load a raw Binance payload from ``tests/fixtures/binance_futures/``."""

    def load(name: str) -> str:
        return (BINANCE_FIXTURES / name).read_text(encoding="utf-8")

    return load

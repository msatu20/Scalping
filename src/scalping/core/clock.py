"""Injectable clock so live, backtest and tests share the same time source contract."""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def now_ms(self) -> int: ...


class SystemClock:
    """Wall clock, optionally corrected by the Binance server offset (``/fapi/v1/time``)."""

    def __init__(self, offset_ms: int = 0) -> None:
        self.offset_ms = offset_ms

    def now_ms(self) -> int:
        return time.time_ns() // 1_000_000 + self.offset_ms


class FixedClock:
    """Deterministic clock for tests and backtest replay."""

    def __init__(self, now_ms: int) -> None:
        self._now_ms = now_ms

    def now_ms(self) -> int:
        return self._now_ms

    def advance(self, ms: int) -> None:
        self.advance_to(self._now_ms + ms)

    def advance_to(self, ms: int) -> None:
        """Move to an absolute time; simulated time must never go backwards."""
        if ms < self._now_ms:
            raise ValueError(f"clock cannot go backwards: {ms} < {self._now_ms}")
        self._now_ms = ms

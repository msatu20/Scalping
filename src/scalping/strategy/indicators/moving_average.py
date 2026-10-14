"""Simple and exponential moving averages: batch (``sma``, ``ema``) and incremental classes.

EMA convention (TA-Lib style): ``alpha = 2 / (period + 1)``, seeded with the SMA of the
first ``period`` values; output is NaN/None during warm-up.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from scalping.strategy.indicators._core import (
    FloatArray,
    as_price,
    as_prices,
    check_period,
    nan_array,
    scalar_sum,
    window_sums,
)

# ------------------------------------------------------------------ SMA


def sma(values: Any, period: int) -> FloatArray:
    x = as_prices(values)
    n = check_period(period)
    out = nan_array(len(x))
    if len(x) >= n:
        out[n - 1 :] = window_sums(x, n) / n
    return out


class SMA:
    def __init__(self, period: int) -> None:
        self.period = check_period(period)
        self._window: deque[float] = deque(maxlen=self.period)
        self.value: float | None = None

    @property
    def ready(self) -> bool:
        return self.value is not None

    def update(self, value: Any) -> float | None:
        """Commit a closed candle (or tick) value."""
        self._window.append(as_price(value))
        if len(self._window) == self.period:
            self.value = scalar_sum(self._window) / self.period
        return self.value

    def peek(self, value: Any) -> float | None:
        """Value if ``value`` were committed now, without changing state (intra-candle)."""
        x = as_price(value)
        if len(self._window) < self.period - 1:
            return None
        window = list(self._window)[1:] if len(self._window) == self.period else list(self._window)
        window.append(x)
        return scalar_sum(window) / self.period


# ------------------------------------------------------------------ EMA


def ema_alpha(period: int) -> tuple[float, float]:
    alpha = 2.0 / (period + 1)
    return alpha, 1.0 - alpha


def ema_step(prev: float, x: float, alpha: float, beta: float) -> float:
    return alpha * x + beta * prev


def ema(values: Any, period: int) -> FloatArray:
    x = as_prices(values)
    n = check_period(period)
    out = nan_array(len(x))
    if len(x) < n:
        return out
    alpha, beta = ema_alpha(n)
    xs = x.tolist()
    prev = scalar_sum(xs[:n]) / n
    result = [prev]
    for v in xs[n:]:
        prev = ema_step(prev, v, alpha, beta)
        result.append(prev)
    out[n - 1 :] = result
    return out


class EMA:
    def __init__(self, period: int) -> None:
        self.period = check_period(period)
        self._alpha, self._beta = ema_alpha(self.period)
        self._seed: list[float] = []
        self.value: float | None = None

    @property
    def ready(self) -> bool:
        return self.value is not None

    def update(self, value: Any) -> float | None:
        x = as_price(value)
        if self.value is not None:
            self.value = ema_step(self.value, x, self._alpha, self._beta)
        else:
            self._seed.append(x)
            if len(self._seed) == self.period:
                self.value = scalar_sum(self._seed) / self.period
                self._seed.clear()
        return self.value

    def peek(self, value: Any) -> float | None:
        x = as_price(value)
        if self.value is not None:
            return ema_step(self.value, x, self._alpha, self._beta)
        if len(self._seed) == self.period - 1:
            return scalar_sum([*self._seed, x]) / self.period
        return None

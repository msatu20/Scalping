"""Bollinger Bands: batch (``bollinger``) and incremental (``BollingerBands``).

Middle = SMA(period); bands = middle ± num_std * std, with std the population standard
deviation (ddof=0) of the same window (TA-Lib / Bollinger's original definition).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, NamedTuple

import numpy as np

from scalping.strategy.indicators._core import (
    FloatArray,
    as_price,
    as_prices,
    check_period,
    nan_array,
    scalar_sq_dev_sum,
    scalar_sum,
    window_sq_dev_sums,
    window_sums,
)


class BollingerArrays(NamedTuple):
    middle: FloatArray
    upper: FloatArray
    lower: FloatArray


@dataclass(frozen=True, slots=True)
class BollingerValue:
    middle: float
    upper: float
    lower: float

    @property
    def bandwidth(self) -> float:
        """(upper - lower) / middle: squeeze detector."""
        return (self.upper - self.lower) / self.middle

    def percent_b(self, price: float) -> float:
        """Position of ``price`` in the band: 0 = lower, 1 = upper (0.5 if band is flat)."""
        width = self.upper - self.lower
        return 0.5 if width == 0.0 else (price - self.lower) / width


def _check_num_std(num_std: float) -> float:
    if not math.isfinite(num_std) or num_std <= 0:
        raise ValueError(f"num_std must be a positive finite number, got {num_std!r}")
    return float(num_std)


def bollinger(values: Any, period: int = 20, num_std: float = 2.0) -> BollingerArrays:
    x = as_prices(values)
    n = check_period(period)
    k = _check_num_std(num_std)
    middle, upper, lower = nan_array(len(x)), nan_array(len(x)), nan_array(len(x))
    if len(x) >= n:
        means = window_sums(x, n) / n
        std = np.sqrt(window_sq_dev_sums(x, n, means) / n)
        offset = k * std
        middle[n - 1 :] = means
        upper[n - 1 :] = means + offset
        lower[n - 1 :] = means - offset
    return BollingerArrays(middle, upper, lower)


def _bands(window: list[float] | deque[float], n: int, k: float) -> BollingerValue:
    mean = scalar_sum(window) / n
    offset = k * math.sqrt(scalar_sq_dev_sum(window, mean) / n)
    return BollingerValue(mean, mean + offset, mean - offset)


class BollingerBands:
    def __init__(self, period: int = 20, num_std: float = 2.0) -> None:
        self.period = check_period(period)
        self.num_std = _check_num_std(num_std)
        self._window: deque[float] = deque(maxlen=self.period)
        self.value: BollingerValue | None = None

    @property
    def ready(self) -> bool:
        return self.value is not None

    def update(self, value: Any) -> BollingerValue | None:
        self._window.append(as_price(value))
        if len(self._window) == self.period:
            self.value = _bands(self._window, self.period, self.num_std)
        return self.value

    def peek(self, value: Any) -> BollingerValue | None:
        x = as_price(value)
        if len(self._window) < self.period - 1:
            return None
        window = list(self._window)[1:] if len(self._window) == self.period else list(self._window)
        window.append(x)
        return _bands(window, self.period, self.num_std)

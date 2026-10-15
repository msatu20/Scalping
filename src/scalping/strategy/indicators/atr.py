"""Average True Range (Wilder): batch (``atr``) and incremental (``ATR``), bit-identical.

- True range from the second bar: ``TR = max(high - low, |high - prev_close|, |low - prev_close|)``.
- Seed: simple average of the first ``period`` TRs (bars 1..period) -> first value at index
  ``period`` (TA-Lib convention); then ``atr = (atr * (period - 1) + tr) / period``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from scalping.strategy.indicators._core import (
    FloatArray,
    as_price,
    as_prices,
    check_period,
    nan_array,
    scalar_sum,
)
from scalping.strategy.indicators.rsi import wilder_step


def true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(high: Any, low: Any, close: Any, period: int = 14) -> FloatArray:
    h, lo, c = as_prices(high), as_prices(low), as_prices(close)
    if not len(h) == len(lo) == len(c):
        raise ValueError("high, low and close must have the same length")
    if np.any(h < lo):
        raise ValueError("high must be >= low")
    n = check_period(period)
    out = nan_array(len(c))
    if len(c) <= n:
        return out
    hs, ls, cs = h.tolist(), lo.tolist(), c.tolist()
    trs = [true_range(hs[i], ls[i], cs[i - 1]) for i in range(1, len(cs))]
    value = scalar_sum(trs[:n]) / n
    result = [value]
    for tr in trs[n:]:
        value = wilder_step(value, tr, n)
        result.append(value)
    out[n:] = result
    return out


class ATR:
    def __init__(self, period: int = 14) -> None:
        self.period = check_period(period)
        self._prev_close: float | None = None
        self._seed: list[float] = []
        self.value: float | None = None

    @property
    def ready(self) -> bool:
        return self.value is not None

    def update(self, high: Any, low: Any, close: Any) -> float | None:
        h, lo, c = as_price(high), as_price(low), as_price(close)
        if h < lo:
            raise ValueError("high must be >= low")
        prev, self._prev_close = self._prev_close, c
        if prev is None:
            return None
        tr = true_range(h, lo, prev)
        if self.value is not None:
            self.value = wilder_step(self.value, tr, self.period)
        else:
            self._seed.append(tr)
            if len(self._seed) == self.period:
                self.value = scalar_sum(self._seed) / self.period
                self._seed.clear()
        return self.value

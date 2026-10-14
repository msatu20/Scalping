"""Wilder's RSI: batch (``rsi``) and incremental (``RSI``).

- Seed: simple average of the first ``period`` gains/losses (needs ``period + 1`` prices).
- Then Wilder smoothing: ``avg = (avg * (period - 1) + x) / period``.
- ``RSI = 100 * avg_gain / (avg_gain + avg_loss)`` (equivalent to ``100 - 100/(1+RS)``,
  defined when ``avg_loss == 0``); a perfectly flat window returns 50.
"""

from __future__ import annotations

from typing import Any

from scalping.strategy.indicators._core import (
    FloatArray,
    as_price,
    as_prices,
    check_period,
    nan_array,
    scalar_sum,
)


def _gain_loss(delta: float) -> tuple[float, float]:
    if delta > 0:
        return delta, 0.0
    if delta < 0:
        return 0.0, -delta
    return 0.0, 0.0


def wilder_step(avg: float, x: float, period: int) -> float:
    return (avg * (period - 1) + x) / period


def rsi_value(avg_gain: float, avg_loss: float) -> float:
    total = avg_gain + avg_loss
    return 50.0 if total == 0.0 else 100.0 * avg_gain / total


def rsi(values: Any, period: int = 14) -> FloatArray:
    x = as_prices(values)
    n = check_period(period)
    out = nan_array(len(x))
    if len(x) <= n:
        return out
    xs = x.tolist()
    seed = [_gain_loss(xs[i] - xs[i - 1]) for i in range(1, n + 1)]
    avg_gain = scalar_sum(g for g, _ in seed) / n
    avg_loss = scalar_sum(lo for _, lo in seed) / n
    result = [rsi_value(avg_gain, avg_loss)]
    for i in range(n + 1, len(xs)):
        gain, loss = _gain_loss(xs[i] - xs[i - 1])
        avg_gain = wilder_step(avg_gain, gain, n)
        avg_loss = wilder_step(avg_loss, loss, n)
        result.append(rsi_value(avg_gain, avg_loss))
    out[n:] = result
    return out


class RSI:
    def __init__(self, period: int = 14) -> None:
        self.period = check_period(period)
        self._prev: float | None = None
        self._seed: list[tuple[float, float]] = []
        self._avg_gain: float | None = None
        self._avg_loss: float = 0.0
        self.value: float | None = None

    @property
    def ready(self) -> bool:
        return self.value is not None

    def update(self, value: Any) -> float | None:
        x = as_price(value)
        prev, self._prev = self._prev, x
        if prev is None:
            return None
        gain, loss = _gain_loss(x - prev)
        if self._avg_gain is not None:
            self._avg_gain = wilder_step(self._avg_gain, gain, self.period)
            self._avg_loss = wilder_step(self._avg_loss, loss, self.period)
        else:
            self._seed.append((gain, loss))
            if len(self._seed) < self.period:
                return None
            self._avg_gain = scalar_sum(g for g, _ in self._seed) / self.period
            self._avg_loss = scalar_sum(lo for _, lo in self._seed) / self.period
            self._seed.clear()
        self.value = rsi_value(self._avg_gain, self._avg_loss)
        return self.value

    def peek(self, value: Any) -> float | None:
        x = as_price(value)
        if self._prev is None:
            return None
        gain, loss = _gain_loss(x - self._prev)
        if self._avg_gain is not None:
            return rsi_value(
                wilder_step(self._avg_gain, gain, self.period),
                wilder_step(self._avg_loss, loss, self.period),
            )
        if len(self._seed) == self.period - 1:
            seed = [*self._seed, (gain, loss)]
            avg_gain = scalar_sum(g for g, _ in seed) / self.period
            avg_loss = scalar_sum(lo for _, lo in seed) / self.period
            return rsi_value(avg_gain, avg_loss)
        return None

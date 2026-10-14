"""Order-flow features from aggTrades.

``AggressionTracker`` keeps per-second buckets of aggressive (taker) notional per side and
answers, in O(1) per trade: how much was bought/sold aggressively in the last
``window_s`` seconds, and what is the average for a window of that length over the last
``baseline_s`` seconds (completed seconds only, so the burst does not inflate its own
baseline).
"""

from __future__ import annotations

from collections import deque

from scalping.core.models import Side


class AggressionTracker:
    def __init__(self, window_s: int = 10, baseline_s: int = 3600) -> None:
        if not 0 < window_s < baseline_s:
            raise ValueError("require 0 < window_s < baseline_s")
        self.window_s = window_s
        self.baseline_s = baseline_s
        self._sec: int | None = None
        self._first_sec: int | None = None
        self._cur = [0.0, 0.0]  # [buy, sell] notional in the current second
        self._window: deque[tuple[int, float, float]] = deque()
        self._baseline: deque[tuple[int, float, float]] = deque()
        self._win_sum = [0.0, 0.0]
        self._base_sum = [0.0, 0.0]

    def update(self, time_ms: int, notional: float, aggressor: Side) -> None:
        sec = time_ms // 1000
        if self._sec is None:
            self._sec = self._first_sec = sec
        elif sec > self._sec:
            self._roll(sec)
        self._cur[0 if aggressor is Side.BUY else 1] += notional

    def _roll(self, sec: int) -> None:
        assert self._sec is not None
        bucket = (self._sec, self._cur[0], self._cur[1])
        for dq, sums in ((self._window, self._win_sum), (self._baseline, self._base_sum)):
            dq.append(bucket)
            sums[0] += bucket[1]
            sums[1] += bucket[2]
        self._evict(self._window, self._win_sum, sec - self.window_s)
        self._evict(self._baseline, self._base_sum, sec - self.baseline_s)
        self._sec = sec
        self._cur = [0.0, 0.0]

    @staticmethod
    def _evict(dq: deque[tuple[int, float, float]], sums: list[float], oldest_excl: int) -> None:
        while dq and dq[0][0] <= oldest_excl:
            _, buy, sell = dq.popleft()
            sums[0] -= buy
            sums[1] -= sell

    @property
    def ready(self) -> bool:
        """True once a full baseline period has been observed."""
        return (
            self._sec is not None
            and self._first_sec is not None
            and self._sec - self._first_sec >= self.baseline_s
        )

    def window(self, side: Side) -> float:
        """Aggressive notional of ``side`` in the last ``window_s`` s (incl. current second).

        The window deque keeps the ``window_s - 1`` completed seconds before the current one.
        """
        i = 0 if side is Side.BUY else 1
        return self._win_sum[i] + self._cur[i]

    def baseline(self, side: Side) -> float:
        """Average aggressive notional of ``side`` per ``window_s`` over the baseline period."""
        i = 0 if side is Side.BUY else 1
        return self._base_sum[i] * self.window_s / self.baseline_s

    def burst_ratio(self, side: Side) -> float:
        base = self.baseline(side)
        return self.window(side) / base if base > 0 else 0.0

"""Walk-forward evaluation over pre-computed backtest trades (T16).

Each variant is backtested once over the whole period (indicators only use past data,
so a variant's trades inside any window do not depend on later data). Then, for every
fold, the variant with the best *train* score is selected and judged on the following
*test* window it never saw. The concatenation of test windows is the out-of-sample
(OOS) estimate; the best full-period variant is reported only as an in-sample contrast.

Results are in R multiples (sizing without compounding), so windows are comparable.
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from scalping.backtest.replay import day_start_ms
from scalping.backtest.sim_broker import ClosedTrade


@dataclass(frozen=True, slots=True)
class TradeRecord:
    """Lightweight, picklable view of a closed trade."""

    symbol: str
    entry_time: int
    r: float
    net: float
    fees: float
    win: bool

    @classmethod
    def from_trade(cls, t: ClosedTrade) -> TradeRecord:
        return cls(t.symbol, t.entry.time, float(t.r_multiple), float(t.net_pnl), float(t.fees),
                   t.net_pnl > 0)  # fmt: skip


@dataclass(frozen=True, slots=True)
class Stats:
    trades: int
    total_r: float
    mean_r: float
    win_rate: float
    profit_factor: float
    max_drawdown_r: float
    t_stat: float  # mean / standard error: |t| < 2 is indistinguishable from zero

    @classmethod
    def of(cls, records: Sequence[TradeRecord]) -> Stats:
        n = len(records)
        if n == 0:
            return cls(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        rs = [r.r for r in records]
        total = sum(rs)
        mean = total / n
        gains = sum(r for r in rs if r > 0)
        losses = -sum(r for r in rs if r < 0)
        equity = peak = drawdown = 0.0
        for r in rs:
            equity += r
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        var = sum((r - mean) ** 2 for r in rs) / (n - 1) if n > 1 else 0.0
        t_stat = mean / math.sqrt(var / n) if var > 0 else 0.0
        return cls(
            trades=n,
            total_r=total,
            mean_r=mean,
            win_rate=sum(1 for r in records if r.win) / n,
            profit_factor=gains / losses if losses else math.inf if gains else 0.0,
            max_drawdown_r=drawdown,
            t_stat=t_stat,
        )


@dataclass(frozen=True, slots=True)
class Fold:
    train_start: date
    train_end: date  # inclusive
    test_start: date
    test_end: date  # inclusive

    def _contains(self, start: date, end: date, ms: int) -> bool:
        return day_start_ms(start) <= ms < day_start_ms(end) + 86_400_000

    def in_train(self, record: TradeRecord) -> bool:
        return self._contains(self.train_start, self.train_end, record.entry_time)

    def in_test(self, record: TradeRecord) -> bool:
        return self._contains(self.test_start, self.test_end, record.entry_time)


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def make_folds(start: date, end: date, train_months: int = 3, test_months: int = 1) -> list[Fold]:
    """Rolling folds: train ``train_months``, test the next ``test_months``, step = test."""
    folds: list[Fold] = []
    train_start = start
    while True:
        test_start = add_months(train_start, train_months)
        test_end = add_months(test_start, test_months) - timedelta(days=1)
        if test_end > end:
            return folds
        folds.append(Fold(train_start, test_start - timedelta(days=1), test_start, test_end))
        train_start = add_months(train_start, test_months)


@dataclass(frozen=True, slots=True)
class FoldResult:
    fold: Fold
    selected: str | None  # None: no variant met the minimum trades in train
    train: Stats
    test: Stats


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    folds: list[FoldResult]
    oos: Stats
    oos_records: list[TradeRecord]


def walk_forward(
    trades_by_variant: Mapping[str, Sequence[TradeRecord]],
    folds: Sequence[Fold],
    min_train_trades: int = 30,
) -> WalkForwardResult:
    """Select by highest train mean R (ties: more trades); never peeks at test windows."""
    results: list[FoldResult] = []
    oos: list[TradeRecord] = []
    for fold in folds:
        best: tuple[float, int, str] | None = None
        for name, records in trades_by_variant.items():
            train = Stats.of([r for r in records if fold.in_train(r)])
            if train.trades >= min_train_trades:
                key = (train.mean_r, train.trades, name)
                if best is None or key[:2] > best[:2]:
                    best = key
        if best is None:
            results.append(FoldResult(fold, None, Stats.of([]), Stats.of([])))
            continue
        name = best[2]
        records = trades_by_variant[name]
        test_records = [r for r in records if fold.in_test(r)]
        oos.extend(test_records)
        results.append(FoldResult(fold, name, Stats.of([r for r in records if fold.in_train(r)]),
                                  Stats.of(test_records)))  # fmt: skip
    return WalkForwardResult(results, Stats.of(oos), oos)

"""Walk-forward: folds, stats, selection uses train only, OOS = concatenated tests."""

import itertools
import math
from datetime import date

import pytest

from scalping.backtest import day_start_ms
from scalping.backtest.walk_forward import (
    Fold,
    Stats,
    TradeRecord,
    add_months,
    make_folds,
    walk_forward,
)


def rec(day: date, r: float) -> TradeRecord:
    return TradeRecord("BTCUSDT", day_start_ms(day) + 1, r, r * 50, 1.0, r > 0)


def test_add_months_clamps_day() -> None:
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2025, 11, 13), 3) == date(2026, 2, 13)


def test_make_folds_are_contiguous_and_cover_the_tail() -> None:
    folds = make_folds(date(2025, 10, 13), date(2026, 10, 12))
    assert len(folds) == 9
    assert folds[0] == Fold(
        date(2025, 10, 13), date(2026, 1, 12), date(2026, 1, 13), date(2026, 2, 12)
    )
    assert folds[-1].test_end == date(2026, 10, 12)
    for a, b in itertools.pairwise(folds):
        assert b.test_start == date.fromordinal(a.test_end.toordinal() + 1)
        assert a.train_end < a.test_start


def test_stats() -> None:
    s = Stats.of([rec(date(2026, 1, 1), r) for r in (1.0, -1.0, 2.0, -0.5)])
    assert (s.trades, s.total_r, s.mean_r, s.win_rate) == (4, 1.5, 0.375, 0.5)
    assert s.profit_factor == pytest.approx(2.0) and s.max_drawdown_r == 1.0
    assert s.t_stat == pytest.approx(
        0.375 / math.sqrt(sum((x - 0.375) ** 2 for x in (1, -1, 2, -0.5)) / 3 / 4)
    )
    assert Stats.of([]).trades == 0


def test_selection_uses_train_only_and_oos_concatenates_tests() -> None:
    fold = Fold(date(2026, 1, 1), date(2026, 3, 31), date(2026, 4, 1), date(2026, 4, 30))
    train_day, test_day = date(2026, 2, 1), date(2026, 4, 10)
    trades = {
        # great in train, bad in test: must still be selected (no peeking at test)
        "lucky": [rec(train_day, 1.0)] * 40 + [rec(test_day, -1.0)] * 5,
        # mediocre in train, great in test: must NOT be selected
        "honest": [rec(train_day, 0.1)] * 40 + [rec(test_day, 3.0)] * 5,
        # best train mean but too few trades
        "tiny": [rec(train_day, 5.0)] * 3,
    }
    result = walk_forward(trades, [fold], min_train_trades=30)
    (fr,) = result.folds
    assert fr.selected == "lucky"
    assert fr.test.trades == 5 and fr.test.mean_r == -1.0
    assert result.oos.total_r == -5.0 and len(result.oos_records) == 5


def test_fold_without_eligible_variant() -> None:
    fold = Fold(date(2026, 1, 1), date(2026, 3, 31), date(2026, 4, 1), date(2026, 4, 30))
    result = walk_forward({"few": [rec(date(2026, 2, 1), 1.0)]}, [fold], min_train_trades=30)
    assert result.folds[0].selected is None and result.oos.trades == 0

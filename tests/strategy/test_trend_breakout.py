"""TREND_BREAKOUT: channel excludes current bar, trend filter, ATR levels, clock."""

from decimal import Decimal

import pytest

from scalping.core import FixedClock, Kline, KlineInterval, Side, StrategyType
from scalping.strategy.indicators import atr
from scalping.strategy.signals import (
    SignalGenerator,
    TrendBreakoutParams,
    TrendBreakoutStrategy,
)

SYM = "BTCUSDT"
H = 3_600_000
T0 = 1_791_763_200_000
P = TrendBreakoutParams(channel=5, trend_ema=3, atr_period=3, atr_mult=2.0, target_r=2.0)


def bar(
    i: int, high: float, low: float, close: float, iv: KlineInterval = KlineInterval.H1
) -> Kline:
    ot = T0 + i * iv.ms
    close_time = ot + iv.ms - 1
    d = Decimal
    c, h, lo = d(repr(close)), d(repr(high)), d(repr(low))
    return Kline(
        SYM, iv, ot, close_time, c, h, lo, c, d(1), d(1), 1, d(0), True, close_time, close_time
    )


def run(strategy: TrendBreakoutStrategy, clock: FixedClock, bars: list[Kline]) -> list:
    out = []
    for b in bars:
        clock.advance_to(b.recv_time)
        if (s := strategy.on_event(b)) is not None:
            out.append(s)
    return out


def flat(n: int, start: int = 0) -> list[Kline]:
    return [bar(start + i, 101.0, 99.0, 100.0 + (0.1 if i % 2 else -0.1)) for i in range(n)]


def test_long_breakout_with_trend() -> None:
    clock = FixedClock(T0)
    strategy = TrendBreakoutStrategy([SYM], clock, P)
    bars = [*flat(8), bar(8, 103.0, 100.0, 102.5)]
    (s,) = run(strategy, clock, bars)
    assert s.side is Side.BUY and s.strategy is StrategyType.TREND_BREAKOUT
    assert s.created_at == bars[-1].recv_time and s.expires_at == s.created_at + H
    highs = [float(b.high) for b in bars]
    lows = [float(b.low) for b in bars]
    closes = [float(b.close) for b in bars]
    expected_atr = atr(highs, lows, closes, 3)[-1]
    risk = 2.0 * expected_atr
    assert float(s.stop_loss) == pytest.approx(102.5 - risk)
    assert float(s.take_profit) == pytest.approx(102.5 + 2 * risk)
    assert s.features["channel_level"] == 101.0


def test_current_bar_is_not_part_of_its_own_channel() -> None:
    clock = FixedClock(T0)
    strategy = TrendBreakoutStrategy([SYM], clock, P)
    # close 100.9 below the previous highs (101) even though its own high is 105
    assert run(strategy, clock, [*flat(8), bar(8, 105.0, 99.5, 100.9)]) == []


def test_breakout_against_trend_is_ignored() -> None:
    clock = FixedClock(T0)
    params = TrendBreakoutParams(channel=5, trend_ema=20, atr_period=3)
    strategy = TrendBreakoutStrategy([SYM], clock, params)
    falling = [bar(i, 121.0 - i, 119.0 - i, 120.0 - i) for i in range(25)]
    spike = bar(25, 101.5, 95.0, 101.0)  # above the 5-bar high (100) but below EMA20
    assert run(strategy, clock, [*falling, spike]) == []


def test_short_breakout_and_interval_filter() -> None:
    clock = FixedClock(T0)
    strategy = TrendBreakoutStrategy([SYM], clock, P)
    m15 = bar(0, 200.0, 1.0, 50.0, KlineInterval.M15)
    assert strategy.on_event(m15) is None  # other interval ignored
    (s,) = run(strategy, clock, [*flat(8), bar(8, 100.0, 96.0, 97.0)])
    assert s.side is Side.SELL and s.take_profit < s.reference_price < s.stop_loss
    assert isinstance(strategy, SignalGenerator)


def test_param_validation() -> None:
    with pytest.raises(ValueError):
        TrendBreakoutParams(channel=1)
    with pytest.raises(ValueError):
        TrendBreakoutParams(atr_mult=0)

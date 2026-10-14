"""STOP_HUNT_REBOUND + AggressionTracker."""

from collections.abc import Iterable
from decimal import Decimal

import pytest

from scalping.core import (
    AggregatedTrade,
    FixedClock,
    Kline,
    KlineInterval,
    MarketEvent,
    Side,
    Signal,
    StrategyType,
)
from scalping.strategy.orderflow import AggressionTracker
from scalping.strategy.signals import SignalGenerator, StopHuntParams, StopHuntReboundStrategy

SYM = "BTCUSDT"
T0 = 1_791_763_200_000  # 00:00 UTC
P = StopHuntParams(lookback_min=5, burst_window_s=5, baseline_s=60, burst_k=4.0)


def kline(minute: int, low: float = 99.9, high: float = 100.1) -> Kline:
    ot = T0 + minute * 60_000
    d = Decimal
    return Kline(SYM, KlineInterval.M1, ot, ot + 59_999, d("100"), d(repr(high)), d(repr(low)),
                 d("100"), d(1), d(100), 1, d(0), True, ot + 59_999, ot + 59_999)  # fmt: skip


_ids = iter(range(1, 10**9))


def trade(
    sec: float, price: float, qty: float = 0.1, sell_aggressor: bool = False
) -> AggregatedTrade:
    ms = T0 + int(sec * 1000)
    i = next(_ids)
    return AggregatedTrade(SYM, i, Decimal(repr(price)), Decimal(repr(qty)), i, i, ms,
                           sell_aggressor, ms, ms)  # fmt: skip


def calm_market() -> list[MarketEvent]:
    """5 minutes of balanced flow around 100 + closed candles: level_low 99.9, level_high 100.1."""
    events: list[MarketEvent] = [trade(s, 100.0, sell_aggressor=s % 2 == 0) for s in range(300)]
    events += [kline(m) for m in range(5)]
    return sorted(events, key=lambda e: e.recv_time)  # type: ignore[union-attr]


def run(
    strategy: StopHuntReboundStrategy, clock: FixedClock, events: Iterable[MarketEvent]
) -> list[Signal]:
    out = []
    for e in events:
        clock.advance_to(e.recv_time)  # type: ignore[union-attr]
        if (s := strategy.on_event(e)) is not None:
            out.append(s)
    return out


def make(params: StopHuntParams = P) -> tuple[StopHuntReboundStrategy, FixedClock]:
    clock = FixedClock(T0)
    strategy = StopHuntReboundStrategy([SYM], clock, params)
    run(strategy, clock, calm_market())
    return strategy, clock


# ------------------------------------------------------------------ AggressionTracker


def test_tracker_window_and_baseline() -> None:
    tr = AggressionTracker(window_s=5, baseline_s=60)
    for s in range(70):
        tr.update(T0 + s * 1000, 10.0, Side.SELL)
    assert tr.ready
    assert tr.window(Side.SELL) == pytest.approx(50.0)  # 5 seconds x 10
    assert tr.baseline(Side.SELL) == pytest.approx(59 * 10 * 5 / 60)  # completed seconds only
    assert tr.window(Side.BUY) == 0.0 and tr.burst_ratio(Side.BUY) == 0.0
    tr.update(T0 + 90_000, 100.0, Side.SELL)  # after a 20 s gap: old seconds evicted
    assert tr.window(Side.SELL) == pytest.approx(100.0)


def test_tracker_not_ready_before_baseline() -> None:
    tr = AggressionTracker(window_s=5, baseline_s=60)
    tr.update(T0, 1.0, Side.BUY)
    assert not tr.ready
    with pytest.raises(ValueError):
        AggressionTracker(window_s=60, baseline_s=60)


# ------------------------------------------------------------------ strategy


def test_long_signal_on_swept_and_reclaimed_low() -> None:
    strategy, clock = make()
    signals = run(strategy, clock, [
        trade(301, 99.85, qty=5, sell_aggressor=True),  # sweep below 99.9 - 3 bps with burst
        trade(302, 99.83, qty=1, sell_aggressor=True),  # deeper extreme
        trade(305, 99.95),  # reclaim above 99.9 + 1 bp
    ])  # fmt: skip
    (s,) = signals
    assert s.side is Side.BUY and s.strategy is StrategyType.STOP_HUNT_REBOUND
    assert s.created_at == T0 + 305_000 == clock.now_ms()
    assert s.reference_price == Decimal("99.95")
    risk = 99.95 * 25 / 10_000  # structural stop (16 bps) widened to 25 bps
    assert float(s.stop_loss) == pytest.approx(99.95 - risk)
    assert float(s.take_profit) == pytest.approx(99.95 + 1.5 * risk)
    assert s.features["extreme"] == 99.83 and s.features["burst_ratio"] >= 4
    assert s.expires_at == s.created_at + 30_000
    assert strategy.stats(SYM)["signals"] == 1


def test_short_signal_is_symmetric() -> None:
    strategy, clock = make()
    (s,) = run(
        strategy, clock, [trade(301, 100.15, qty=5), trade(305, 100.05, sell_aggressor=True)]
    )
    assert s.side is Side.SELL and s.take_profit < s.reference_price < s.stop_loss


def test_reclaim_without_burst_is_ignored() -> None:
    strategy, clock = make()
    assert run(strategy, clock, [trade(301, 99.85, sell_aggressor=True), trade(305, 99.95)]) == []
    assert strategy.stats(SYM)["reclaimed_without_burst"] == 1


def test_breakdown_and_expiry_drop_the_sweep() -> None:
    strategy, clock = make()
    run(strategy, clock, [trade(301, 99.85, qty=5, sell_aggressor=True), trade(302, 98.8)])
    assert strategy.stats(SYM)["breakdown"] == 1  # > 100 bps below the level

    strategy, clock = make()
    signals = run(
        strategy, clock, [trade(301, 99.85, qty=5, sell_aggressor=True), trade(362, 99.95)]
    )
    assert signals == [] and strategy.stats(SYM)["expired"] == 1


def test_rearm_and_cooldown() -> None:
    strategy, clock = make()
    run(strategy, clock, [trade(301, 99.85, qty=5, sell_aggressor=True), trade(305, 99.95)])
    # immediate new sweep: re-armed (price was back above the level) but in cool-down
    run(strategy, clock, [trade(310, 99.85, qty=5, sell_aggressor=True), trade(315, 99.95)])
    stats = strategy.stats(SYM)
    assert stats["signals"] == 1 and stats["sweeps"] == 1


def test_no_signals_before_levels_and_baseline() -> None:
    clock = FixedClock(T0)
    strategy = StopHuntReboundStrategy([SYM], clock, P)
    assert (
        run(strategy, clock, [trade(1, 90.0, qty=50, sell_aggressor=True), trade(2, 100.0)]) == []
    )
    assert isinstance(strategy, SignalGenerator)


def test_param_validation() -> None:
    with pytest.raises(ValueError):
        StopHuntParams(max_depth_bps=2.0, sweep_bps=3.0)

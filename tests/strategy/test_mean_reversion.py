"""MEAN_REVERSION signal: setup/trigger logic, clock usage, tick mode, filters, replay."""

import itertools
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from scalping.backtest import DataKind, HistoricalStore, ReplayFeed, day_start_ms
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
from scalping.strategy.indicators import bollinger
from scalping.strategy.signals import (
    MeanReversionParams,
    MeanReversionStrategy,
    SignalGenerator,
    TriggerMode,
)

DAY = date(2026, 10, 12)
T0 = day_start_ms(DAY)
SYM = "BTCUSDT"
LOOSE = MeanReversionParams(min_reward_risk=0.0)  # isolate setup/trigger logic from filters

BASE = [100.0, 100.2] * 15  # calm market: RSI ~50, narrow bands
DROP = [99.0, 98.0]  # 98.0 closes below the lower band (98.91) with RSI 28
REENTRY = 99.6  # closes back inside the band, below the middle


def kline(i: int, close: float, symbol: str = SYM, spread: float = 0.05) -> Kline:
    c = Decimal(repr(close))
    s = Decimal(repr(spread))
    open_time = T0 + i * 60_000
    return Kline(symbol, KlineInterval.M1, open_time, open_time + 59_999, c, c + s, c - s, c,
                 Decimal(1), Decimal(100), 10, Decimal("0.5"), True,
                 open_time + 59_999, open_time + 59_999)  # fmt: skip


def trade(ms: int, price: float, trade_id: int = 1) -> AggregatedTrade:
    return AggregatedTrade(SYM, trade_id, Decimal(repr(price)), Decimal("0.1"), trade_id,
                           trade_id, ms, False, ms, ms)  # fmt: skip


def run(
    strategy: MeanReversionStrategy, clock: FixedClock, events: Iterable[MarketEvent]
) -> list[Signal]:
    """Mimic the replay contract: advance the clock to recv_time, then dispatch."""
    out = []
    for e in events:
        clock.advance_to(e.recv_time)  # type: ignore[union-attr]
        if (s := strategy.on_event(e)) is not None:
            out.append(s)
    return out


def scenario(closes: list[float]) -> list[Kline]:
    return [kline(i, c) for i, c in enumerate(closes)]


def make(params: MeanReversionParams = LOOSE) -> tuple[MeanReversionStrategy, FixedClock]:
    clock = FixedClock(T0)
    return MeanReversionStrategy([SYM], clock, params), clock


# ------------------------------------------------------------------ core logic


def test_no_signal_in_calm_market_or_warmup() -> None:
    strategy, clock = make()
    assert run(strategy, clock, scenario(BASE)) == []
    assert strategy.setup_side(SYM) is None


def test_buy_signal_on_oversold_reentry() -> None:
    strategy, clock = make()
    closes = [*BASE, *DROP, REENTRY]
    signals = run(strategy, clock, scenario(closes))

    assert len(signals) == 1
    s = signals[0]
    middle = bollinger(closes, 20, 2.0).middle[-1]
    assert s.side is Side.BUY and s.strategy is StrategyType.MEAN_REVERSION
    assert s.created_at == clock.now_ms() == T0 + 32 * 60_000 + 59_999  # injected clock
    assert s.expires_at == s.created_at + 60_000 and not s.is_expired(s.created_at)
    assert s.reference_price == Decimal("99.6")
    assert float(s.take_profit) == middle  # target = mean
    extreme_low = 98.0 - 0.05
    assert float(s.stop_loss) == pytest.approx(extreme_low * (1 - 5 / 10_000))  # -5 bps
    assert s.stop_loss < s.reference_price < s.take_profit
    assert s.confidence is not None and 0.0 <= s.confidence <= 1.0
    assert s.features["extreme_rsi"] <= 30 and s.features["target_bps"] >= 12
    assert strategy.setup_side(SYM) is None  # consumed


def test_sell_signal_is_symmetric() -> None:
    strategy, clock = make()
    mirrored = [200.0 - c for c in [*BASE, *DROP, REENTRY]]
    (s,) = run(strategy, clock, scenario(mirrored))
    assert s.side is Side.SELL
    assert s.take_profit < s.reference_price < s.stop_loss
    assert s.features["extreme_rsi"] >= 70


def test_setup_expires_after_max_bars() -> None:
    params = MeanReversionParams(min_target_bps=10_000, max_setup_bars=2)  # never passes
    strategy, clock = make(params)
    run(strategy, clock, scenario([*BASE, *DROP, REENTRY]))
    assert strategy.setup_side(SYM) is Side.BUY  # 1 bar without valid trigger
    run(strategy, clock, [kline(33, REENTRY)])
    assert strategy.setup_side(SYM) is None
    assert strategy.stats(SYM)["rejected_target_below_fees"] == 2


def test_default_reward_risk_filter_rejects_poor_setups() -> None:
    strategy, clock = make(MeanReversionParams())
    assert run(strategy, clock, scenario([*BASE, *DROP, REENTRY])) == []
    assert strategy.stats(SYM)["rejected_reward_risk"] == 1


def test_signal_only_once_per_setup() -> None:
    strategy, clock = make()
    signals = run(strategy, clock, scenario([*BASE, *DROP, REENTRY, 99.65, 99.7]))
    assert len(signals) == 1


# ------------------------------------------------------------------ tick mode


def test_tick_mode_triggers_intra_candle_once() -> None:
    strategy, clock = make(MeanReversionParams(min_reward_risk=0.0, trigger=TriggerMode.TICK))
    run(strategy, clock, scenario([*BASE, *DROP]))
    assert strategy.setup_side(SYM) is Side.BUY

    candle = T0 + 32 * 60_000
    signals = run(strategy, clock, [
        trade(candle + 100, 97.9, 1),  # deeper: extends the extreme, no re-entry
        trade(candle + 200, 99.6, 2),  # re-entry -> signal
        trade(candle + 300, 99.6, 3),  # same candle: no second signal
    ])  # fmt: skip

    assert len(signals) == 1
    s = signals[0]
    assert s.created_at == candle + 200 and s.reference_price == Decimal("99.6")
    assert float(s.stop_loss) == pytest.approx(97.9 * (1 - 5 / 10_000))  # tick extreme
    assert "(tick)" in s.reason


def test_close_mode_ignores_trades() -> None:
    strategy, clock = make()
    run(strategy, clock, scenario([*BASE, *DROP]))
    assert run(strategy, clock, [trade(T0 + 32 * 60_000 + 1, 99.6)]) == []


def test_ignores_unknown_symbols_and_other_intervals() -> None:
    strategy, _ = make()
    assert strategy.on_event(kline(0, 100.0, symbol="ETHUSDT")) is None
    k5 = Kline(SYM, KlineInterval.M5, T0, T0 + 299_999, *[Decimal(100)] * 4, Decimal(1),
               Decimal(100), 1, Decimal(0), True, T0, T0)  # fmt: skip
    assert strategy.on_event(k5) is None


def test_protocol_and_param_validation() -> None:
    strategy, _ = make()
    assert isinstance(strategy, SignalGenerator)
    with pytest.raises(ValueError):
        MeanReversionParams(rsi_oversold=60)
    with pytest.raises(ValueError):
        MeanReversionParams(max_setup_bars=0)


def test_signal_expiry_validation() -> None:
    with pytest.raises(ValueError, match="expires_at"):
        Signal(SYM, Side.BUY, StrategyType.MEAN_REVERSION, Decimal(100), Decimal(99),
               Decimal(101), created_at=10, reason="x", expires_at=10)  # fmt: skip


# ------------------------------------------------------------------ replay integration


def test_runs_on_replay_engine_with_same_result(tmp_path: Path) -> None:
    closes = [*BASE, *DROP, REENTRY, *BASE[:5], *[200.0 - c for c in (*DROP, REENTRY)]]
    klines_df = pd.DataFrame({
        "open_time": [T0 + i * 60_000 for i in range(len(closes))],
        "open": closes, "high": [c + 0.05 for c in closes], "low": [c - 0.05 for c in closes],
        "close": closes, "volume": 1.0,
        "close_time": [T0 + i * 60_000 + 59_999 for i in range(len(closes))],
        "quote_volume": 100.0, "count": 10, "taker_buy_volume": 0.5,
        "taker_buy_quote_volume": 50.0,
    })  # fmt: skip
    store = HistoricalStore(tmp_path)
    store.write(klines_df, store.path(DataKind.KLINES, SYM, DAY))

    feed = ReplayFeed(store, [SYM], DAY, DAY, agg_trades=False)
    via_replay: list[Signal] = []
    strategy = MeanReversionStrategy([SYM], feed.clock, LOOSE, on_signal=via_replay.append)
    feed.replay(strategy.on_event)

    direct_strategy, clock = make()
    direct = run(direct_strategy, clock, scenario(closes))

    assert len(via_replay) >= 1
    assert [(s.side, s.created_at, s.reference_price, s.take_profit) for s in via_replay] == [
        (s.side, s.created_at, s.reference_price, s.take_profit) for s in direct
    ]
    assert all(a.created_at < b.created_at for a, b in itertools.pairwise(via_replay))


# ------------------------------------------------------------------ T16 extensions


def test_min_stop_widens_the_structural_stop() -> None:
    strategy, clock = make(MeanReversionParams(min_reward_risk=0.0, min_stop_bps=300))
    (s,) = run(strategy, clock, scenario([*BASE, *DROP, REENTRY]))
    assert float(s.stop_loss) == pytest.approx(99.6 * (1 - 0.03))  # 3 % > structural 1.7 %
    assert s.features["reward_risk"] == pytest.approx(
        (s.features["bb_middle"] - 99.6) / (99.6 * 0.03)
    )


def test_trend_filter_rejects_signals_in_strong_trends() -> None:
    params = MeanReversionParams(
        min_reward_risk=0.0, max_trend_bps=0.01, trend_fast=2, trend_slow=5
    )
    strategy, clock = make(params)
    assert run(strategy, clock, scenario([*BASE, *DROP, REENTRY])) == []
    assert strategy.stats(SYM)["rejected_trend"] == 1


def test_trend_filter_allows_ranging_market() -> None:
    params = MeanReversionParams(
        min_reward_risk=0.0, max_trend_bps=10_000, trend_fast=2, trend_slow=5
    )
    strategy, clock = make(params)
    assert len(run(strategy, clock, scenario([*BASE, *DROP, REENTRY]))) == 1

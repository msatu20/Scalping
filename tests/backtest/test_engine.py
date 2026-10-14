"""Backtester (replay + strategy + SimBroker), sizing and metrics."""

import dataclasses
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pandas as pd
import pytest

from scalping.backtest import (
    Backtester,
    ClosedTrade,
    CostModel,
    DataKind,
    ExitReason,
    Fill,
    HistoricalStore,
    Liquidity,
    PriceSource,
    SizingParams,
    compute_metrics,
    day_start_ms,
    position_size,
)
from scalping.core import Clock, Side, Signal, StrategyType
from scalping.strategy.signals import MeanReversionParams, MeanReversionStrategy, SignalHandler

DAY = date(2026, 10, 12)
T0 = day_start_ms(DAY)
SYM = "BTCUSDT"
# calm market, oversold drop, band re-entry, then reversion to the mean
CLOSES = [*[100.0, 100.2] * 15, 99.0, 98.0, 99.6, 99.8, 100.0, 100.3]


def write_klines(store: HistoricalStore, closes: list[float]) -> None:
    n = len(closes)
    frame = pd.DataFrame({
        "open_time": [T0 + i * 60_000 for i in range(n)],
        "open": closes, "high": [c + 0.05 for c in closes], "low": [c - 0.05 for c in closes],
        "close": closes, "volume": 1.0, "close_time": [T0 + i * 60_000 + 59_999 for i in range(n)],
        "quote_volume": 100.0, "count": 10, "taker_buy_volume": 0.5,
        "taker_buy_quote_volume": 50.0,
    })  # fmt: skip
    store.write(frame, store.path(DataKind.KLINES, SYM, DAY))


def factory(clock: Clock, on_signal: SignalHandler) -> MeanReversionStrategy:
    return MeanReversionStrategy([SYM], clock, MeanReversionParams(min_reward_risk=0.0), on_signal)


def test_end_to_end_backtest_on_klines(tmp_path: Path) -> None:
    store = HistoricalStore(tmp_path)
    write_klines(store, CLOSES)
    result = Backtester(store, [SYM], DAY, DAY, factory, price_source=PriceSource.KLINES).run()

    assert len(result.signals) == 1 and len(result.trades) == 1
    (t,) = result.trades
    signal = result.signals[0]
    # entry: open of the candle after the signal (99.8) + 1 bp; exit: TP at the mean (maker)
    assert t.entry.time == signal.created_at + 1
    assert t.entry.price == D("99.8") * D("1.0001")
    assert t.exit_reason is ExitReason.TAKE_PROFIT and t.exit.price == signal.take_profit
    assert t.exit.liquidity is Liquidity.MAKER
    assert t.net_pnl == t.gross_pnl - t.fees + t.funding
    m = result.metrics
    assert m.trades == 1 and m.wins == 1 and m.final_equity == D("10000") + t.net_pnl
    assert result.broker_stats["entry_taker"] == 1


def test_costs_reduce_pnl(tmp_path: Path) -> None:
    store = HistoricalStore(tmp_path)
    write_klines(store, CLOSES)
    free = CostModel(maker_fee=D(0), taker_fee=D(0), taker_slippage_bps=D(0))
    base = Backtester(store, [SYM], DAY, DAY, factory).run().metrics
    no_costs = Backtester(store, [SYM], DAY, DAY, factory, costs=free).run().metrics
    assert no_costs.fees == 0 and base.fees > 0
    assert base.net_pnl < no_costs.net_pnl


def make_signal(ref: str = "100", sl: str = "99") -> Signal:
    return Signal(SYM, Side.BUY, StrategyType.MEAN_REVERSION, D(ref), D(sl), D("103"), 0, "t")


def test_position_size_fixed_fractional_and_leverage_cap() -> None:
    p = SizingParams(initial_equity=D("10000"), risk_per_trade=D("0.005"), max_leverage=3)
    assert position_size(make_signal(), D("100"), D("10000"), p) == D("50.000")  # 50 / 1
    tight = make_signal(sl="99.99")  # risk sizing 5000 units -> capped at 3x: 300
    assert position_size(tight, D("100"), D("10000"), p) == D("300.000")
    assert position_size(make_signal(), D("99"), D("10000"), p) == D(0)  # entry at stop


def closed(net: str, gross: str = "0", fees: str = "0", risk: str = "10") -> ClosedTrade:
    f = Fill(0, D(1), D(1), Liquidity.TAKER, D(0))
    exit_fill = Fill(120_000, D(1), D(1), Liquidity.TAKER, D(0))
    return ClosedTrade(
        SYM, Side.BUY, StrategyType.MEAN_REVERSION, "id", D(1), f, exit_fill,
        ExitReason.TAKE_PROFIT, D(gross), D(fees), D(0), D(net), D(risk),
    )  # fmt: skip


def test_metrics() -> None:
    trades = [closed("10", "12", "2"), closed("-5", "-4", "1"), closed("-5", "-4", "1"),
              closed("20", "21", "1")]  # fmt: skip
    m = compute_metrics(trades, D("1000"))
    assert (m.trades, m.wins, m.win_rate) == (4, 2, 0.5)
    assert m.net_pnl == D("20") and m.fees == D("5")
    assert m.profit_factor == pytest.approx(3.0)
    assert m.max_drawdown == D("10") and m.max_drawdown_pct == pytest.approx(10 / 1010)
    assert m.expectancy_r == pytest.approx(0.5)
    assert m.avg_hold_minutes == 2.0 and m.final_equity == D("1020")
    assert m.fee_to_gross_ratio == pytest.approx(5 / 25)


def test_metrics_empty() -> None:
    m = compute_metrics([], D("1000"))
    assert m.trades == 0 and m.net_pnl == 0 and m.profit_factor == 0.0


def test_maker_entry_offset_and_non_compounding_sizing(tmp_path: Path) -> None:
    from scalping.core import ExecutionStyle

    store = HistoricalStore(tmp_path)
    write_klines(store, CLOSES)
    sizing = SizingParams(compounding=False)
    result = Backtester(store, [SYM], DAY, DAY, factory, entry_style=ExecutionStyle.MAKER,
                        maker_offset_bps=D(2), sizing=sizing).run()  # fmt: skip
    (signal,) = result.signals
    assert result.broker_stats["submitted"] == 1
    # limit 2 bps below the reference; the next candle's low (99.75) never trades through it
    assert result.trades == [] and result.broker_stats["expired"] == 1
    assert signal.reference_price == D("99.6")


def test_maker_offset_beyond_tight_stop_is_skipped(tmp_path: Path) -> None:
    from scalping.core import ExecutionStyle

    store = HistoricalStore(tmp_path)
    write_klines(store, CLOSES)
    # 5000 bps offset puts the buy limit far below the stop -> no order, counted skip
    result = Backtester(store, [SYM], DAY, DAY, factory, entry_style=ExecutionStyle.MAKER,
                        maker_offset_bps=D(5000)).run()  # fmt: skip
    assert result.skipped == {"entry_outside_brackets": 1}
    assert "submitted" not in result.broker_stats


def test_run_many_matches_individual_backtests(tmp_path: Path) -> None:
    from scalping.backtest import RunSpec, run_many
    from scalping.core import ExecutionStyle

    store = HistoricalStore(tmp_path)
    write_klines(store, CLOSES)
    specs = [
        RunSpec("taker", factory),
        RunSpec("maker", factory, entry_style=ExecutionStyle.MAKER, maker_offset_bps=D(1)),
        RunSpec("no-costs", factory, costs=CostModel(D(0), D(0), D(0))),
    ]
    together = run_many(store, [SYM], DAY, DAY, specs)
    for spec in specs:
        alone = Backtester(store, [SYM], DAY, DAY, spec.strategy_factory, costs=spec.costs,
                           entry_style=spec.entry_style,
                           maker_offset_bps=spec.maker_offset_bps).run()  # fmt: skip

        def strip(trades: list[ClosedTrade]) -> list[ClosedTrade]:
            return [dataclasses.replace(t, client_order_id="") for t in trades]  # random ids

        assert strip(together[spec.name].trades) == strip(alone.trades)
        assert together[spec.name].broker_stats == alone.broker_stats
    with pytest.raises(ValueError, match="unique"):
        run_many(store, [SYM], DAY, DAY, [specs[0], specs[0]])

"""SimBroker: maker/taker fills, slippage, SL/TP on trades and klines, funding, PnL."""

from decimal import Decimal as D

import pytest

from scalping.backtest import (
    CostModel,
    ExitReason,
    FundingEvent,
    FundingSchedule,
    Liquidity,
    PriceSource,
    SimBroker,
    TpStyle,
)
from scalping.core import (
    AggregatedTrade,
    ExecutionStyle,
    Kline,
    KlineInterval,
    OrderIntent,
    Side,
    StrategyType,
)

SYM = "BTCUSDT"
TAKER, MAKER = ExecutionStyle.TAKER, ExecutionStyle.MAKER


def intent(side: Side = Side.BUY, execution: ExecutionStyle = TAKER, entry: str = "100",
           qty: str = "2", created_at: int = 1000) -> OrderIntent:  # fmt: skip
    sl, tp = ("99", "102") if side is Side.BUY else ("101", "98")
    return OrderIntent(SYM, side, execution, D(qty), D(entry), D(sl), D(tp),
                       StrategyType.MEAN_REVERSION, created_at)  # fmt: skip


def trade(t: int, price: str) -> AggregatedTrade:
    return AggregatedTrade(SYM, t, D(price), D("0.1"), t, t, t, False, t, t)


def candle(i: int, o: str, h: str, low: str, c: str) -> Kline:
    ot = i * 60_000
    return Kline(SYM, KlineInterval.M1, ot, ot + 59_999, D(o), D(h), D(low), D(c), D(1), D(100),
                 1, D(0), True, ot + 59_999, ot + 59_999)  # fmt: skip


def feed(broker: SimBroker, *events: object) -> None:
    for e in events:
        broker.on_event(e)  # type: ignore[arg-type]


# ------------------------------------------------------------------ trades: taker / maker


def test_taker_long_entry_and_maker_take_profit_exact_pnl() -> None:
    broker = SimBroker()
    assert broker.submit(intent(), now=1000)
    feed(broker, trade(999, "50"))  # before submission: ignored
    feed(broker, trade(1001, "100"), trade(1002, "101"), trade(1003, "102"))  # TP touch only
    assert broker.has_position(SYM)
    feed(broker, trade(1004, "102.1"))  # trades through TP -> maker fill at TP

    (t,) = broker.trades
    assert t.entry.price == D("100.01") and t.entry.liquidity is Liquidity.TAKER  # +1 bp slip
    assert t.entry.fee == D("0.100010")  # 100.01 * 2 * 0.05 %
    assert t.exit.price == D("102") and t.exit.liquidity is Liquidity.MAKER
    assert t.exit.fee == D("0.0408")  # 102 * 2 * 0.02 %
    assert t.gross_pnl == D("3.98")
    assert t.net_pnl == D("3.98") - D("0.100010") - D("0.0408")
    assert t.exit_reason is ExitReason.TAKE_PROFIT and t.planned_risk == D("2")
    assert broker.equity == D("10000") + t.net_pnl


def test_stop_loss_gap_fills_at_trade_price_minus_slippage() -> None:
    broker = SimBroker()
    broker.submit(intent(), now=1000)
    feed(broker, trade(1001, "100"), trade(1002, "98.5"))  # gap far below SL 99
    (t,) = broker.trades
    assert t.exit_reason is ExitReason.STOP_LOSS and t.exit.liquidity is Liquidity.TAKER
    assert t.exit.price == D("98.49015")  # 98.5 * (1 - 1 bp): worse than the stop
    assert t.gross_pnl == (D("98.49015") - D("100.01")) * 2


def test_short_stop_on_touch() -> None:
    broker = SimBroker()
    broker.submit(intent(Side.SELL), now=1000)
    feed(broker, trade(1001, "100"), trade(1002, "101"))
    (t,) = broker.trades
    assert t.entry.price == D("99.99") and t.exit.price == D("101.0101")
    assert t.gross_pnl == -(D("101.0101") - D("99.99")) * 2


def test_maker_entry_post_only_and_fill_through() -> None:
    broker = SimBroker()
    feed(broker, trade(500, "100"))
    assert not broker.submit(intent(execution=MAKER, entry="100"), now=1000)  # would cross
    assert broker.stats["rejected_post_only"] == 1

    assert broker.submit(intent(execution=MAKER, entry="99.5"), now=1000)
    feed(broker, trade(1001, "99.5"))  # touch: queue position unknown -> no fill
    assert not broker.has_position(SYM)
    feed(broker, trade(1002, "99.4"))
    (fill,) = [broker._positions[SYM].entry]
    assert fill.price == D("99.5") and fill.liquidity is Liquidity.MAKER
    assert fill.fee == D("99.5") * 2 * D("0.0002")


def test_maker_fill_on_touch_option() -> None:
    broker = SimBroker(CostModel(maker_fill_on_touch=True))
    feed(broker, trade(500, "100"))
    broker.submit(intent(execution=MAKER, entry="99.5"), now=1000)
    feed(broker, trade(1001, "99.5"))
    assert broker.has_position(SYM)


def test_maker_entry_expires() -> None:
    broker = SimBroker()
    feed(broker, trade(500, "100"))
    broker.submit(intent(execution=MAKER, entry="99.5"), now=1000, expires_at=2000)
    feed(broker, trade(1500, "99.8"), trade(2000, "99.0"))  # at expiry: cancelled first
    assert not broker.is_busy(SYM) and broker.stats["expired"] == 1 and broker.trades == []


def test_take_profit_taker_style() -> None:
    broker = SimBroker(CostModel(tp_style=TpStyle.TAKER_MARKET))
    broker.submit(intent(), now=1000)
    feed(broker, trade(1001, "100"), trade(1002, "102"))
    (t,) = broker.trades
    assert t.exit.liquidity is Liquidity.TAKER and t.exit.price == D("101.9898")


def test_busy_and_close_all() -> None:
    broker = SimBroker()
    broker.submit(intent(), now=1000)
    assert not broker.submit(intent(), now=1000)
    feed(broker, trade(1001, "100"), trade(1002, "100.5"))
    broker.close_all(now=5000)
    (t,) = broker.trades
    assert t.exit_reason is ExitReason.END_OF_DATA and t.exit.price == D("100.5") * D("0.9999")
    assert broker.stats["rejected_busy"] == 1


# ------------------------------------------------------------------ funding


@pytest.mark.parametrize(("side", "expected"), [(Side.BUY, D("-0.0200")), (Side.SELL, D("0.0200"))])
def test_funding_paid_by_longs_received_by_shorts(side: Side, expected: D) -> None:
    schedule = FundingSchedule([
        FundingEvent(900, D("0.01"), D("100")),  # before entry: not applied
        FundingEvent(5000, D("0.0001"), D("100")),
    ])  # fmt: skip
    broker = SimBroker(funding={SYM: schedule})
    broker.submit(intent(side), now=1000)
    feed(broker, trade(1001, "100"), trade(6000, "100"))
    broker.close_all(now=6000)
    (t,) = broker.trades
    assert t.funding == expected
    assert t.net_pnl == t.gross_pnl - t.fees + expected
    assert broker.stats["funding_settlements"] == 1


# ------------------------------------------------------------------ klines (pessimistic)


def kline_broker() -> SimBroker:
    return SimBroker(price_source=PriceSource.KLINES)


def test_klines_taker_fills_next_open_and_ambiguous_candle_is_stop() -> None:
    broker = kline_broker()
    broker.submit(intent(created_at=59_999), now=59_999)  # at close of candle 0
    feed(broker, candle(1, "100", "100.5", "99.5", "100.2"))
    assert broker._positions[SYM].entry.price == D("100.01")
    feed(broker, candle(2, "100.2", "103", "98.9", "101"))  # SL and TP both inside
    (t,) = broker.trades
    assert t.exit_reason is ExitReason.STOP_LOSS and t.exit.price == D("99") * D("0.9999")


def test_klines_gap_through_stop_fills_at_open() -> None:
    broker = kline_broker()
    broker.submit(intent(created_at=59_999), now=59_999)
    feed(broker, candle(1, "100", "100.5", "99.5", "100.2"), candle(2, "98", "98.5", "97", "98"))
    (t,) = broker.trades
    assert t.exit.price == D("98") * D("0.9999") and t.exit.time == 2 * 60_000


def test_klines_no_target_in_entry_candle() -> None:
    broker = kline_broker()
    broker.submit(intent(created_at=59_999), now=59_999)
    feed(broker, candle(1, "100", "103", "99.5", "102.5"))  # TP inside entry candle: ignored
    assert broker.has_position(SYM)
    feed(broker, candle(2, "102.5", "102.6", "101", "102"))
    (t,) = broker.trades
    assert t.exit_reason is ExitReason.TAKE_PROFIT and t.exit.price == D("102")


def test_klines_stop_checked_in_entry_candle() -> None:
    broker = kline_broker()
    broker.submit(intent(created_at=59_999), now=59_999)
    feed(broker, candle(1, "100", "100.5", "98.8", "99.5"))
    assert broker.trades[0].exit_reason is ExitReason.STOP_LOSS


def test_klines_maker_entry_needs_trade_through() -> None:
    broker = kline_broker()
    feed(broker, candle(0, "100", "100.2", "99.9", "100"))
    broker.submit(intent(execution=MAKER, entry="99.5", created_at=59_999), now=59_999,
                  expires_at=59_999 + 120_000)  # fmt: skip
    feed(broker, candle(1, "100", "100.1", "99.5", "99.9"))  # low == limit: no fill
    assert not broker.has_position(SYM)
    feed(broker, candle(2, "99.9", "100", "99.4", "99.8"))
    assert broker._positions[SYM].entry.price == D("99.5")


def test_klines_ignores_other_intervals() -> None:
    broker = kline_broker()
    broker.submit(intent(created_at=59_999), now=59_999)
    m5 = Kline(SYM, KlineInterval.M5, 60_000, 359_999, D(100), D(100), D(100), D(100), D(1),
               D(100), 1, D(0), True, 359_999, 359_999)  # fmt: skip
    feed(broker, m5)
    assert not broker.has_position(SYM)  # only the 1m price path fills orders

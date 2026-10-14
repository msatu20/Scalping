from decimal import Decimal as D

import pytest

from scalping.core import (
    AggregatedTrade,
    ExecutionStyle,
    FixedClock,
    Kline,
    KlineInterval,
    OrderBookDelta,
    OrderBookImbalance,
    OrderBookSnapshot,
    OrderIntent,
    PriceLevel,
    Side,
    Signal,
    StrategyType,
)

T0 = 1_760_000_000_000


def lv(price: str, qty: str) -> PriceLevel:
    return PriceLevel(D(price), D(qty))


def make_book(**overrides: object) -> OrderBookSnapshot:
    kwargs: dict[str, object] = dict(
        symbol="BTCUSDT",
        last_update_id=100,
        bids=(lv("100.0", "3"), lv("99.9", "1")),
        asks=(lv("100.1", "1"), lv("100.2", "1")),
        timestamp=T0,
    )
    kwargs.update(overrides)
    return OrderBookSnapshot(**kwargs)  # type: ignore[arg-type]


def make_signal(side: Side = Side.BUY, sl: str = "99", tp: str = "102") -> Signal:
    return Signal(
        symbol="BTCUSDT",
        side=side,
        strategy=StrategyType.MEAN_REVERSION,
        reference_price=D("100"),
        stop_loss=D(sl),
        take_profit=D(tp),
        created_at=T0,
        reason="test",
    )


# ------------------------------------------------------------------ Kline


def make_kline(**overrides: object) -> Kline:
    kwargs: dict[str, object] = dict(
        symbol="ETHUSDT",
        interval=KlineInterval.M1,
        open_time=T0,
        close_time=T0 + 59_999,
        open=D("10"),
        high=D("12"),
        low=D("9"),
        close=D("11"),
        volume=D("5"),
        quote_volume=D("55"),
        trades=7,
        taker_buy_volume=D("3"),
        is_closed=True,
        event_time=T0 + 60_000,
        recv_time=T0 + 60_010,
    )
    kwargs.update(overrides)
    return Kline(**kwargs)  # type: ignore[arg-type]


def test_kline_valid_and_taker_sell_volume() -> None:
    assert make_kline().taker_sell_volume == D("2")


@pytest.mark.parametrize("overrides", [{"high": D("10.5")}, {"low": D("10.5")}])
def test_kline_rejects_inconsistent_ohlc(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        make_kline(**overrides)


def test_kline_rejects_float_prices() -> None:
    with pytest.raises(TypeError):
        make_kline(close=11.0)


# ------------------------------------------------------------------ Order book


def test_snapshot_derived_prices() -> None:
    book = make_book()
    assert book.mid_price == D("100.05")
    assert book.spread == D("0.1")


def test_snapshot_rejects_crossed_book() -> None:
    with pytest.raises(ValueError, match="crossed"):
        make_book(asks=(lv("99.95", "1"),))


def test_snapshot_rejects_unsorted_bids() -> None:
    with pytest.raises(ValueError, match="bids"):
        make_book(bids=(lv("99.9", "1"), lv("100.0", "1")))


def test_imbalance_from_snapshot() -> None:
    obi = OrderBookImbalance.from_snapshot(make_book(), levels=2)
    assert (obi.bid_qty, obi.ask_qty) == (D("4"), D("2"))
    assert obi.value == pytest.approx(1 / 3)


def test_imbalance_empty_is_neutral() -> None:
    assert OrderBookImbalance("BTCUSDT", T0, 5, D(0), D(0)).value == 0.0


def delta(U: int, u: int, pu: int | None) -> OrderBookDelta:
    return OrderBookDelta("BTCUSDT", U, u, pu, (), (), T0, None, T0)


def test_delta_continuity_futures_uses_pu() -> None:
    assert delta(150, 160, pu=149).is_continuation_of(149)
    assert not delta(150, 160, pu=148).is_continuation_of(149)


def test_delta_continuity_spot_uses_U() -> None:
    assert delta(150, 160, pu=None).is_continuation_of(149)
    assert not delta(151, 160, pu=None).is_continuation_of(149)


# ------------------------------------------------------------------ Aggregated trade


@pytest.mark.parametrize(("buyer_maker", "aggressor"), [(True, Side.SELL), (False, Side.BUY)])
def test_agg_trade_aggressor_side(buyer_maker: bool, aggressor: Side) -> None:
    t = AggregatedTrade("BTCUSDT", 1, D("100"), D("0.5"), 10, 12, T0, buyer_maker, T0, T0)
    assert t.aggressor_side is aggressor
    assert t.notional == D("50.0")
    assert t.trade_count == 3


# ------------------------------------------------------------------ Signal / OrderIntent


def test_signal_reward_risk() -> None:
    assert make_signal().reward_risk == D("2")


@pytest.mark.parametrize(
    ("side", "sl", "tp"),
    [
        (Side.BUY, "101", "102"),  # SL above entry
        (Side.BUY, "99", "99.5"),  # TP below entry
        (Side.SELL, "99", "98"),  # SL below entry
    ],
)
def test_signal_rejects_wrong_brackets(side: Side, sl: str, tp: str) -> None:
    with pytest.raises(ValueError):
        make_signal(side, sl, tp)


def test_sell_signal_valid() -> None:
    assert make_signal(Side.SELL, sl="101", tp="98").side is Side.SELL


def test_order_intent_from_signal() -> None:
    intent = OrderIntent.from_signal(
        make_signal(), quantity=D("0.5"), execution=ExecutionStyle.MAKER, created_at=T0
    )
    assert intent.stop_loss == D("99") and intent.take_profit == D("102")
    assert intent.notional == D("50.0")
    assert intent.risk_amount == D("0.5")
    assert intent.client_order_id.startswith("scp-") and len(intent.client_order_id) <= 36


def test_order_intent_requires_sl_and_tp() -> None:
    with pytest.raises(TypeError):
        OrderIntent(  # type: ignore[call-arg]
            symbol="BTCUSDT",
            side=Side.BUY,
            execution=ExecutionStyle.TAKER,
            quantity=D("1"),
            entry_price=D("100"),
            strategy=StrategyType.ORDER_FLOW_SQUEEZE,
            created_at=T0,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"quantity": D("0")},
        {"quantity": D("NaN")},
        {"symbol": "btc/usdt"},
        {"client_order_id": "x" * 37},
        {"stop_loss": D("100")},
    ],
)
def test_order_intent_rejects_invalid(overrides: dict[str, object]) -> None:
    kwargs: dict[str, object] = dict(
        symbol="BTCUSDT",
        side=Side.BUY,
        execution=ExecutionStyle.MAKER,
        quantity=D("1"),
        entry_price=D("100"),
        stop_loss=D("99"),
        take_profit=D("102"),
        strategy=StrategyType.STOP_HUNT_REBOUND,
        created_at=T0,
    )
    kwargs.update(overrides)
    with pytest.raises((ValueError, TypeError)):
        OrderIntent(**kwargs)  # type: ignore[arg-type]


def test_models_are_immutable() -> None:
    with pytest.raises(AttributeError):
        make_signal().stop_loss = D("0")  # type: ignore[misc]


def test_fixed_clock() -> None:
    clock = FixedClock(T0)
    clock.advance(250)
    assert clock.now_ms() == T0 + 250

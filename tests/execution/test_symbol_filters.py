"""T15: exchange filters from real exchangeInfo, safe-side rounding, validation."""

import json
from decimal import Decimal as D

import pytest

from scalping.core import ExecutionStyle, OrderIntent, Side, StrategyType
from scalping.execution.symbol_filters import (
    FilterViolation,
    SymbolFilters,
    apply_filters,
    parse_exchange_info,
)
from tests.conftest import BINANCE_FIXTURES

FILTERS = parse_exchange_info(json.loads((BINANCE_FIXTURES / "exchange_info.json").read_text()))
BTC = FILTERS["BTCUSDT"]


def intent(side: Side = Side.BUY, execution: ExecutionStyle = ExecutionStyle.MAKER,
           qty: str = "0.0127", entry: str = "64250.17", sl: str = "64100.03",
           tp: str = "64600.09", symbol: str = "BTCUSDT") -> OrderIntent:  # fmt: skip
    if side is Side.SELL:
        sl, tp = tp, sl
    return OrderIntent(symbol, side, execution, D(qty), D(entry), D(sl), D(tp),
                       StrategyType.MEAN_REVERSION, 0)  # fmt: skip


def test_parse_real_exchange_info() -> None:
    assert set(FILTERS) == {"BTCUSDT", "ETHUSDT"}
    assert (BTC.tick_size, BTC.step_size, BTC.min_notional) == (D("0.10"), D("0.001"), D("50"))
    assert BTC.market_max_qty == D("120") and FILTERS["ETHUSDT"].tick_size == D("0.01")


def test_buy_maker_rounds_to_the_safe_side() -> None:
    original = intent()
    out = apply_filters(original, BTC)
    assert out.entry_price == D("64250.1")  # limit down: not more aggressive
    assert out.stop_loss == D("64100.1")  # stop up: smaller risk
    assert out.take_profit == D("64600.0")  # target down: closer
    assert out.quantity == D("0.012")  # qty down
    assert out.risk_amount <= original.risk_amount
    assert out.client_order_id == original.client_order_id  # identity preserved


def test_sell_maker_mirrors_rounding() -> None:
    out = apply_filters(intent(Side.SELL), BTC)
    assert out.entry_price == D("64250.2")  # limit up
    assert out.stop_loss == D("64600.0")  # stop down
    assert out.take_profit == D("64100.1")  # target up


def test_taker_entry_rounds_to_nearest_and_uses_market_lot() -> None:
    out = apply_filters(intent(execution=ExecutionStyle.TAKER, qty="0.0019"), BTC)
    assert out.entry_price == D("64250.2") and out.quantity == D("0.001")


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"qty": "0.0004"}, "rounds to zero"),
        ({"qty": "0.0007"}, "rounds to zero"),
        ({"qty": "0.0009", "entry": "64250", "sl": "64000", "tp": "65000"}, "rounds to zero"),
        ({"qty": "0.001", "entry": "40000", "sl": "39000", "tp": "41000"}, "notional"),
        ({"qty": "130", "execution": ExecutionStyle.TAKER}, "outside"),
        ({"entry": "64250.12", "sl": "64250.11", "tp": "64300"}, "collapse"),
    ],
)
def test_violations(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(FilterViolation, match=match):
        apply_filters(intent(**kwargs), BTC)  # type: ignore[arg-type]


def test_wrong_symbol() -> None:
    with pytest.raises(ValueError):
        apply_filters(intent(symbol="ETHUSDT"), BTC)


def test_round_helpers() -> None:
    f = SymbolFilters("XUSDT", D("0.5"), D("0.5"), D("1000"), D("0.01"), D("0.01"), D("10"),
                      D("0.1"), D("0.1"), D("5"), D("5"))  # fmt: skip
    assert f.round_qty(D("1.239"), market=False) == D("1.23")
    assert f.round_qty(D("1.239"), market=True) == D("1.2")

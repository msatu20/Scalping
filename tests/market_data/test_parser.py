import json
from collections.abc import Callable
from decimal import Decimal as D

import pytest

from scalping.core import (
    AggregatedTrade,
    Kline,
    KlineInterval,
    OrderBookDelta,
    OrderBookImbalance,
    PriceLevel,
    Side,
)
from scalping.market_data import ParseError, parse_depth_snapshot, parse_message

RECV = 1_760_400_000_999

Loader = Callable[[str], str]


def test_depth_update(binance_raw: Loader) -> None:
    event = parse_message(binance_raw("depth_update.json"), RECV)

    assert isinstance(event, OrderBookDelta)
    assert event.symbol == "BTCUSDT"
    assert (event.first_update_id, event.final_update_id) == (8123456700, 8123456712)
    assert event.prev_final_update_id == 8123456699
    assert event.bids == (PriceLevel(D("64250.10"), D("1.250")), PriceLevel(D("64249.90"), D("0")))
    assert event.asks[1] == PriceLevel(D("64251.00"), D("3.100"))
    assert (event.event_time, event.transaction_time, event.recv_time) == (
        1760400000123,
        1760400000120,
        RECV,
    )
    assert event.is_continuation_of(8123456699)


def test_agg_trade_from_combined_stream(binance_raw: Loader) -> None:
    event = parse_message(binance_raw("agg_trade_combined.json"), RECV)

    assert isinstance(event, AggregatedTrade)
    assert event.symbol == "BTCUSDT"
    assert event.price == D("64250.10") and event.qty == D("0.125")
    assert event.aggressor_side is Side.SELL  # m=true -> buyer is maker
    assert event.trade_count == 4
    assert event.trade_time == 1760400000148


def test_kline(binance_raw: Loader) -> None:
    event = parse_message(binance_raw("kline_1m.json"), RECV)

    assert isinstance(event, Kline)
    assert event.symbol == "ETHUSDT" and event.interval is KlineInterval.M1
    assert (event.open, event.high, event.low, event.close) == (
        D("2510.25"),
        D("2513.40"),
        D("2509.90"),
        D("2512.80"),
    )
    assert event.volume == D("1832.551") and event.taker_buy_volume == D("1012.300")
    assert event.taker_sell_volume == D("820.251")
    assert event.trades == 291 and event.is_closed


def test_prices_are_exact_decimals(binance_raw: Loader) -> None:
    event = parse_message(binance_raw("kline_1m.json"), RECV)
    assert isinstance(event, Kline)
    assert str(event.close) == "2512.80"  # no float round-trip


def test_depth_snapshot_rest(binance_raw: Loader) -> None:
    data = json.loads(binance_raw("depth_snapshot_rest.json"))
    book = parse_depth_snapshot("BTCUSDT", data, RECV)

    assert book.last_update_id == 8123456690
    assert book.timestamp == 1760399999985
    assert book.best_bid == PriceLevel(D("64250.00"), D("2.104"))
    assert book.spread == D("0.20")
    obi = OrderBookImbalance.from_snapshot(book, levels=3)
    assert (obi.bid_qty, obi.ask_qty) == (D("3.616"), D("6.650"))


@pytest.mark.parametrize(
    "raw",
    [
        '{"result":null,"id":1}',
        '{"e":"markPriceUpdate","E":1,"s":"BTCUSDT","p":"1"}',
        '{"stream":"btcusdt@markPrice","data":{"e":"markPriceUpdate"}}',
    ],
)
def test_ignored_messages_return_none(raw: str) -> None:
    assert parse_message(raw, RECV) is None


def test_bytes_frames_are_accepted(binance_raw: Loader) -> None:
    assert isinstance(
        parse_message(binance_raw("depth_update.json").encode(), RECV), OrderBookDelta
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("p"),  # missing field
        lambda d: d.update(p="abc"),  # non-numeric price
        lambda d: d.update(q="-1"),  # negative qty rejected by model
        lambda d: d.update(p=64250.1),  # float instead of string
    ],
)
def test_malformed_agg_trade_raises(binance_raw: Loader, mutate: Callable[[dict], object]) -> None:
    msg = json.loads(binance_raw("agg_trade_combined.json"))
    mutate(msg["data"])
    with pytest.raises(ParseError):
        parse_message(json.dumps(msg), RECV)


@pytest.mark.parametrize("raw", ["not json", "[1, 2]"])
def test_invalid_frames_raise(raw: str) -> None:
    with pytest.raises(ParseError):
        parse_message(raw, RECV)


def test_unsupported_kline_interval_raises(binance_raw: Loader) -> None:
    msg = json.loads(binance_raw("kline_1m.json"))
    msg["k"]["i"] = "1h"
    with pytest.raises(ParseError):
        parse_message(json.dumps(msg), RECV)


def test_bad_snapshot_raises() -> None:
    with pytest.raises(ParseError):
        parse_depth_snapshot("BTCUSDT", {"lastUpdateId": 1, "bids": [["1", "x"]], "asks": []}, RECV)

import pytest

from scalping.core import KlineInterval
from scalping.market_data import (
    StreamRoute,
    agg_trade_stream,
    combined_stream_url,
    default_streams,
    depth_stream,
    kline_stream,
    route_of,
    routed_stream_urls,
)

BASE = "wss://fstream.binance.com"


def test_stream_names() -> None:
    assert depth_stream("BTCUSDT") == "btcusdt@depth@100ms"
    assert depth_stream("BTCUSDT", speed_ms=250) == "btcusdt@depth"
    assert agg_trade_stream("ETHUSDT") == "ethusdt@aggTrade"
    assert kline_stream("ETHUSDT", KlineInterval.M5) == "ethusdt@kline_5m"


def test_invalid_depth_speed() -> None:
    with pytest.raises(ValueError):
        depth_stream("BTCUSDT", speed_ms=50)


@pytest.mark.parametrize(
    ("stream", "route"),
    [
        ("btcusdt@depth@100ms", StreamRoute.PUBLIC),
        ("btcusdt@depth20@100ms", StreamRoute.PUBLIC),
        ("btcusdt@bookTicker", StreamRoute.PUBLIC),
        ("!bookTicker", StreamRoute.PUBLIC),
        ("btcusdt@aggTrade", StreamRoute.MARKET),
        ("btcusdt@kline_1m", StreamRoute.MARKET),
        ("btcusdt@markPrice@1s", StreamRoute.MARKET),
        ("!forceOrder@arr", StreamRoute.MARKET),
    ],
)
def test_route_of(stream: str, route: StreamRoute) -> None:
    assert route_of(stream) is route


def test_combined_url_includes_route() -> None:
    url = combined_stream_url(f"{BASE}/", StreamRoute.MARKET, ["a@aggTrade", "b@kline_1m"])
    assert url == f"{BASE}/market/stream?streams=a@aggTrade/b@kline_1m"


def test_combined_url_rejects_misrouted_streams() -> None:
    with pytest.raises(ValueError, match="route"):
        combined_stream_url(BASE, StreamRoute.PUBLIC, ["btcusdt@aggTrade"])


def test_combined_url_limits() -> None:
    with pytest.raises(ValueError):
        combined_stream_url(BASE, StreamRoute.MARKET, [])
    with pytest.raises(ValueError):
        combined_stream_url(BASE, StreamRoute.MARKET, ["s@aggTrade"] * 201)


def test_routed_stream_urls_split_by_route() -> None:
    urls = routed_stream_urls(BASE, default_streams(["BTCUSDT"], [KlineInterval.M1]))
    assert urls == {
        StreamRoute.PUBLIC: f"{BASE}/public/stream?streams=btcusdt@depth@100ms",
        StreamRoute.MARKET: f"{BASE}/market/stream?streams=btcusdt@aggTrade/btcusdt@kline_1m",
    }


def test_default_streams() -> None:
    streams = default_streams(["BTCUSDT", "ETHUSDT"], [KlineInterval.M1])
    assert streams == [
        "btcusdt@depth@100ms",
        "btcusdt@aggTrade",
        "btcusdt@kline_1m",
        "ethusdt@depth@100ms",
        "ethusdt@aggTrade",
        "ethusdt@kline_1m",
    ]

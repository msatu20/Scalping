import pytest

from scalping.core import KlineInterval
from scalping.market_data import (
    agg_trade_stream,
    combined_stream_url,
    default_streams,
    depth_stream,
    kline_stream,
)


def test_stream_names() -> None:
    assert depth_stream("BTCUSDT") == "btcusdt@depth@100ms"
    assert depth_stream("BTCUSDT", speed_ms=250) == "btcusdt@depth"
    assert agg_trade_stream("ETHUSDT") == "ethusdt@aggTrade"
    assert kline_stream("ETHUSDT", KlineInterval.M5) == "ethusdt@kline_5m"


def test_invalid_depth_speed() -> None:
    with pytest.raises(ValueError):
        depth_stream("BTCUSDT", speed_ms=50)


def test_combined_url() -> None:
    url = combined_stream_url("wss://fstream.binance.com/", ["a@aggTrade", "b@depth"])
    assert url == "wss://fstream.binance.com/stream?streams=a@aggTrade/b@depth"


def test_combined_url_limits() -> None:
    with pytest.raises(ValueError):
        combined_stream_url("wss://x", [])
    with pytest.raises(ValueError):
        combined_stream_url("wss://x", ["s"] * 201)


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

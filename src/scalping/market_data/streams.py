"""Binance USDⓈ-M Futures stream names and combined-stream URLs."""

from __future__ import annotations

from collections.abc import Sequence

from scalping.core.models import KlineInterval

# Binance limit for streams per combined connection.
MAX_STREAMS_PER_CONNECTION = 200

_DEPTH_SPEEDS_MS = (100, 250, 500)


def depth_stream(symbol: str, speed_ms: int = 100) -> str:
    if speed_ms not in _DEPTH_SPEEDS_MS:
        raise ValueError(f"speed_ms must be one of {_DEPTH_SPEEDS_MS}")
    suffix = "" if speed_ms == 250 else f"@{speed_ms}ms"  # 250 ms is the default stream
    return f"{symbol.lower()}@depth{suffix}"


def agg_trade_stream(symbol: str) -> str:
    return f"{symbol.lower()}@aggTrade"


def kline_stream(symbol: str, interval: KlineInterval) -> str:
    return f"{symbol.lower()}@kline_{interval.value}"


def combined_stream_url(ws_base_url: str, streams: Sequence[str]) -> str:
    if not streams:
        raise ValueError("at least one stream is required")
    if len(streams) > MAX_STREAMS_PER_CONNECTION:
        raise ValueError(f"max {MAX_STREAMS_PER_CONNECTION} streams per connection")
    return f"{ws_base_url.rstrip('/')}/stream?streams={'/'.join(streams)}"


def default_streams(symbols: Sequence[str], intervals: Sequence[KlineInterval]) -> list[str]:
    """Depth (100 ms) + aggTrade + klines for every symbol."""
    streams: list[str] = []
    for symbol in symbols:
        streams.append(depth_stream(symbol))
        streams.append(agg_trade_stream(symbol))
        streams.extend(kline_stream(symbol, interval) for interval in intervals)
    return streams

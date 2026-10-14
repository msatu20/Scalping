"""Binance USDⓈ-M Futures stream names and routed combined-stream URLs.

Since 2026 Binance splits futures WS traffic by route (ADR-0005):
``/public`` (book: depth, bookTicker) and ``/market`` (aggTrade, kline, markPrice, ...).
Legacy ``/stream`` and ``/ws`` only deliver ``/public`` data: requesting aggTrade or
kline there fails silently (no error, no frames).
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from scalping.core.models import KlineInterval

# Binance limit for streams per combined connection.
MAX_STREAMS_PER_CONNECTION = 200

_DEPTH_SPEEDS_MS = (100, 250, 500)


class StreamRoute(StrEnum):
    PUBLIC = "public"
    MARKET = "market"


def depth_stream(symbol: str, speed_ms: int = 100) -> str:
    if speed_ms not in _DEPTH_SPEEDS_MS:
        raise ValueError(f"speed_ms must be one of {_DEPTH_SPEEDS_MS}")
    suffix = "" if speed_ms == 250 else f"@{speed_ms}ms"  # 250 ms is the default stream
    return f"{symbol.lower()}@depth{suffix}"


def agg_trade_stream(symbol: str) -> str:
    return f"{symbol.lower()}@aggTrade"


def kline_stream(symbol: str, interval: KlineInterval) -> str:
    return f"{symbol.lower()}@kline_{interval.value}"


def route_of(stream: str) -> StreamRoute:
    name = stream.split("@", 1)[1] if "@" in stream else stream
    if name.startswith(("depth", "bookTicker")) or stream == "!bookTicker":
        return StreamRoute.PUBLIC
    return StreamRoute.MARKET


def combined_stream_url(ws_base_url: str, route: StreamRoute, streams: Sequence[str]) -> str:
    if not streams:
        raise ValueError("at least one stream is required")
    if len(streams) > MAX_STREAMS_PER_CONNECTION:
        raise ValueError(f"max {MAX_STREAMS_PER_CONNECTION} streams per connection")
    misrouted = [s for s in streams if route_of(s) is not route]
    if misrouted:
        raise ValueError(f"streams {misrouted} do not belong to route /{route}")
    return f"{ws_base_url.rstrip('/')}/{route}/stream?streams={'/'.join(streams)}"


def routed_stream_urls(ws_base_url: str, streams: Sequence[str]) -> dict[StreamRoute, str]:
    """One combined URL per route that has at least one stream."""
    by_route: dict[StreamRoute, list[str]] = {}
    for stream in streams:
        by_route.setdefault(route_of(stream), []).append(stream)
    return {
        route: combined_stream_url(ws_base_url, route, route_streams)
        for route, route_streams in by_route.items()
    }


def default_streams(symbols: Sequence[str], intervals: Sequence[KlineInterval]) -> list[str]:
    """Depth (100 ms) + aggTrade + klines for every symbol."""
    streams: list[str] = []
    for symbol in symbols:
        streams.append(depth_stream(symbol))
        streams.append(agg_trade_stream(symbol))
        streams.extend(kline_stream(symbol, interval) for interval in intervals)
    return streams

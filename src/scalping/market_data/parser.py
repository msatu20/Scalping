"""Binance USDⓈ-M Futures raw payloads -> core models.

Pure functions, no I/O. Prices/quantities arrive as strings and are converted to
``Decimal`` without passing through ``float`` (R6).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from scalping.core.models import (
    AggregatedTrade,
    Kline,
    KlineInterval,
    MarketEvent,
    OrderBookDelta,
    OrderBookSnapshot,
    PriceLevel,
)

type Payload = Mapping[str, Any]


class ParseError(ValueError):
    """Raw payload does not match the expected Binance schema."""


_PARSE_FAILURES = (KeyError, TypeError, ValueError, InvalidOperation)


def _dec(value: object) -> Decimal:
    """Binance sends numbers as strings; a JSON float would already have lost precision."""
    if not isinstance(value, str):
        raise TypeError(f"expected numeric string, got {type(value).__name__}: {value!r}")
    return Decimal(value)


def _levels(raw: Sequence[Sequence[str]]) -> tuple[PriceLevel, ...]:
    return tuple(PriceLevel(_dec(price), _dec(qty)) for price, qty in raw)


def parse_depth_update(data: Payload, recv_time: int) -> OrderBookDelta:
    """``depthUpdate`` event from ``<symbol>@depth[@100ms|@500ms]``."""
    return OrderBookDelta(
        symbol=data["s"],
        first_update_id=data["U"],
        final_update_id=data["u"],
        prev_final_update_id=data.get("pu"),
        bids=_levels(data["b"]),
        asks=_levels(data["a"]),
        event_time=data["E"],
        transaction_time=data.get("T"),
        recv_time=recv_time,
    )


def parse_agg_trade(data: Payload, recv_time: int) -> AggregatedTrade:
    """``aggTrade`` event from ``<symbol>@aggTrade``."""
    return AggregatedTrade(
        symbol=data["s"],
        agg_trade_id=data["a"],
        price=_dec(data["p"]),
        qty=_dec(data["q"]),
        first_trade_id=data["f"],
        last_trade_id=data["l"],
        trade_time=data["T"],
        is_buyer_maker=data["m"],
        event_time=data["E"],
        recv_time=recv_time,
    )


def parse_kline(data: Payload, recv_time: int) -> Kline:
    """``kline`` event from ``<symbol>@kline_<interval>``."""
    k = data["k"]
    return Kline(
        symbol=k["s"],
        interval=KlineInterval(k["i"]),
        open_time=k["t"],
        close_time=k["T"],
        open=_dec(k["o"]),
        high=_dec(k["h"]),
        low=_dec(k["l"]),
        close=_dec(k["c"]),
        volume=_dec(k["v"]),
        quote_volume=_dec(k["q"]),
        trades=k["n"],
        taker_buy_volume=_dec(k["V"]),
        is_closed=k["x"],
        event_time=data["E"],
        recv_time=recv_time,
    )


def parse_depth_snapshot(symbol: str, data: Payload, recv_time: int) -> OrderBookSnapshot:
    """REST ``GET /fapi/v1/depth`` response (symbol is not included in the payload)."""
    try:
        return OrderBookSnapshot(
            symbol=symbol,
            last_update_id=data["lastUpdateId"],
            bids=_levels(data["bids"]),
            asks=_levels(data["asks"]),
            timestamp=data.get("T") or data.get("E") or recv_time,
        )
    except _PARSE_FAILURES as exc:
        raise ParseError(f"bad depth snapshot for {symbol}: {exc!r}") from exc


_EVENT_PARSERS: dict[str, Callable[[Payload, int], MarketEvent]] = {
    "depthUpdate": parse_depth_update,
    "aggTrade": parse_agg_trade,
    "kline": parse_kline,
}


def parse_message(raw: str | bytes, recv_time: int) -> MarketEvent | None:
    """Parse one WS frame (raw or combined-stream wrapper).

    Returns ``None`` for control frames (e.g. ``{"result": null, "id": 1}``) and event
    types without a parser. Raises ``ParseError`` for malformed payloads.
    """
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(msg, dict):
        raise ParseError(f"expected JSON object, got {type(msg).__name__}")

    data = msg["data"] if "stream" in msg and "data" in msg else msg
    event_type = data.get("e") if isinstance(data, dict) else None
    parser = _EVENT_PARSERS.get(event_type) if isinstance(event_type, str) else None
    if parser is None:
        return None
    try:
        return parser(data, recv_time)
    except _PARSE_FAILURES as exc:
        raise ParseError(f"bad {event_type} payload: {exc!r}") from exc

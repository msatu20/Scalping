"""Shared domain models (contracts between market_data, strategy, risk, execution and backtest).

- Hot path: immutable dataclasses with slots (no pydantic overhead per event).
- Prices and quantities are ``Decimal`` (invariant R6); derived metrics may be ``float``.
- Timestamps are ``int`` milliseconds UTC, as delivered by Binance.
- Symbols use Binance native notation (``BTCUSDT``); ccxt conversion lives in ``execution``.
"""

from __future__ import annotations

import itertools
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

# --------------------------------------------------------------------------- enums


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def opposite(self) -> Side:
        return Side.SELL if self is Side.BUY else Side.BUY


class ExecutionStyle(StrEnum):
    MAKER = "MAKER"  # LIMIT + timeInForce=GTX (post-only)
    TAKER = "TAKER"  # MARKET


class StrategyType(StrEnum):
    MEAN_REVERSION = "MEAN_REVERSION"
    STOP_HUNT_REBOUND = "STOP_HUNT_REBOUND"
    ORDER_FLOW_SQUEEZE = "ORDER_FLOW_SQUEEZE"


class KlineInterval(StrEnum):
    M1 = "1m"
    M3 = "3m"
    M5 = "5m"


# --------------------------------------------------------------------------- validation helpers

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")
# Binance newClientOrderId rule.
_CLIENT_ORDER_ID_RE = re.compile(r"^[\.A-Z\:/a-z0-9_-]{1,36}$")


def _require_decimal(name: str, value: object, *, allow_zero: bool = False) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite, got {value}")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} must be {'>= 0' if allow_zero else '> 0'}, got {value}")


def _require_symbol(symbol: str) -> None:
    if not _SYMBOL_RE.match(symbol):
        raise ValueError(f"invalid symbol {symbol!r}; expected Binance format like 'BTCUSDT'")


def _require_brackets(side: Side, entry: Decimal, stop_loss: Decimal, take_profit: Decimal) -> None:
    """SL and TP must sit on opposite sides of the entry (R1)."""
    for name, value in (("entry", entry), ("stop_loss", stop_loss), ("take_profit", take_profit)):
        _require_decimal(name, value)
    levels = f"sl={stop_loss} entry={entry} tp={take_profit}"
    if side is Side.BUY and not (stop_loss < entry < take_profit):
        raise ValueError(f"BUY requires stop_loss < entry < take_profit ({levels})")
    if side is Side.SELL and not (take_profit < entry < stop_loss):
        raise ValueError(f"SELL requires take_profit < entry < stop_loss ({levels})")


def _new_client_order_id() -> str:
    return f"scp-{uuid.uuid4().hex[:28]}"


# --------------------------------------------------------------------------- market data


@dataclass(frozen=True, slots=True)
class Kline:
    symbol: str
    interval: KlineInterval
    open_time: int
    close_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal
    trades: int
    taker_buy_volume: Decimal
    is_closed: bool
    event_time: int
    recv_time: int

    def __post_init__(self) -> None:
        for name in ("open", "high", "low", "close"):
            _require_decimal(name, getattr(self, name))
        for name in ("volume", "quote_volume", "taker_buy_volume"):
            _require_decimal(name, getattr(self, name), allow_zero=True)
        body_high, body_low = max(self.open, self.close), min(self.open, self.close)
        if self.high < max(body_high, self.low) or self.low > body_low:
            raise ValueError(f"inconsistent OHLC: {self.open}/{self.high}/{self.low}/{self.close}")
        if self.taker_buy_volume > self.volume:
            raise ValueError("taker_buy_volume cannot exceed volume")
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be after open_time")

    @property
    def taker_sell_volume(self) -> Decimal:
        return self.volume - self.taker_buy_volume


@dataclass(frozen=True, slots=True)
class PriceLevel:
    price: Decimal
    qty: Decimal  # 0 inside a delta means "remove level"

    def __post_init__(self) -> None:
        _require_decimal("price", self.price)
        _require_decimal("qty", self.qty, allow_zero=True)


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    """Full book state: bids sorted by price desc, asks asc."""

    symbol: str
    last_update_id: int
    bids: tuple[PriceLevel, ...]
    asks: tuple[PriceLevel, ...]
    timestamp: int

    def __post_init__(self) -> None:
        if any(prev.price <= nxt.price for prev, nxt in itertools.pairwise(self.bids)):
            raise ValueError("bids must be strictly descending by price")
        if any(prev.price >= nxt.price for prev, nxt in itertools.pairwise(self.asks)):
            raise ValueError("asks must be strictly ascending by price")
        if self.bids and self.asks and self.bids[0].price >= self.asks[0].price:
            raise ValueError(f"crossed book: bid {self.bids[0].price} >= ask {self.asks[0].price}")

    @property
    def best_bid(self) -> PriceLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> PriceLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> Decimal | None:
        if not (self.bids and self.asks):
            return None
        return (self.bids[0].price + self.asks[0].price) / 2

    @property
    def spread(self) -> Decimal | None:
        if not (self.bids and self.asks):
            return None
        return self.asks[0].price - self.bids[0].price


@dataclass(frozen=True, slots=True)
class OrderBookDelta:
    """Diff depth event (``<symbol>@depth@100ms``): U, u and, on futures, pu."""

    symbol: str
    first_update_id: int  # U
    final_update_id: int  # u
    prev_final_update_id: int | None  # pu (futures only)
    bids: tuple[PriceLevel, ...]
    asks: tuple[PriceLevel, ...]
    event_time: int
    transaction_time: int | None
    recv_time: int

    def __post_init__(self) -> None:
        if self.first_update_id > self.final_update_id:
            raise ValueError("first_update_id (U) must be <= final_update_id (u)")

    def is_continuation_of(self, last_final_update_id: int) -> bool:
        """True if no events were lost since ``last_final_update_id``; otherwise resync."""
        if self.prev_final_update_id is not None:
            return self.prev_final_update_id == last_final_update_id
        return self.first_update_id == last_final_update_id + 1


@dataclass(frozen=True, slots=True)
class AggregatedTrade:
    """``<symbol>@aggTrade``: base for aggression, volume spikes and stop-sweep detection."""

    symbol: str
    agg_trade_id: int
    price: Decimal
    qty: Decimal
    first_trade_id: int
    last_trade_id: int
    trade_time: int
    is_buyer_maker: bool
    event_time: int
    recv_time: int

    def __post_init__(self) -> None:
        _require_decimal("price", self.price)
        _require_decimal("qty", self.qty)
        if self.first_trade_id > self.last_trade_id:
            raise ValueError("first_trade_id must be <= last_trade_id")

    @property
    def aggressor_side(self) -> Side:
        # Buyer is maker -> the seller crossed the spread (aggressive sell).
        return Side.SELL if self.is_buyer_maker else Side.BUY

    @property
    def notional(self) -> Decimal:
        return self.price * self.qty

    @property
    def trade_count(self) -> int:
        """Upper bound only: futures trade IDs are not contiguous (ADR-0006, K16)."""
        return self.last_trade_id - self.first_trade_id + 1


@dataclass(frozen=True, slots=True)
class OrderBookImbalance:
    """Buy/sell pressure over the top ``levels`` of the book, in [-1, 1] (+1 = all bids)."""

    symbol: str
    timestamp: int
    levels: int
    bid_qty: Decimal
    ask_qty: Decimal

    def __post_init__(self) -> None:
        if self.levels < 1:
            raise ValueError("levels must be >= 1")
        _require_decimal("bid_qty", self.bid_qty, allow_zero=True)
        _require_decimal("ask_qty", self.ask_qty, allow_zero=True)

    @property
    def value(self) -> float:
        total = self.bid_qty + self.ask_qty
        if total == 0:
            return 0.0
        return float((self.bid_qty - self.ask_qty) / total)

    @classmethod
    def from_snapshot(cls, book: OrderBookSnapshot, levels: int) -> OrderBookImbalance:
        return cls(
            symbol=book.symbol,
            timestamp=book.timestamp,
            levels=levels,
            bid_qty=sum((lvl.qty for lvl in book.bids[:levels]), Decimal(0)),
            ask_qty=sum((lvl.qty for lvl in book.asks[:levels]), Decimal(0)),
        )


type MarketEvent = Kline | OrderBookSnapshot | OrderBookDelta | AggregatedTrade


# --------------------------------------------------------------------------- strategy / execution


@dataclass(frozen=True, slots=True)
class Signal:
    """Strategy output. Proposes protective levels; risk decides size and final validation.

    Invalidation: price (``stop_loss``) and time (``expires_at``: do not act on the signal
    at or after this ms). ``confidence`` is the signal strength in [0, 1]; ``features``
    holds the indicator values that produced it (for audit and analysis).
    """

    symbol: str
    side: Side
    strategy: StrategyType
    reference_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    created_at: int
    reason: str
    confidence: float | None = None
    expires_at: int | None = None
    features: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        _require_brackets(self.side, self.reference_price, self.stop_loss, self.take_profit)
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")

    def is_expired(self, now_ms: int) -> bool:
        return self.expires_at is not None and now_ms >= self.expires_at

    @property
    def reward_risk(self) -> Decimal:
        reward = abs(self.take_profit - self.reference_price)
        return reward / abs(self.reference_price - self.stop_loss)


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """Risk-approved entry order. SL and TP are mandatory from creation (R1).

    ``entry_price`` is the limit price for MAKER and the expected fill price for TAKER.
    """

    symbol: str
    side: Side
    execution: ExecutionStyle
    quantity: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    strategy: StrategyType
    created_at: int
    client_order_id: str = field(default_factory=_new_client_order_id)

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        _require_decimal("quantity", self.quantity)
        _require_brackets(self.side, self.entry_price, self.stop_loss, self.take_profit)
        if not _CLIENT_ORDER_ID_RE.match(self.client_order_id):
            raise ValueError(f"invalid client_order_id {self.client_order_id!r}")

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.entry_price

    @property
    def risk_amount(self) -> Decimal:
        """Loss in quote currency if the stop is hit at its price (before fees/slippage)."""
        return self.quantity * abs(self.entry_price - self.stop_loss)

    @classmethod
    def from_signal(
        cls,
        signal: Signal,
        *,
        quantity: Decimal,
        execution: ExecutionStyle,
        created_at: int,
        entry_price: Decimal | None = None,
    ) -> OrderIntent:
        return cls(
            symbol=signal.symbol,
            side=signal.side,
            execution=execution,
            quantity=quantity,
            entry_price=signal.reference_price if entry_price is None else entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy=signal.strategy,
            created_at=created_at,
        )

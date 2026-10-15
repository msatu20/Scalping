"""Simulated USDⓈ-M broker for backtests (T13). One-way mode, one position per symbol.

Two price sources:

- ``PriceSource.TRADES`` (precise): every aggTrade is a point of the price path.
- ``PriceSource.KLINES`` (fallback, pessimistic): closed 1m candles only; the
  intra-candle path is unknown, so ambiguity is always resolved against us.

Fill rules (both sources):

- Entry TAKER (MARKET): next price after submission ± slippage (trades: next trade;
  klines: next open). Taker fee.
- Entry MAKER (LIMIT GTX): rejected if it would cross at submission (post-only); fills at
  the limit only when price trades *through* it (``maker_fill_on_touch`` accepts touches);
  cancelled at ``expires_at``. Maker fee.
- Stop loss (STOP_MARKET): first price at/through the stop; fills at *that* price ∓
  slippage, so gaps fill worse than the stop. Taker fee.
- Take profit: ``MAKER_LIMIT`` behaves like a resting maker limit at TP;
  ``TAKER_MARKET`` triggers at/through TP and fills at that price ∓ slippage.

Klines extras: stop and target in the same candle → stop; after an entry inside a
candle only the stop is checked in that candle; gaps at the open fill at the open.

Funding: at each settlement while a position is open, ``-side * qty * mark * rate``
(mark from history, else last price). Orders/events strictly after submission only.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from scalping.backtest.funding import FundingSchedule
from scalping.config.settings import Settings
from scalping.core.broker import Broker
from scalping.core.models import (
    AggregatedTrade,
    ExecutionStyle,
    Kline,
    KlineInterval,
    MarketEvent,
    OrderIntent,
    Side,
    StrategyType,
)

_BPS = Decimal(10_000)


class PriceSource(StrEnum):
    TRADES = "trades"
    KLINES = "klines"


class TpStyle(StrEnum):
    MAKER_LIMIT = "maker_limit"
    TAKER_MARKET = "taker_market"


class Liquidity(StrEnum):
    MAKER = "MAKER"
    TAKER = "TAKER"


class ExitReason(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    END_OF_DATA = "END_OF_DATA"


@dataclass(frozen=True, slots=True)
class CostModel:
    maker_fee: Decimal = Decimal("0.0002")
    taker_fee: Decimal = Decimal("0.0005")
    taker_slippage_bps: Decimal = Decimal("1")
    maker_fill_on_touch: bool = False
    tp_style: TpStyle = TpStyle.MAKER_LIMIT

    @classmethod
    def from_settings(cls, settings: Settings, **overrides: object) -> CostModel:
        return cls(maker_fee=settings.maker_fee, taker_fee=settings.taker_fee, **overrides)  # type: ignore[arg-type]

    def fee(self, liquidity: Liquidity) -> Decimal:
        return self.maker_fee if liquidity is Liquidity.MAKER else self.taker_fee

    def slip(self, price: Decimal, side: Side) -> Decimal:
        """Taker fill price: worse than ``price`` for the given order side."""
        factor = self.taker_slippage_bps / _BPS
        return price * (1 + factor) if side is Side.BUY else price * (1 - factor)


@dataclass(frozen=True, slots=True)
class Fill:
    time: int
    price: Decimal
    qty: Decimal
    liquidity: Liquidity
    fee: Decimal


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    symbol: str
    side: Side
    strategy: StrategyType
    client_order_id: str
    qty: Decimal
    entry: Fill
    exit: Fill
    exit_reason: ExitReason
    gross_pnl: Decimal
    fees: Decimal
    funding: Decimal
    net_pnl: Decimal
    planned_risk: Decimal  # qty * |entry - stop| as planned in the intent

    @property
    def r_multiple(self) -> Decimal:
        return self.net_pnl / self.planned_risk if self.planned_risk else Decimal(0)

    @property
    def hold_ms(self) -> int:
        return self.exit.time - self.entry.time


@dataclass(slots=True)
class _Pending:
    intent: OrderIntent
    submitted_at: int
    expires_at: int | None


@dataclass(slots=True)
class _Position:
    intent: OrderIntent
    entry: Fill
    funding: Decimal
    funding_checked_to: int


class SimBroker:
    """Implements ``core.broker.Broker`` (backtest and paper trading)."""

    def __init__(
        self,
        costs: CostModel | None = None,
        price_source: PriceSource = PriceSource.TRADES,
        funding: Mapping[str, FundingSchedule] | None = None,
        initial_equity: Decimal = Decimal("10000"),
        kline_interval: KlineInterval = KlineInterval.M1,
    ) -> None:
        self.costs = costs or CostModel()
        self.kline_interval = kline_interval  # price path; other intervals are ignored
        self.price_source = price_source
        self.initial_equity = initial_equity
        self._funding = dict(funding or {})
        self._pending: dict[str, _Pending] = {}
        self._positions: dict[str, _Position] = {}
        self._last_price: dict[str, Decimal] = {}
        self.trades: list[ClosedTrade] = []
        self.stats: Counter[str] = Counter()

    # ------------------------------------------------------------------ API

    @property
    def equity(self) -> Decimal:
        """Initial equity + realised net PnL (open positions not marked)."""
        return self.initial_equity + sum((t.net_pnl for t in self.trades), Decimal(0))

    def is_busy(self, symbol: str) -> bool:
        return symbol in self._pending or symbol in self._positions

    def has_position(self, symbol: str) -> bool:
        return symbol in self._positions

    def submit(self, intent: OrderIntent, now: int, expires_at: int | None = None) -> bool:
        if self.is_busy(intent.symbol):
            self.stats["rejected_busy"] += 1
            return False
        last = self._last_price.get(intent.symbol)
        if intent.execution is ExecutionStyle.MAKER and last is not None:
            crosses = (
                intent.entry_price >= last
                if intent.side is Side.BUY
                else intent.entry_price <= last
            )
            if crosses:  # GTX: a post-only order that would take liquidity is rejected
                self.stats["rejected_post_only"] += 1
                return False
        self._pending[intent.symbol] = _Pending(intent, now, expires_at)
        self.stats["submitted"] += 1
        return True

    def on_event(self, event: MarketEvent) -> None:
        if isinstance(event, AggregatedTrade):
            if self.price_source is PriceSource.TRADES:
                self._on_price(event.symbol, event.trade_time, event.price)
        elif (
            isinstance(event, Kline)
            and self.price_source is PriceSource.KLINES
            and event.is_closed
            and event.interval is self.kline_interval
        ):
            self._on_candle(event)

    def close_all(self, now: int) -> None:
        """End of data: cancel pending orders, close positions at the last price (taker)."""
        for symbol in list(self._pending):
            del self._pending[symbol]
            self.stats["cancelled_end_of_data"] += 1
        for symbol, pos in list(self._positions.items()):
            self._apply_funding(symbol, pos, now)
            price = self.costs.slip(self._last_price[symbol], pos.intent.side.opposite)
            self._close(symbol, now, price, Liquidity.TAKER, ExitReason.END_OF_DATA)

    # ------------------------------------------------------------------ trades path

    def _on_price(self, symbol: str, time: int, price: Decimal) -> None:
        self._last_price[symbol] = price
        pos = self._positions.get(symbol)
        if pos is not None:
            self._apply_funding(symbol, pos, time)
            self._check_exit_at_price(symbol, pos, time, price)
            return
        pending = self._pending.get(symbol)
        if pending is None or time < pending.submitted_at:
            return
        if pending.expires_at is not None and time >= pending.expires_at:
            self._expire(symbol)
            return
        intent = pending.intent
        if intent.execution is ExecutionStyle.TAKER:
            self._open(symbol, time, self.costs.slip(price, intent.side), Liquidity.TAKER)
        elif self._limit_fills(intent.side, intent.entry_price, price):
            self._open(symbol, time, intent.entry_price, Liquidity.MAKER)

    def _check_exit_at_price(self, symbol: str, pos: _Position, time: int, price: Decimal) -> None:
        side, sl, tp = pos.intent.side, pos.intent.stop_loss, pos.intent.take_profit
        exit_side = side.opposite
        if (side is Side.BUY and price <= sl) or (side is Side.SELL and price >= sl):
            self._close(symbol, time, self.costs.slip(price, exit_side), Liquidity.TAKER,
                        ExitReason.STOP_LOSS)  # fmt: skip
        elif self.costs.tp_style is TpStyle.MAKER_LIMIT:
            if self._limit_fills(exit_side, tp, price):
                self._close(symbol, time, tp, Liquidity.MAKER, ExitReason.TAKE_PROFIT)
        elif (side is Side.BUY and price >= tp) or (side is Side.SELL and price <= tp):
            self._close(symbol, time, self.costs.slip(price, exit_side), Liquidity.TAKER,
                        ExitReason.TAKE_PROFIT)  # fmt: skip

    def _limit_fills(self, order_side: Side, limit: Decimal, price: Decimal) -> bool:
        """Resting limit fill: price must trade through it (or touch, if allowed)."""
        if self.costs.maker_fill_on_touch:
            return price <= limit if order_side is Side.BUY else price >= limit
        return price < limit if order_side is Side.BUY else price > limit

    # ------------------------------------------------------------------ klines path

    def _on_candle(self, k: Kline) -> None:
        symbol = k.symbol
        self._last_price[symbol] = k.close
        pos = self._positions.get(symbol)
        if pos is not None:
            self._apply_funding(symbol, pos, k.close_time)
            self._check_exit_in_candle(symbol, pos, k, entered_in_candle=False)
            return
        pending = self._pending.get(symbol)
        if pending is None or k.open_time < pending.submitted_at:
            return
        if pending.expires_at is not None and k.open_time >= pending.expires_at:
            self._expire(symbol)
            return
        intent = pending.intent
        if intent.execution is ExecutionStyle.TAKER:
            self._open(symbol, k.open_time, self.costs.slip(k.open, intent.side), Liquidity.TAKER)
        else:
            through = k.low if intent.side is Side.BUY else k.high
            if not self._limit_fills(intent.side, intent.entry_price, through):
                return
            self._open(symbol, k.open_time, intent.entry_price, Liquidity.MAKER)
        new_pos = self._positions[symbol]
        self._apply_funding(symbol, new_pos, k.close_time)
        self._check_exit_in_candle(symbol, new_pos, k, entered_in_candle=True)

    def _check_exit_in_candle(
        self, symbol: str, pos: _Position, k: Kline, *, entered_in_candle: bool
    ) -> None:
        side, sl, tp = pos.intent.side, pos.intent.stop_loss, pos.intent.take_profit
        exit_side = side.opposite
        long = side is Side.BUY
        if not entered_in_candle and ((long and k.open <= sl) or (not long and k.open >= sl)):
            self._close(symbol, k.open_time, self.costs.slip(k.open, exit_side), Liquidity.TAKER,
                        ExitReason.STOP_LOSS)  # fmt: skip
            return
        if (long and k.low <= sl) or (not long and k.high >= sl):  # stop wins any ambiguity
            self._close(symbol, k.close_time, self.costs.slip(sl, exit_side), Liquidity.TAKER,
                        ExitReason.STOP_LOSS)  # fmt: skip
            return
        if entered_in_candle:
            return  # unknown order of events after the entry: no target in this candle
        if self.costs.tp_style is TpStyle.MAKER_LIMIT:
            if self._limit_fills(exit_side, tp, k.high if long else k.low):
                self._close(symbol, k.close_time, tp, Liquidity.MAKER, ExitReason.TAKE_PROFIT)
        elif (long and k.high >= tp) or (not long and k.low <= tp):
            self._close(symbol, k.close_time, self.costs.slip(tp, exit_side), Liquidity.TAKER,
                        ExitReason.TAKE_PROFIT)  # fmt: skip

    # ------------------------------------------------------------------ bookkeeping

    def _open(self, symbol: str, time: int, price: Decimal, liquidity: Liquidity) -> None:
        pending = self._pending.pop(symbol)
        qty = pending.intent.quantity
        fill = Fill(time, price, qty, liquidity, price * qty * self.costs.fee(liquidity))
        self._positions[symbol] = _Position(pending.intent, fill, Decimal(0), time)
        self.stats[f"entry_{liquidity.value.lower()}"] += 1

    def _close(
        self, symbol: str, time: int, price: Decimal, liquidity: Liquidity, reason: ExitReason
    ) -> None:
        pos = self._positions.pop(symbol)
        intent, entry = pos.intent, pos.entry
        qty = entry.qty
        exit_fill = Fill(time, price, qty, liquidity, price * qty * self.costs.fee(liquidity))
        direction = 1 if intent.side is Side.BUY else -1
        gross = (exit_fill.price - entry.price) * qty * direction
        fees = entry.fee + exit_fill.fee
        self.trades.append(ClosedTrade(
            symbol=symbol, side=intent.side, strategy=intent.strategy,
            client_order_id=intent.client_order_id, qty=qty, entry=entry, exit=exit_fill,
            exit_reason=reason, gross_pnl=gross, fees=fees, funding=pos.funding,
            net_pnl=gross - fees + pos.funding, planned_risk=intent.risk_amount,
        ))  # fmt: skip
        self.stats[f"exit_{reason.value.lower()}"] += 1

    def _expire(self, symbol: str) -> None:
        del self._pending[symbol]
        self.stats["expired"] += 1

    def _apply_funding(self, symbol: str, pos: _Position, up_to: int) -> None:
        schedule = self._funding.get(symbol)
        if schedule is None or up_to <= pos.funding_checked_to:
            return
        direction = 1 if pos.intent.side is Side.BUY else -1
        for event in schedule.between(pos.funding_checked_to, up_to):
            mark = event.mark_price or self._last_price.get(symbol, pos.entry.price)
            pos.funding -= direction * pos.entry.qty * mark * event.rate
            self.stats["funding_settlements"] += 1
        pos.funding_checked_to = up_to


def _conforms_to_broker(broker: SimBroker) -> Broker:
    """Static check (mypy): SimBroker satisfies the core Broker protocol."""
    return broker

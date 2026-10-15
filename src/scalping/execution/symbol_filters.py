"""Exchange symbol filters (T15): round prices/quantities and validate orders.

Source: ``GET /fapi/v1/exchangeInfo`` (weight 1). Rounding is always towards the safe side:

| Field | BUY | SELL | Why |
|---|---|---|---|
| maker entry (limit) | down | up | never more aggressive than intended (post-only) |
| taker entry (reference only) | nearest | nearest | the fill price is the market's |
| stop loss | up | down | risk never larger than planned |
| take profit | down | up | target never further than planned |
| quantity | down | down | never more size than planned (``MARKET_LOT_SIZE`` for takers) |
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, Decimal
from typing import Any

import aiohttp

from scalping.core.models import ExecutionStyle, OrderIntent, Side
from scalping.execution.rate_limit import RateLimiter, guarded_get_json

EXCHANGE_INFO_PATH = "/fapi/v1/exchangeInfo"


class FilterViolation(ValueError):
    """The order cannot satisfy the exchange filters (too small, too large, degenerate)."""


@dataclass(frozen=True, slots=True)
class SymbolFilters:
    symbol: str
    tick_size: Decimal
    min_price: Decimal
    max_price: Decimal
    step_size: Decimal
    min_qty: Decimal
    max_qty: Decimal
    market_step_size: Decimal
    market_min_qty: Decimal
    market_max_qty: Decimal
    min_notional: Decimal

    def round_price(self, price: Decimal, rounding: str) -> Decimal:
        return _to_multiple(price, self.tick_size, rounding)

    def round_qty(self, qty: Decimal, *, market: bool) -> Decimal:
        step = self.market_step_size if market else self.step_size
        return _to_multiple(qty, step, ROUND_FLOOR)

    def check(self, qty: Decimal, price: Decimal, *, market: bool) -> None:
        """Raise ``FilterViolation`` if an already-rounded order breaks a filter."""
        lo, hi = (
            (self.market_min_qty, self.market_max_qty) if market else (self.min_qty, self.max_qty)
        )
        if not lo <= qty <= hi:
            raise FilterViolation(f"{self.symbol}: qty {qty} outside [{lo}, {hi}]")
        if not self.min_price <= price <= self.max_price:
            raise FilterViolation(
                f"{self.symbol}: price {price} outside [{self.min_price}, {self.max_price}]"
            )
        if qty * price < self.min_notional:
            raise FilterViolation(
                f"{self.symbol}: notional {qty * price} < min {self.min_notional}"
            )


def _to_multiple(value: Decimal, step: Decimal, rounding: str) -> Decimal:
    units = (value / step).to_integral_value(rounding=rounding)
    return (units * step).quantize(step)


def parse_exchange_info(data: Mapping[str, Any]) -> dict[str, SymbolFilters]:
    """Map symbol -> filters for every symbol in an ``exchangeInfo`` payload."""
    out: dict[str, SymbolFilters] = {}
    for sym in data["symbols"]:
        f = {flt["filterType"]: flt for flt in sym["filters"]}
        price, lot = f["PRICE_FILTER"], f["LOT_SIZE"]
        market = f.get("MARKET_LOT_SIZE", lot)
        out[sym["symbol"]] = SymbolFilters(
            symbol=sym["symbol"],
            tick_size=Decimal(price["tickSize"]),
            min_price=Decimal(price["minPrice"]),
            max_price=Decimal(price["maxPrice"]),
            step_size=Decimal(lot["stepSize"]),
            min_qty=Decimal(lot["minQty"]),
            max_qty=Decimal(lot["maxQty"]),
            market_step_size=Decimal(market["stepSize"]),
            market_min_qty=Decimal(market["minQty"]),
            market_max_qty=Decimal(market["maxQty"]),
            min_notional=Decimal(f.get("MIN_NOTIONAL", {}).get("notional", "0")),
        )
    return out


async def fetch_symbol_filters(
    session: aiohttp.ClientSession, rest_base_url: str, limiter: RateLimiter | None = None
) -> dict[str, SymbolFilters]:
    url = f"{rest_base_url.rstrip('/')}{EXCHANGE_INFO_PATH}"
    if limiter is not None:
        return parse_exchange_info(await guarded_get_json(session, limiter, url, weight=1))
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        resp.raise_for_status()
        return parse_exchange_info(await resp.json())


def apply_filters(intent: OrderIntent, filters: SymbolFilters) -> OrderIntent:
    """Return ``intent`` rounded to the exchange grid; ``FilterViolation`` if impossible."""
    if intent.symbol != filters.symbol:
        raise ValueError(f"filters for {filters.symbol} applied to {intent.symbol}")
    buy = intent.side is Side.BUY
    market = intent.execution is ExecutionStyle.TAKER
    if market:
        entry = filters.round_price(intent.entry_price, ROUND_HALF_EVEN)
    else:
        entry = filters.round_price(intent.entry_price, ROUND_FLOOR if buy else ROUND_CEILING)
    stop = filters.round_price(intent.stop_loss, ROUND_CEILING if buy else ROUND_FLOOR)
    target = filters.round_price(intent.take_profit, ROUND_FLOOR if buy else ROUND_CEILING)
    qty = filters.round_qty(intent.quantity, market=market)
    if qty <= 0:
        raise FilterViolation(f"{intent.symbol}: qty {intent.quantity} rounds to zero")
    filters.check(qty, entry, market=market)
    try:
        return dataclasses.replace(
            intent, entry_price=entry, stop_loss=stop, take_profit=target, quantity=qty
        )
    except ValueError as exc:  # e.g. stop rounded onto the entry price
        raise FilterViolation(f"{intent.symbol}: levels collapse after rounding: {exc}") from exc

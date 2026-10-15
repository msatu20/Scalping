"""Broker contract shared by backtest, paper and (future) live execution (T17).

The strategy runner only talks to this interface, so the same wiring runs against
``SimBroker`` fed by ``ReplayFeed`` (backtest), ``SimBroker`` fed by the live
``MarketDataFeed`` (paper trading: real-time prices, simulated fills) and, later, a real
exchange broker (live trading — requires explicit user approval, ADR-0002).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from scalping.core.models import MarketEvent, OrderIntent


@runtime_checkable
class Broker(Protocol):
    def submit(self, intent: OrderIntent, now: int, expires_at: int | None = None) -> bool:
        """Place an entry order with attached SL/TP. False if rejected (busy, post-only...)."""
        ...

    def on_event(self, event: MarketEvent) -> None:
        """Update orders/positions with market data (fills, stops, targets, funding)."""
        ...

    def is_busy(self, symbol: str) -> bool:
        """True if the symbol has a pending order or an open position."""
        ...

    def has_position(self, symbol: str) -> bool: ...

    def close_all(self, now: int) -> None:
        """Cancel pending orders and close every position at market."""
        ...

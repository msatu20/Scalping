"""Common interface of event sources: live ``MarketDataFeed`` and backtest ``ReplayFeed``.

Consumers (strategy runners) depend on this contract only, so the same code runs live
and in backtests: events arrive through ``on_event`` in time order, and the injected
``Clock`` reads the time at which the current event is being processed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from scalping.core.models import MarketEvent

type EventHandler = Callable[[MarketEvent], None]


@runtime_checkable
class MarketFeed(Protocol):
    async def run(self) -> None: ...

    async def stop(self) -> None: ...

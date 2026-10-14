"""Signal generator contract shared by every strategy.

A generator consumes the same ``MarketEvent`` stream in live (``MarketDataFeed``) and
backtest (``ReplayFeed``) and reads time only from the injected ``Clock``: never from
the wall clock, never from "future" data.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from scalping.core.models import MarketEvent, Signal

type SignalHandler = Callable[[Signal], None]


@runtime_checkable
class SignalGenerator(Protocol):
    def on_event(self, event: MarketEvent) -> Signal | None:
        """Process one event; return the signal it triggered, if any."""
        ...

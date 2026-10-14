"""Backtest replay (T12): Parquet history -> core events, same contract as the live feed.

Emission order is deterministic: by event time; at equal ms, aggTrades before klines
(trades at a candle's last ms belong to that candle), then by symbol order, then by row.

Klines are emitted once, closed (``is_closed=True``), at ``close_time`` — history has no
intra-candle updates. aggTrades are emitted at ``transact_time``. ``recv_time`` adds an
optional simulated latency.

Clock integrity: the injected ``FixedClock`` is advanced to the event's ``recv_time``
right before the handler sees it — at consumption, never at production — so with the
async queue the producer running ahead can never leak future time into the strategy.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from scalping.backtest.store import DataKind, HistoricalStore, MissingDataError, day_range
from scalping.core.clock import FixedClock
from scalping.core.feed import EventHandler
from scalping.core.models import AggregatedTrade, Kline, KlineInterval
from scalping.market_data.feed import FeedStats

# History has no depth data: only klines and aggTrades are replayed.
type ReplayEvent = Kline | AggregatedTrade

_TRADE_PRIORITY = 0
_KLINE_PRIORITY = 1

_KLINE_COLUMNS = (
    "open_time", "close_time", "open", "high", "low", "close",
    "volume", "quote_volume", "count", "taker_buy_volume",
)  # fmt: skip
_AGG_TRADE_COLUMNS = (
    "agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id",
    "transact_time", "is_buyer_maker",
)  # fmt: skip


def day_start_ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp()) * 1000


def _dec(value: float) -> Decimal:
    # Parquet floats were parsed round-trip (ADR-0006): repr() restores the original digits.
    return Decimal(repr(value))


class ReplayFeed:
    def __init__(
        self,
        store: HistoricalStore,
        symbols: Sequence[str],
        start: date,
        end: date,
        *,
        intervals: Sequence[KlineInterval] = (KlineInterval.M1,),
        agg_trades: bool = True,
        on_event: EventHandler | None = None,
        clock: FixedClock | None = None,
        latency_ms: int = 0,
        queue_maxsize: int = 10_000,
    ) -> None:
        if not symbols:
            raise ValueError("at least one symbol is required")
        if not intervals and not agg_trades:
            raise ValueError("nothing to replay: no kline intervals and agg_trades=False")
        if latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        self._store = store
        self._symbols = list(symbols)
        self._days = day_range(start, end)
        self._intervals = list(intervals)
        self._agg_trades = agg_trades
        self._on_event = on_event
        self._latency_ms = latency_ms
        self._queue_maxsize = queue_maxsize
        self._stop_requested = False
        self.clock = clock or FixedClock(day_start_ms(start))
        self.stats = FeedStats()

    # ------------------------------------------------------------------ public API

    def check_data(self) -> None:
        """Fail fast, before emitting anything, if any required day is missing."""
        for symbol in self._symbols:
            for kind, interval in self._sources():
                missing = [
                    day for day in self._days if not self._store.has(kind, symbol, day, interval)
                ]
                if missing:
                    raise MissingDataError(kind, symbol, missing)

    def events(self) -> Iterator[ReplayEvent]:
        """Pure, ordered event stream (does not touch the clock or stats)."""
        self.check_data()
        for day in self._days:
            yield from self._day_events(day)

    def replay(self, on_event: EventHandler | None = None) -> int:
        """Fast synchronous backtest path. Returns the number of events dispatched."""
        handler = on_event or self._on_event
        count = 0
        for event in self.events():
            if self._stop_requested:
                break
            self._dispatch(event, handler, queue_size=0)
            count += 1
        return count

    async def run(self) -> None:
        """Live-like path: producer -> bounded ``asyncio.Queue`` -> consumer -> ``on_event``."""
        queue: asyncio.Queue[ReplayEvent | None] = asyncio.Queue(maxsize=self._queue_maxsize)

        async def produce() -> None:
            # No try/finally: if the consumer fails, TaskGroup cancels us and a blocking
            # sentinel put on a full queue would hang.
            for event in self.events():
                if self._stop_requested:
                    break
                await queue.put(event)
            await queue.put(None)

        async def consume() -> None:
            while (event := await queue.get()) is not None:
                if not self._stop_requested:
                    self._dispatch(event, self._on_event, queue.qsize())

        self.check_data()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(produce(), name="replay-producer")
            tg.create_task(consume(), name="replay-consumer")

    def request_stop(self) -> None:
        """Stop after the current event (safe to call from inside ``on_event``)."""
        self._stop_requested = True

    async def stop(self) -> None:
        self.request_stop()

    # ------------------------------------------------------------------ internals

    def _sources(self) -> list[tuple[DataKind, KlineInterval]]:
        sources = [(DataKind.KLINES, interval) for interval in self._intervals]
        if self._agg_trades:
            sources.append((DataKind.AGG_TRADES, KlineInterval.M1))  # interval unused
        return sources

    def _dispatch(self, event: ReplayEvent, handler: EventHandler | None, queue_size: int) -> None:
        self.clock.advance_to(event.recv_time)
        self.stats.record(event, None, queue_size)
        if handler is not None:
            handler(event)

    def _day_events(self, day: date) -> Iterator[ReplayEvent]:
        times: list[np.ndarray] = []
        priorities: list[np.ndarray] = []
        source_ids: list[np.ndarray] = []
        builders: list[Callable[[int], ReplayEvent]] = []

        for symbol in self._symbols:
            for kind, interval in self._sources():
                frame = self._store.load(kind, symbol, day, day, interval)
                if kind is DataKind.KLINES:
                    t = frame["close_time"].to_numpy(dtype=np.int64)
                    builder = self._kline_builder(symbol, interval, frame)
                    priority = _KLINE_PRIORITY
                else:
                    t = frame["transact_time"].to_numpy(dtype=np.int64)
                    builder = self._agg_trade_builder(symbol, frame)
                    priority = _TRADE_PRIORITY
                times.append(t)
                priorities.append(np.full(len(t), priority, dtype=np.int8))
                source_ids.append(np.full(len(t), len(builders), dtype=np.int32))
                builders.append(builder)

        all_times = np.concatenate(times)
        all_sources = np.concatenate(source_ids)
        rows = np.concatenate([np.arange(len(t), dtype=np.int64) for t in times])
        # lexsort: last key is primary -> time, then priority, then source, then row.
        order = np.lexsort((rows, all_sources, np.concatenate(priorities), all_times))
        for source, row in zip(all_sources[order].tolist(), rows[order].tolist(), strict=True):
            yield builders[source](row)

    def _kline_builder(
        self, symbol: str, interval: KlineInterval, frame: pd.DataFrame
    ) -> Callable[[int], ReplayEvent]:
        cols = {name: frame[name].tolist() for name in _KLINE_COLUMNS}
        latency = self._latency_ms

        def build(i: int) -> ReplayEvent:
            close_time = cols["close_time"][i]
            return Kline(
                symbol=symbol,
                interval=interval,
                open_time=cols["open_time"][i],
                close_time=close_time,
                open=_dec(cols["open"][i]),
                high=_dec(cols["high"][i]),
                low=_dec(cols["low"][i]),
                close=_dec(cols["close"][i]),
                volume=_dec(cols["volume"][i]),
                quote_volume=_dec(cols["quote_volume"][i]),
                trades=cols["count"][i],
                taker_buy_volume=_dec(cols["taker_buy_volume"][i]),
                is_closed=True,
                event_time=close_time,
                recv_time=close_time + latency,
            )

        return build

    def _agg_trade_builder(self, symbol: str, frame: pd.DataFrame) -> Callable[[int], ReplayEvent]:
        cols = {name: frame[name].tolist() for name in _AGG_TRADE_COLUMNS}
        latency = self._latency_ms

        def build(i: int) -> ReplayEvent:
            trade_time = cols["transact_time"][i]
            return AggregatedTrade(
                symbol=symbol,
                agg_trade_id=cols["agg_trade_id"][i],
                price=_dec(cols["price"][i]),
                qty=_dec(cols["quantity"][i]),
                first_trade_id=cols["first_trade_id"][i],
                last_trade_id=cols["last_trade_id"][i],
                trade_time=trade_time,
                is_buyer_maker=cols["is_buyer_maker"][i],
                event_time=trade_time,
                recv_time=trade_time + latency,
            )

        return build

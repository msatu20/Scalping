"""Local order book for Binance USDⓈ-M Futures diff-depth streams (T6).

``LocalOrderBook`` is a pure state machine (no I/O):

    UNSYNCED --apply_snapshot--> AWAITING_BRIDGE --first overlapping delta--> SYNCED
        ^                                                                       |
        +------------------- gap (pu mismatch) / crossed book -----------------+

Binance procedure: buffer deltas, fetch REST snapshot, drop deltas with ``u`` older
than ``lastUpdateId``, the first applied delta must satisfy ``U <= lastUpdateId + 1``
and ``u >= lastUpdateId``; afterwards every delta's ``pu`` must equal the previous ``u``.

``OrderBookManager`` adds the I/O: snapshot fetching with backoff, resync on gaps and
on every WS (re)connection, and latency gating (K13). A book whose stream lags more
than ``max_latency_ms`` is not tradeable; resyncing would not cure a slow consumer.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import random
from collections import deque
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from scalping.core.models import (
    MarketEvent,
    OrderBookDelta,
    OrderBookImbalance,
    OrderBookSnapshot,
    PriceLevel,
)

log = logging.getLogger(__name__)

type SnapshotFetcher = Callable[[str], Awaitable[OrderBookSnapshot]]


class SyncState(StrEnum):
    UNSYNCED = "UNSYNCED"  # buffering deltas, waiting for a snapshot
    AWAITING_BRIDGE = "AWAITING_BRIDGE"  # snapshot loaded, waiting for an overlapping delta
    SYNCED = "SYNCED"


class DeltaResult(StrEnum):
    BUFFERED = "BUFFERED"
    APPLIED = "APPLIED"
    STALE = "STALE"  # older than the book; ignored
    GAP = "GAP"  # continuity lost; book reset, resync required


class BookNotSyncedError(RuntimeError):
    """Raised when reading a book that is not SYNCED (never trade on a partial book)."""


class LocalOrderBook:
    def __init__(
        self, symbol: str, max_buffer: int = 5_000, max_levels_per_side: int = 5_000
    ) -> None:
        self.symbol = symbol
        self._max_buffer = max_buffer
        self._max_levels = max_levels_per_side
        self._bids: dict[Decimal, Decimal] = {}
        self._asks: dict[Decimal, Decimal] = {}
        self._buffer: deque[OrderBookDelta] = deque()
        self.state = SyncState.UNSYNCED
        self.last_update_id: int | None = None
        self.last_event_time: int | None = None
        self.last_latency_ms: int | None = None
        self.gaps = 0

    # ------------------------------------------------------------------ updates

    def reset(self) -> None:
        self._bids.clear()
        self._asks.clear()
        self._buffer.clear()
        self.state = SyncState.UNSYNCED
        self.last_update_id = None

    def apply_delta(self, delta: OrderBookDelta) -> DeltaResult:
        if delta.symbol != self.symbol:
            raise ValueError(f"delta for {delta.symbol} sent to {self.symbol} book")
        self.last_latency_ms = delta.recv_time - delta.event_time
        if self.state is SyncState.UNSYNCED:
            if len(self._buffer) >= self._max_buffer:
                # The snapshot will be newer than the dropped events; if not, it is refetched.
                self._buffer.popleft()
            self._buffer.append(delta)
            return DeltaResult.BUFFERED
        return self._apply_live(delta)

    def apply_snapshot(self, snapshot: OrderBookSnapshot) -> bool:
        """Load ``snapshot`` and replay buffered deltas.

        Returns False if the snapshot cannot be bridged to the buffered stream (it is
        older than the first buffered delta, or a gap appears during replay); the book
        stays UNSYNCED with its buffer and a newer snapshot must be fetched.
        """
        if snapshot.symbol != self.symbol:
            raise ValueError(f"snapshot for {snapshot.symbol} sent to {self.symbol} book")
        lid = snapshot.last_update_id
        pending = [d for d in self._buffer if d.final_update_id >= lid]
        if pending and pending[0].first_update_id > lid + 1:
            return False

        self.reset()
        self._bids.update((lvl.price, lvl.qty) for lvl in snapshot.bids if lvl.qty)
        self._asks.update((lvl.price, lvl.qty) for lvl in snapshot.asks if lvl.qty)
        self.last_update_id = lid
        self.last_event_time = snapshot.timestamp
        self.state = SyncState.AWAITING_BRIDGE
        for i, delta in enumerate(pending):
            if self._apply_live(delta) is DeltaResult.GAP:
                self._buffer.extend(pending[i + 1 :])
                return False
        return True

    def _apply_live(self, delta: OrderBookDelta) -> DeltaResult:
        lid = self.last_update_id
        assert lid is not None
        if delta.final_update_id < lid or (
            self.state is SyncState.SYNCED and delta.final_update_id == lid
        ):
            return DeltaResult.STALE
        if self.state is SyncState.AWAITING_BRIDGE:
            if delta.first_update_id > lid + 1:
                return self._gap(delta, "no delta overlaps the snapshot")
        elif not delta.is_continuation_of(lid):
            return self._gap(delta, f"sequence gap (expected pu={lid})")

        _apply_levels(self._bids, delta.bids)
        _apply_levels(self._asks, delta.asks)
        self.last_update_id = delta.final_update_id
        self.last_event_time = delta.event_time
        self.state = SyncState.SYNCED
        if self._bids and self._asks and max(self._bids) >= min(self._asks):
            return self._gap(delta, "crossed book")
        self._prune()
        return DeltaResult.APPLIED

    def _gap(self, delta: OrderBookDelta, reason: str) -> DeltaResult:
        log.warning(
            "%s book reset: %s (U=%d u=%d)",
            self.symbol,
            reason,
            delta.first_update_id,
            delta.final_update_id,
        )
        self.reset()
        self.gaps += 1
        self._buffer.append(delta)
        return DeltaResult.GAP

    def _prune(self) -> None:
        """Bound memory: drop levels farthest from the touch (amortised, keeps 80 %)."""
        keep = self._max_levels * 4 // 5
        if len(self._bids) > self._max_levels:
            self._bids = {p: self._bids[p] for p in heapq.nlargest(keep, self._bids)}
        if len(self._asks) > self._max_levels:
            self._asks = {p: self._asks[p] for p in heapq.nsmallest(keep, self._asks)}

    # ------------------------------------------------------------------ reads

    @property
    def is_synced(self) -> bool:
        return self.state is SyncState.SYNCED

    @property
    def buffered(self) -> int:
        return len(self._buffer)

    def best_bid(self) -> PriceLevel | None:
        self._require_synced()
        if not self._bids:
            return None
        price = max(self._bids)
        return PriceLevel(price, self._bids[price])

    def best_ask(self) -> PriceLevel | None:
        self._require_synced()
        if not self._asks:
            return None
        price = min(self._asks)
        return PriceLevel(price, self._asks[price])

    def snapshot(self, levels: int | None = None) -> OrderBookSnapshot:
        """Immutable view of the top ``levels`` per side (all levels if None)."""
        self._require_synced()
        assert self.last_update_id is not None and self.last_event_time is not None
        if levels is None:
            bid_prices = sorted(self._bids, reverse=True)
            ask_prices = sorted(self._asks)
        else:
            bid_prices = heapq.nlargest(levels, self._bids)
            ask_prices = heapq.nsmallest(levels, self._asks)
        return OrderBookSnapshot(
            symbol=self.symbol,
            last_update_id=self.last_update_id,
            bids=tuple(PriceLevel(p, self._bids[p]) for p in bid_prices),
            asks=tuple(PriceLevel(p, self._asks[p]) for p in ask_prices),
            timestamp=self.last_event_time,
        )

    def imbalance(self, levels: int) -> OrderBookImbalance:
        self._require_synced()
        assert self.last_event_time is not None
        return OrderBookImbalance(
            symbol=self.symbol,
            timestamp=self.last_event_time,
            levels=levels,
            bid_qty=sum((self._bids[p] for p in heapq.nlargest(levels, self._bids)), Decimal(0)),
            ask_qty=sum((self._asks[p] for p in heapq.nsmallest(levels, self._asks)), Decimal(0)),
        )

    def _require_synced(self) -> None:
        if self.state is not SyncState.SYNCED:
            raise BookNotSyncedError(f"{self.symbol} book is {self.state}")


def _apply_levels(side: dict[Decimal, Decimal], levels: tuple[PriceLevel, ...]) -> None:
    for lvl in levels:
        if lvl.qty:
            side[lvl.price] = lvl.qty
        else:
            side.pop(lvl.price, None)


# --------------------------------------------------------------------------- manager


@dataclass(frozen=True, slots=True)
class ResyncPolicy:
    initial_backoff_s: float = 0.5
    max_backoff_s: float = 10.0  # snapshot limit=1000 costs weight 20; keep retries slow (K3)
    max_latency_ms: int = 500  # stream lag above this -> book not tradeable (K13, R5)

    def backoff(self, attempt: int) -> float:
        ceiling = min(self.max_backoff_s, self.initial_backoff_s * 2**attempt)
        return random.uniform(ceiling / 2, ceiling)


class OrderBookManager:
    """Keeps one ``LocalOrderBook`` per symbol in sync.

    Wiring: pass ``on_connected`` to ``BinanceFuturesWsClient`` and call ``handle``
    for every event taken from its queue.
    """

    def __init__(
        self,
        symbols: Iterable[str],
        fetch_snapshot: SnapshotFetcher,
        policy: ResyncPolicy | None = None,
    ) -> None:
        self.books = {symbol: LocalOrderBook(symbol) for symbol in symbols}
        self._fetch = fetch_snapshot
        self._policy = policy or ResyncPolicy()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self.snapshot_requests = 0

    async def on_connected(self) -> None:
        """New WS session: deltas from the old one are unrelated, rebuild every book."""
        for symbol, book in self.books.items():
            book.reset()
            self._schedule_resync(symbol, restart=True)

    def handle(self, event: MarketEvent) -> DeltaResult | None:
        if not isinstance(event, OrderBookDelta):
            return None
        book = self.books.get(event.symbol)
        if book is None:
            return None
        result = book.apply_delta(event)
        if book.state is SyncState.UNSYNCED:
            self._schedule_resync(event.symbol)
        return result

    def is_tradeable(self, symbol: str) -> bool:
        book = self.books[symbol]
        latency = book.last_latency_ms
        return book.is_synced and latency is not None and latency <= self._policy.max_latency_ms

    async def close(self) -> None:
        tasks = [t for t in self._tasks.values() if not t.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _schedule_resync(self, symbol: str, *, restart: bool = False) -> None:
        task = self._tasks.get(symbol)
        if task is not None and not task.done():
            if not restart:
                return
            task.cancel()
        self._tasks[symbol] = asyncio.create_task(self._resync(symbol), name=f"resync-{symbol}")

    async def _resync(self, symbol: str) -> None:
        book = self.books[symbol]
        attempt = 0
        while book.state is SyncState.UNSYNCED:
            self.snapshot_requests += 1
            try:
                snapshot = await self._fetch(symbol)
            except Exception as exc:  # network / HTTP / parse: retry with backoff
                log.warning("%s snapshot fetch failed: %r", symbol, exc)
            else:
                if book.apply_snapshot(snapshot):
                    log.info("%s book resynced at lastUpdateId=%d", symbol, book.last_update_id)
                    return
                log.info("%s snapshot not bridgeable, refetching", symbol)
            await asyncio.sleep(self._policy.backoff(attempt))
            attempt += 1

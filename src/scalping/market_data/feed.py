"""Market data runner (T10): settings -> routed WS clients -> queue -> order books.

    /public WS (depth) ──┐                       ┌─► OrderBookManager.handle (deltas)
                         ├─► asyncio.Queue ──────┤
    /market WS (trades,  ┘                       └─► on_event callback (klines, trades)
               klines)

Only the /public client resyncs the books on (re)connection. The local clock is
aligned with Binance server time at start-up so latency gating (K13) is meaningful.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import aiohttp

from scalping.config.settings import Settings
from scalping.core.clock import Clock, SystemClock
from scalping.core.models import KlineInterval, MarketEvent, OrderBookDelta
from scalping.market_data.order_book import DeltaResult, OrderBookManager, ResyncPolicy
from scalping.market_data.rest_snapshot import make_snapshot_fetcher
from scalping.market_data.streams import StreamRoute, default_streams, routed_stream_urls
from scalping.market_data.ws_client import BinanceFuturesWsClient, ReconnectPolicy

log = logging.getLogger(__name__)

SERVER_TIME_PATH = "/fapi/v1/time"


async def server_clock_offset_ms(session: aiohttp.ClientSession, rest_base_url: str) -> int:
    """Binance server time minus local time, compensating half the round trip."""
    url = f"{rest_base_url.rstrip('/')}{SERVER_TIME_PATH}"
    sent = time.time_ns() // 1_000_000
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
        resp.raise_for_status()
        server_time = int((await resp.json())["serverTime"])
    received = time.time_ns() // 1_000_000
    return server_time - (sent + received) // 2


@dataclass(slots=True)
class FeedStats:
    events: Counter[str] = field(default_factory=Counter)
    delta_results: Counter[str] = field(default_factory=Counter)
    max_latency_ms: int = 0
    latency_sum_ms: int = 0
    latency_samples: int = 0
    max_queue_size: int = 0

    @property
    def avg_latency_ms(self) -> float:
        return self.latency_sum_ms / self.latency_samples if self.latency_samples else 0.0

    def record(self, event: MarketEvent, result: DeltaResult | None, queue_size: int) -> None:
        self.events[type(event).__name__] += 1
        if result is not None:
            self.delta_results[result] += 1
        if isinstance(event, OrderBookDelta):
            latency = event.recv_time - event.event_time
            self.max_latency_ms = max(self.max_latency_ms, latency)
            self.latency_sum_ms += latency
            self.latency_samples += 1
        self.max_queue_size = max(self.max_queue_size, queue_size)


class MarketDataFeed:
    def __init__(
        self,
        settings: Settings,
        intervals: Sequence[KlineInterval] = (KlineInterval.M1,),
        on_event: Callable[[MarketEvent], None] | None = None,
        clock: Clock | None = None,
        reconnect_policy: ReconnectPolicy | None = None,
        resync_policy: ResyncPolicy | None = None,
        queue_maxsize: int = 10_000,
        snapshot_limit: int = 1000,
        ws_base_url: str | None = None,
        rest_base_url: str | None = None,
        streams: Sequence[str] | None = None,
    ) -> None:
        self._settings = settings
        # Default: depth + aggTrade + klines per symbol; pass ``streams`` to narrow it.
        self._streams = list(streams) if streams else default_streams(settings.symbols, intervals)
        self._on_event = on_event
        self._clock = clock
        self._reconnect_policy = reconnect_policy
        self._resync_policy = resync_policy
        self._snapshot_limit = snapshot_limit
        self._ws_base_url = ws_base_url or settings.ws_base_url
        self._rest_base_url = rest_base_url or settings.rest_base_url
        self._queue: asyncio.Queue[MarketEvent] = asyncio.Queue(maxsize=queue_maxsize)
        self._clients: dict[StreamRoute, BinanceFuturesWsClient] = {}
        self._stopped = asyncio.Event()
        self.manager: OrderBookManager | None = None
        self.clock: Clock | None = clock  # set to the server-aligned clock once running
        self.stats = FeedStats()

    @property
    def urls(self) -> dict[StreamRoute, str]:
        return routed_stream_urls(self._ws_base_url, self._streams)

    @property
    def parse_errors(self) -> int:
        return sum(client.parse_errors for client in self._clients.values())

    @property
    def reconnects(self) -> int:
        return sum(client.reconnects for client in self._clients.values())

    async def run(self) -> None:
        """Run until ``stop()``. Network errors are retried inside the WS clients."""
        async with aiohttp.ClientSession() as session:
            clock = self._clock or await self._server_aligned_clock(session)
            self.clock = clock
            fetcher = make_snapshot_fetcher(
                session, self._rest_base_url, clock, limit=self._snapshot_limit
            )
            manager = OrderBookManager(self._settings.symbols, fetcher, self._resync_policy)
            self.manager = manager
            for route, url in self.urls.items():
                self._clients[route] = BinanceFuturesWsClient(
                    url,
                    self._queue,
                    clock,
                    self._reconnect_policy,
                    on_connected=manager.on_connected if route is StreamRoute.PUBLIC else None,
                )
            try:
                async with asyncio.TaskGroup() as tg:
                    for route, client in self._clients.items():
                        tg.create_task(client.run(), name=f"ws-{route}")
                    tg.create_task(self._consume(manager), name="feed-consumer")
                    await self._stopped.wait()
                    await asyncio.gather(*(client.stop() for client in self._clients.values()))
                    raise _Shutdown
            except* _Shutdown:
                pass
            finally:
                await manager.close()

    async def stop(self) -> None:
        self._stopped.set()

    async def _consume(self, manager: OrderBookManager) -> None:
        while True:
            event = await self._queue.get()
            result = manager.handle(event)
            self.stats.record(event, result, self._queue.qsize())
            if result is None and self._on_event is not None:
                self._on_event(event)

    async def _server_aligned_clock(self, session: aiohttp.ClientSession) -> Clock:
        try:
            offset = await server_clock_offset_ms(session, self._rest_base_url)
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as exc:
            log.warning("server time sync failed, using local clock: %r", exc)
            return SystemClock()
        log.info("clock offset vs Binance: %+d ms", offset)
        return SystemClock(offset_ms=offset)


class _Shutdown(Exception):
    """Internal: cancels the TaskGroup on stop()."""

"""Native WebSocket client for Binance USDⓈ-M Futures market streams (ADR-0004).

Responsibilities: connect, parse frames into core models, push them to a queue,
reconnect with exponential backoff + jitter, detect stale streams and reconnect
proactively before Binance's 24 h cut-off. Order book synchronisation is done
downstream; ``on_connected`` lets it resync after every (re)connection.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import WebSocketException

from scalping.core.clock import Clock
from scalping.core.models import MarketEvent
from scalping.market_data.parser import ParseError, parse_message

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    initial_backoff_s: float = 0.5
    max_backoff_s: float = 30.0
    stale_timeout_s: float = 10.0  # no frame for this long -> reconnect (R5)
    max_session_s: float = 23 * 3600  # Binance closes connections at 24 h
    open_timeout_s: float = 10.0

    def backoff(self, attempt: int) -> float:
        ceiling = min(self.max_backoff_s, self.initial_backoff_s * 2**attempt)
        return random.uniform(ceiling / 2, ceiling)


class BinanceFuturesWsClient:
    def __init__(
        self,
        url: str,
        queue: asyncio.Queue[MarketEvent],
        clock: Clock,
        policy: ReconnectPolicy | None = None,
        on_connected: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._url = url
        self._queue = queue
        self._clock = clock
        self._policy = policy or ReconnectPolicy()
        self._on_connected = on_connected
        self._stopped = asyncio.Event()
        self._ws: ClientConnection | None = None
        self.reconnects = 0
        self.parse_errors = 0

    async def run(self) -> None:
        """Run until ``stop()``; never raises on network errors."""
        attempt = 0
        while not self._stopped.is_set():
            try:
                async with connect(
                    self._url, open_timeout=self._policy.open_timeout_s, max_size=2**22
                ) as ws:
                    self._ws = ws
                    log.info("ws connected", extra={"url": self._url})
                    if self._on_connected is not None:
                        await self._on_connected()
                    if await self._consume(ws):
                        attempt = 0
            except (OSError, TimeoutError, WebSocketException) as exc:
                log.warning("ws connection error: %r", exc)
            finally:
                self._ws = None

            if self._stopped.is_set():
                break
            self.reconnects += 1
            delay = self._policy.backoff(attempt)
            attempt += 1
            log.info("ws reconnecting in %.2fs (attempt %d)", delay, attempt)
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stopped.wait(), timeout=delay)

    async def stop(self) -> None:
        self._stopped.set()
        if self._ws is not None:
            await self._ws.close()

    async def _consume(self, ws: ClientConnection) -> bool:
        """Read frames until the session ends. Returns True if any frame was received."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._policy.max_session_s
        received = False
        while not self._stopped.is_set():
            remaining = deadline - loop.time()
            if remaining <= 0:
                log.info("ws proactive reconnect (max session reached)")
                return received
            try:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=min(self._policy.stale_timeout_s, remaining)
                )
            except TimeoutError:
                if loop.time() < deadline:
                    log.warning("ws stale: no frames for %.1fs", self._policy.stale_timeout_s)
                return received
            received = True
            recv_time = self._clock.now_ms()
            try:
                event = parse_message(raw, recv_time)
            except ParseError:
                self.parse_errors += 1
                log.exception("ws parse error")
                continue
            if event is not None:
                # Backpressure instead of dropping: a lost depth delta corrupts the book.
                await self._queue.put(event)
        return received

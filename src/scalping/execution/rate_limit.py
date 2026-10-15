"""Central REST rate-limit guard (T9) shared by every Binance REST call of a process.

Binance USDⓈ-M: REQUEST_WEIGHT 2400 / minute per IP (exchangeInfo ``rateLimits``).
- Before a request: wait if ``used + weight`` would exceed ``limit * safety`` this minute.
- After a response: sync ``used`` with ``X-MBX-USED-WEIGHT-1M`` (the server is the truth).
- HTTP 429: pause *all* requests for ``Retry-After`` seconds (default 60).
- HTTP 418 (IP auto-banned for ignoring 429s): block everything until ``Retry-After`` and
  raise ``IpBannedError``; trading must pause (callers check ``is_banned``).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import aiohttp

from scalping.core.clock import Clock

log = logging.getLogger(__name__)

WEIGHT_HEADER = "X-MBX-USED-WEIGHT-1M"
DEFAULT_WEIGHT_LIMIT = 2400


class RateLimitError(RuntimeError):
    pass


class IpBannedError(RateLimitError):
    pass


def depth_weight(limit: int) -> int:
    """``GET /fapi/v1/depth`` weight by ``limit``."""
    if limit <= 50:
        return 2
    if limit <= 100:
        return 5
    if limit <= 500:
        return 10
    return 20


class RateLimiter:
    def __init__(
        self,
        clock: Clock,
        weight_limit: int = DEFAULT_WEIGHT_LIMIT,
        safety: float = 0.8,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not 0 < safety <= 1:
            raise ValueError("safety must be in (0, 1]")
        self._clock = clock
        self._budget = int(weight_limit * safety)
        self._sleep = sleep
        self._minute = -1
        self.used = 0
        self.blocked_until = 0
        self.banned_until = 0
        self._lock = asyncio.Lock()

    def is_banned(self) -> bool:
        return self._clock.now_ms() < self.banned_until

    async def acquire(self, weight: int) -> None:
        if weight > self._budget:
            raise ValueError(f"weight {weight} exceeds the per-minute budget {self._budget}")
        async with self._lock:  # serialise: concurrent callers must not overshoot together
            while True:
                now = self._clock.now_ms()
                if now < self.banned_until:
                    raise IpBannedError(f"IP banned for {(self.banned_until - now) / 1000:.0f}s")
                if now < self.blocked_until:
                    await self._sleep((self.blocked_until - now) / 1000)
                    continue
                minute = now // 60_000
                if minute != self._minute:
                    self._minute, self.used = minute, 0
                if self.used + weight <= self._budget:
                    self.used += weight
                    return
                wait_ms = (minute + 1) * 60_000 - now
                log.warning("rate limit budget reached (%d/%d), waiting %.1fs",
                            self.used, self._budget, wait_ms / 1000)  # fmt: skip
                await self._sleep(wait_ms / 1000)

    def on_response(self, status: int, headers: Mapping[str, str]) -> None:
        now = self._clock.now_ms()
        used = headers.get(WEIGHT_HEADER)
        if used is not None and now // 60_000 == self._minute:
            self.used = max(self.used, int(used))
        retry_s = int(headers.get("Retry-After", "0") or 0)
        if status == 418:
            self.banned_until = now + (retry_s or 120) * 1000
            log.error("HTTP 418: IP banned until %d", self.banned_until)
            raise IpBannedError(f"HTTP 418: IP banned for {retry_s or 120}s")
        if status == 429:
            self.blocked_until = now + (retry_s or 60) * 1000
            log.warning("HTTP 429: pausing all REST requests for %ds", retry_s or 60)


async def guarded_get_json(
    session: aiohttp.ClientSession,
    limiter: RateLimiter,
    url: str,
    weight: int,
    params: Mapping[str, str] | None = None,
    timeout_s: float = 10.0,
) -> Any:
    """GET with the rate-limit guard; raises ``aiohttp.ClientResponseError`` on HTTP errors."""
    await limiter.acquire(weight)
    async with session.get(
        url, params=params, timeout=aiohttp.ClientTimeout(total=timeout_s)
    ) as resp:
        limiter.on_response(resp.status, resp.headers)
        resp.raise_for_status()
        return await resp.json()

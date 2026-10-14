"""REST depth snapshot fetcher (``GET /fapi/v1/depth``) for the local order book.

Public endpoint, no signature: plain aiohttp (ADR-0004). Weight: limit 1000 -> 20.
"""

from __future__ import annotations

import aiohttp

from scalping.core.clock import Clock
from scalping.core.models import OrderBookSnapshot
from scalping.market_data.order_book import SnapshotFetcher
from scalping.market_data.parser import parse_depth_snapshot

DEPTH_PATH = "/fapi/v1/depth"
_VALID_LIMITS = (5, 10, 20, 50, 100, 500, 1000)


def make_snapshot_fetcher(
    session: aiohttp.ClientSession,
    rest_base_url: str,
    clock: Clock,
    limit: int = 1000,
    timeout_s: float = 5.0,
) -> SnapshotFetcher:
    if limit not in _VALID_LIMITS:
        raise ValueError(f"limit must be one of {_VALID_LIMITS}")
    url = f"{rest_base_url.rstrip('/')}{DEPTH_PATH}"
    timeout = aiohttp.ClientTimeout(total=timeout_s)

    async def fetch(symbol: str) -> OrderBookSnapshot:
        params = {"symbol": symbol, "limit": str(limit)}
        async with session.get(url, params=params, timeout=timeout) as resp:
            resp.raise_for_status()  # 429/418 -> ClientResponseError; manager backs off
            data = await resp.json()
        return parse_depth_snapshot(symbol, data, clock.now_ms())

    return fetch

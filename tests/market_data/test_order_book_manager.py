import asyncio
import json
from collections.abc import AsyncIterator, Callable
from decimal import Decimal as D

import aiohttp
import pytest
from aiohttp import web

from scalping.core import FixedClock, OrderBookDelta, OrderBookSnapshot, PriceLevel
from scalping.market_data import (
    DeltaResult,
    OrderBookManager,
    ResyncPolicy,
    SyncState,
    make_snapshot_fetcher,
)

SYM = "BTCUSDT"
T0 = 1_760_400_000_000
FAST = ResyncPolicy(initial_backoff_s=0.001, max_backoff_s=0.005, max_latency_ms=500)


def delta(U: int, u: int, pu: int, latency_ms: int = 5) -> OrderBookDelta:
    return OrderBookDelta(SYM, U, u, pu, (), (), T0 + u, T0 + u, T0 + u + latency_ms)


def snap(lid: int) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        SYM, lid, (PriceLevel(D("100"), D("1")),), (PriceLevel(D("101"), D("1")),), T0
    )


class FakeFetcher:
    """Returns queued snapshots (or raises queued exceptions) once ``gate`` is open."""

    def __init__(self, *results: OrderBookSnapshot | Exception) -> None:
        self.results = list(results)
        self.calls = 0
        self.gate = asyncio.Event()
        self.gate.set()

    async def __call__(self, symbol: str) -> OrderBookSnapshot:
        self.calls += 1
        await self.gate.wait()
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


async def wait_for_state(manager: OrderBookManager, state: SyncState) -> None:
    async def poll() -> None:
        while manager.books[SYM].state is not state:
            await asyncio.sleep(0.001)

    await asyncio.wait_for(poll(), timeout=2)


async def test_connect_buffers_then_syncs() -> None:
    fetcher = FakeFetcher(snap(100))
    fetcher.gate.clear()  # hold the snapshot until deltas are buffered
    manager = OrderBookManager([SYM], fetcher, FAST)

    await manager.on_connected()
    assert manager.handle(delta(95, 101, pu=94)) is DeltaResult.BUFFERED
    assert manager.handle(delta(102, 103, pu=101)) is DeltaResult.BUFFERED
    fetcher.gate.set()
    await wait_for_state(manager, SyncState.SYNCED)

    assert manager.books[SYM].last_update_id == 103
    assert manager.is_tradeable(SYM)
    assert fetcher.calls == 1
    await manager.close()


async def test_gap_triggers_new_snapshot() -> None:
    fetcher = FakeFetcher(snap(100), snap(200))
    manager = OrderBookManager([SYM], fetcher, FAST)
    await manager.on_connected()
    await wait_for_state(manager, SyncState.AWAITING_BRIDGE)
    manager.handle(delta(100, 101, pu=99))
    assert manager.books[SYM].is_synced

    assert manager.handle(delta(150, 201, pu=149)) is DeltaResult.GAP
    await wait_for_state(manager, SyncState.SYNCED)  # snapshot 200 bridges buffered 150..201
    assert manager.books[SYM].last_update_id == 201
    assert fetcher.calls == 2 and manager.books[SYM].gaps == 1
    await manager.close()


async def test_fetch_errors_and_stale_snapshots_are_retried() -> None:
    fetcher = FakeFetcher(OSError("network down"), snap(50), snap(100))
    manager = OrderBookManager([SYM], fetcher, FAST)
    manager.handle(delta(99, 101, pu=98))  # buffered; first handle schedules resync
    await wait_for_state(manager, SyncState.SYNCED)
    assert fetcher.calls == 3  # error, too old (50 < U-1), ok
    await manager.close()


async def test_reconnect_rebuilds_synced_book() -> None:
    fetcher = FakeFetcher(snap(100), snap(500))
    manager = OrderBookManager([SYM], fetcher, FAST)
    await manager.on_connected()
    await wait_for_state(manager, SyncState.AWAITING_BRIDGE)
    manager.handle(delta(100, 101, pu=99))

    await manager.on_connected()
    await wait_for_state(manager, SyncState.AWAITING_BRIDGE)
    assert manager.books[SYM].last_update_id == 500
    await manager.close()


async def test_high_latency_makes_book_untradeable() -> None:
    manager = OrderBookManager([SYM], FakeFetcher(snap(100)), FAST)
    await manager.on_connected()
    await wait_for_state(manager, SyncState.AWAITING_BRIDGE)
    manager.handle(delta(100, 101, pu=99, latency_ms=900))
    assert manager.books[SYM].is_synced and not manager.is_tradeable(SYM)
    manager.handle(delta(102, 102, pu=101, latency_ms=20))
    assert manager.is_tradeable(SYM)
    await manager.close()


async def test_non_depth_and_unknown_symbols_are_ignored() -> None:
    manager = OrderBookManager([SYM], FakeFetcher(), FAST)
    other = OrderBookDelta("ETHUSDT", 1, 2, 0, (), (), T0, T0, T0)
    assert manager.handle(other) is None
    await manager.close()


# ------------------------------------------------------------------ REST fetcher


@pytest.fixture
async def depth_server(
    binance_raw: Callable[[str], str],
) -> AsyncIterator[tuple[str, list[dict[str, str]]]]:
    seen: list[dict[str, str]] = []

    async def depth(request: web.Request) -> web.Response:
        seen.append(dict(request.query))
        if request.query["symbol"] == "LIMITED":
            return web.Response(status=429)
        return web.json_response(json.loads(binance_raw("depth_snapshot_rest.json")))

    app = web.Application()
    app.router.add_get("/fapi/v1/depth", depth)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    yield f"http://127.0.0.1:{port}", seen
    await runner.cleanup()


async def test_rest_snapshot_fetcher(depth_server: tuple[str, list[dict[str, str]]]) -> None:
    base_url, seen = depth_server
    async with aiohttp.ClientSession() as session:
        fetch = make_snapshot_fetcher(session, base_url, FixedClock(T0), limit=1000)
        book = await fetch(SYM)
        with pytest.raises(aiohttp.ClientResponseError):
            await fetch("LIMITED")

    assert seen[0] == {"symbol": SYM, "limit": "1000"}
    assert book.symbol == SYM and book.last_update_id == 8123456690
    assert book.best_bid == PriceLevel(D("64250.00"), D("2.104"))


def test_rest_snapshot_fetcher_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError):
        make_snapshot_fetcher(None, "http://x", FixedClock(T0), limit=7)  # type: ignore[arg-type]

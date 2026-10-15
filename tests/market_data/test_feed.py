"""End-to-end feed test against local WS (/public, /market) and REST servers: no internet."""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from aiohttp import web
from websockets.asyncio.server import ServerConnection, serve

from scalping.config import Settings
from scalping.core import AggregatedTrade, Kline, MarketEvent
from scalping.market_data import MarketDataFeed, ReconnectPolicy, ResyncPolicy, StreamRoute

FAST_WS = ReconnectPolicy(initial_backoff_s=0.01, max_backoff_s=0.05, stale_timeout_s=5)
FAST_RESYNC = ResyncPolicy(initial_backoff_s=0.01, max_backoff_s=0.05)
SNAPSHOT_LID = 8123456690  # depth_snapshot_rest.json


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def depth_frame(U: int, u: int, pu: int, bids: list[list[str]]) -> str:
    data = {"e": "depthUpdate", "E": now_ms(), "T": now_ms(), "s": "BTCUSDT",
            "U": U, "u": u, "pu": pu, "b": bids, "a": []}  # fmt: skip
    return json.dumps({"stream": "btcusdt@depth@100ms", "data": data})


@pytest.fixture
async def servers(binance_raw: Callable[[str], str]) -> AsyncIterator[dict[str, Any]]:
    paths: list[str] = []

    async def ws_handler(ws: ServerConnection) -> None:
        path = ws.request.path if ws.request else ""
        paths.append(path)
        if path.startswith("/public/"):
            await ws.send(depth_frame(SNAPSHOT_LID - 10, SNAPSHOT_LID + 5, SNAPSHOT_LID - 11,
                                      [["64250.00", "3.000"]]))  # fmt: skip
            await ws.send(depth_frame(SNAPSHOT_LID + 6, SNAPSHOT_LID + 9, SNAPSHOT_LID + 5,
                                      [["64249.90", "0"]]))  # fmt: skip
        elif path.startswith("/market/"):
            await ws.send(binance_raw("agg_trade_combined.json"))
            await ws.send(binance_raw("kline_1m.json"))
        await ws.wait_closed()

    async def depth(request: web.Request) -> web.Response:
        return web.json_response(json.loads(binance_raw("depth_snapshot_rest.json")))

    async def server_time(request: web.Request) -> web.Response:
        return web.json_response({"serverTime": now_ms()})

    app = web.Application()
    app.router.add_get("/fapi/v1/depth", depth)
    app.router.add_get("/fapi/v1/time", server_time)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    rest_port = runner.addresses[0][1]

    async with serve(ws_handler, "127.0.0.1", 0) as ws_server:
        ws_port = next(iter(ws_server.sockets)).getsockname()[1]
        yield {
            "ws": f"ws://127.0.0.1:{ws_port}",
            "rest": f"http://127.0.0.1:{rest_port}",
            "paths": paths,
        }
    await runner.cleanup()


async def test_feed_end_to_end(servers: dict[str, Any]) -> None:
    received: list[MarketEvent] = []
    settings = Settings(_env_file=None, symbols="BTCUSDT")  # type: ignore[call-arg]
    feed = MarketDataFeed(
        settings,
        on_event=received.append,
        reconnect_policy=FAST_WS,
        resync_policy=FAST_RESYNC,
        ws_base_url=servers["ws"],
        rest_base_url=servers["rest"],
    )
    assert set(feed.urls) == {StreamRoute.PUBLIC, StreamRoute.MARKET}

    task = asyncio.create_task(feed.run())

    async def ready() -> None:
        while not (
            feed.manager is not None
            and feed.manager.books["BTCUSDT"].last_update_id == SNAPSHOT_LID + 9
            and len(received) >= 2
        ):
            await asyncio.sleep(0.005)

    try:
        await asyncio.wait_for(ready(), timeout=5)
    finally:
        await feed.stop()
        await asyncio.wait_for(task, timeout=5)

    assert feed.manager is not None
    book = feed.manager.books["BTCUSDT"]
    assert book.gaps == 0 and feed.parse_errors == 0
    assert feed.manager.is_tradeable("BTCUSDT")
    best = book.snapshot(levels=2).bids
    assert [str(lvl.price) for lvl in best] == ["64250.00", "64249.50"]  # 64249.90 removed
    assert best[0].qty == 3
    assert {type(e) for e in received} == {AggregatedTrade, Kline}
    assert sorted(p.split("?")[0] for p in servers["paths"]) == [
        "/market/stream",
        "/public/stream",
    ]
    assert feed.stats.events["OrderBookDelta"] == 2


def test_feed_stats_latency_percentiles() -> None:
    from scalping.market_data import FeedStats

    stats = FeedStats()
    assert stats.latency_percentile(99) == 0.0
    stats.latency_sample.extend(range(1, 101))  # 1..100 ms
    assert (stats.latency_percentile(50), stats.latency_percentile(99)) == (51.0, 100.0)

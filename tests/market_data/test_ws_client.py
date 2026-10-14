"""WS client against a local in-process server (127.0.0.1): no internet required."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from websockets.asyncio.server import Server, ServerConnection, serve

from scalping.core import AggregatedTrade, FixedClock, Kline, MarketEvent, OrderBookDelta
from scalping.market_data import BinanceFuturesWsClient, ReconnectPolicy

FAST = ReconnectPolicy(initial_backoff_s=0.01, max_backoff_s=0.05, stale_timeout_s=0.3)
T0 = 1_760_400_000_000


ServerFactory = Callable[[list[list[str]]], Awaitable[str]]


@pytest.fixture
async def server_factory() -> AsyncIterator[ServerFactory]:
    servers: list[Server] = []

    async def start(sessions: list[list[str]]) -> str:
        """Each connection consumes the next session: sends its frames, then closes."""
        remaining = list(sessions)

        async def handler(ws: ServerConnection) -> None:
            frames = remaining.pop(0) if remaining else []
            for frame in frames:
                await ws.send(frame)
            if not remaining and not frames:
                await ws.wait_closed()  # idle until the client disconnects

        server = await serve(handler, "127.0.0.1", 0)
        servers.append(server)
        port = next(iter(server.sockets)).getsockname()[1]
        return f"ws://127.0.0.1:{port}"

    yield start
    for server in servers:
        server.close()
        await server.wait_closed()


async def _collect(queue: asyncio.Queue[MarketEvent], n: int) -> list[MarketEvent]:
    return [await asyncio.wait_for(queue.get(), timeout=3) for _ in range(n)]


async def test_receives_events_and_reconnects(
    server_factory: ServerFactory, binance_raw: Callable[[str], str]
) -> None:
    url = await server_factory(
        [
            [binance_raw("agg_trade_combined.json")],
            [binance_raw("depth_update.json"), binance_raw("kline_1m.json")],
        ]
    )
    queue: asyncio.Queue[MarketEvent] = asyncio.Queue()
    connections = 0

    async def on_connected() -> None:
        nonlocal connections
        connections += 1

    client = BinanceFuturesWsClient(url, queue, FixedClock(T0), FAST, on_connected)
    task = asyncio.create_task(client.run())
    try:
        events = await _collect(queue, 3)
    finally:
        await client.stop()
        await asyncio.wait_for(task, timeout=3)

    assert [type(e) for e in events] == [AggregatedTrade, OrderBookDelta, Kline]
    assert all(e.recv_time == T0 for e in events)
    assert connections >= 2 and client.reconnects >= 1


async def test_parse_errors_do_not_kill_the_stream(
    server_factory: ServerFactory, binance_raw: Callable[[str], str]
) -> None:
    url = await server_factory(
        [["garbage", '{"result":null,"id":1}', binance_raw("kline_1m.json")]]
    )
    queue: asyncio.Queue[MarketEvent] = asyncio.Queue()
    client = BinanceFuturesWsClient(url, queue, FixedClock(T0), FAST)
    task = asyncio.create_task(client.run())
    try:
        (event,) = await _collect(queue, 1)
    finally:
        await client.stop()
        await asyncio.wait_for(task, timeout=3)

    assert isinstance(event, Kline)
    assert client.parse_errors == 1


async def test_stop_while_idle_returns_promptly(server_factory: ServerFactory) -> None:
    url = await server_factory([[]])
    client = BinanceFuturesWsClient(url, asyncio.Queue(), FixedClock(T0), ReconnectPolicy())
    task = asyncio.create_task(client.run())
    await asyncio.sleep(0.2)
    await client.stop()
    await asyncio.wait_for(task, timeout=2)


def test_backoff_is_bounded_and_jittered() -> None:
    policy = ReconnectPolicy(initial_backoff_s=0.5, max_backoff_s=30.0)
    for attempt in range(20):
        delay = policy.backoff(attempt)
        ceiling = min(30.0, 0.5 * 2**attempt)
        assert ceiling / 2 <= delay <= ceiling

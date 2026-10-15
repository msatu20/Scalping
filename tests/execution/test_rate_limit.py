"""T9: rate-limit guard — budget per minute, header sync, 429 pause, 418 ban."""

import asyncio
from collections.abc import AsyncIterator

import aiohttp
import pytest
from aiohttp import web

from scalping.core import FixedClock
from scalping.execution import (
    IpBannedError,
    RateLimiter,
    depth_weight,
    guarded_get_json,
)

T0 = 1_791_763_200_000  # minute boundary


def make(budget_limit: int = 100) -> tuple[RateLimiter, FixedClock, list[float]]:
    clock = FixedClock(T0)
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:  # advance simulated time instead of waiting
        slept.append(seconds)
        clock.advance(int(seconds * 1000))

    return RateLimiter(clock, weight_limit=budget_limit, safety=0.8, sleep=fake_sleep), clock, slept


async def test_budget_waits_for_next_minute() -> None:
    limiter, clock, slept = make()  # budget 80
    for _ in range(4):
        await limiter.acquire(20)
    assert slept == [] and limiter.used == 80
    clock.advance(15_000)
    await limiter.acquire(20)  # over budget -> wait 45 s until the next minute
    assert slept == [45.0] and limiter.used == 20


async def test_headers_sync_used_weight() -> None:
    limiter, _, slept = make()
    await limiter.acquire(1)
    limiter.on_response(200, {"X-MBX-USED-WEIGHT-1M": "79"})  # other processes share the IP
    await limiter.acquire(5)
    assert slept == [60.0]


async def test_429_pauses_everything() -> None:
    limiter, _, slept = make()
    await limiter.acquire(1)
    limiter.on_response(429, {"Retry-After": "7"})
    await limiter.acquire(1)
    assert slept[0] == 7.0


async def test_418_bans_and_blocks() -> None:
    limiter, clock, _ = make()
    await limiter.acquire(1)
    with pytest.raises(IpBannedError):
        limiter.on_response(418, {"Retry-After": "120"})
    assert limiter.is_banned()
    with pytest.raises(IpBannedError):
        await limiter.acquire(1)
    clock.advance(120_000)
    assert not limiter.is_banned()
    await limiter.acquire(1)


async def test_concurrent_callers_do_not_overshoot() -> None:
    limiter, _, slept = make()  # budget 80
    await asyncio.gather(*(limiter.acquire(20) for _ in range(5)))
    assert len(slept) == 1 and limiter.used == 20  # 5th waited for the next minute


def test_weights_and_validation() -> None:
    assert [depth_weight(n) for n in (5, 50, 100, 500, 1000)] == [2, 2, 5, 10, 20]
    limiter, _, _ = make()
    with pytest.raises(ValueError):
        asyncio.run(limiter.acquire(81))
    with pytest.raises(ValueError):
        RateLimiter(FixedClock(T0), safety=0)


@pytest.fixture
async def api() -> AsyncIterator[str]:
    async def ok(request: web.Request) -> web.Response:
        return web.json_response({"ok": True}, headers={"X-MBX-USED-WEIGHT-1M": "42"})

    async def banned(request: web.Request) -> web.Response:
        return web.Response(status=418, headers={"Retry-After": "30"})

    app = web.Application()
    app.router.add_get("/ok", ok)
    app.router.add_get("/banned", banned)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    yield f"http://127.0.0.1:{runner.addresses[0][1]}"
    await runner.cleanup()


async def test_guarded_get_json_against_server(api: str) -> None:
    limiter, _, _ = make(budget_limit=2400)
    async with aiohttp.ClientSession() as session:
        assert await guarded_get_json(session, limiter, f"{api}/ok", weight=1) == {"ok": True}
        assert limiter.used == 42
        with pytest.raises(IpBannedError):
            await guarded_get_json(session, limiter, f"{api}/banned", weight=1)
    assert limiter.is_banned()

"""Read-only smoke test against real Binance USDS-M Futures public streams (T7/T10).

No API keys, no orders: forces TRADING_MODE=paper and only listens to public data.

    .venv/Scripts/python.exe scripts/smoke_market_data.py --seconds 120

Exit code 0 if every book synced with zero sequence gaps and zero parse errors.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from scalping.config import Settings, TradingMode
from scalping.market_data import MarketDataFeed


def report(feed: MarketDataFeed, elapsed: int) -> None:
    assert feed.manager is not None
    books = ", ".join(
        f"{s}:{b.state} lid={b.last_update_id} gaps={b.gaps} buf={b.buffered} "
        f"tradeable={feed.manager.is_tradeable(s)}"
        for s, b in feed.manager.books.items()
    )
    st = feed.stats
    print(
        f"[{elapsed:>4}s] events={dict(st.events)} deltas={dict(st.delta_results)} "
        f"latency avg={st.avg_latency_ms:.0f} p50={st.latency_percentile(50):.0f} "
        f"p90={st.latency_percentile(90):.0f} p99={st.latency_percentile(99):.0f} "
        f"max={st.max_latency_ms}ms "
        f"queue_max={st.max_queue_size} parse_errors={feed.parse_errors} "
        f"reconnects={feed.reconnects} snapshots={feed.manager.snapshot_requests} | {books}",
        flush=True,
    )


async def main(seconds: int, interval: int) -> int:
    settings = Settings(_env_file=None, trading_mode=TradingMode.PAPER)  # type: ignore[call-arg]
    feed = MarketDataFeed(settings)
    print("streams:", feed.urls, flush=True)
    task = asyncio.create_task(feed.run())
    elapsed = 0
    try:
        while elapsed < seconds:
            await asyncio.sleep(interval)
            elapsed += interval
            if feed.manager is not None:
                report(feed, elapsed)
    finally:
        await feed.stop()
        await asyncio.wait_for(task, timeout=10)

    assert feed.manager is not None
    books = feed.manager.books.values()
    checks = {
        "all books SYNCED": all(b.is_synced for b in books),
        "zero sequence gaps": all(b.gaps == 0 for b in books),
        "zero parse errors": feed.parse_errors == 0,
        "aggTrades received": feed.stats.events["AggregatedTrade"] > 0,
        "klines received": feed.stats.events["Kline"] > 0,
    }
    print("\nRESULT")
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "WARNING"))
    sys.exit(asyncio.run(main(args.seconds, args.interval)))

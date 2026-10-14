"""Real Binance USDⓈ-M Futures public streams. Read-only: no keys, no orders.

Run explicitly: ``pytest -m live_readonly`` (excluded from the default run).
"""

import asyncio

import pytest

from scalping.config import Settings, TradingMode
from scalping.market_data import MarketDataFeed

pytestmark = pytest.mark.live_readonly

SYMBOLS = ("BTCUSDT", "ETHUSDT")


async def test_live_feed_syncs_books_without_gaps() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, trading_mode=TradingMode.PAPER, symbols=",".join(SYMBOLS)
    )
    feed = MarketDataFeed(settings)
    task = asyncio.create_task(feed.run())
    try:
        await asyncio.sleep(20)
    finally:
        await feed.stop()
        await asyncio.wait_for(task, timeout=10)

    assert feed.manager is not None
    for symbol in SYMBOLS:
        book = feed.manager.books[symbol]
        assert book.is_synced, f"{symbol} is {book.state}"
        assert book.gaps == 0
        top = book.snapshot(levels=5)
        assert top.bids[0].price < top.asks[0].price
    assert feed.parse_errors == 0
    assert feed.stats.delta_results["APPLIED"] > 100
    assert feed.stats.events["AggregatedTrade"] > 0
    assert feed.stats.events["Kline"] > 0

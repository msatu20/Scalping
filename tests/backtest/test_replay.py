"""ReplayFeed: ordering, clock integrity, live-interface parity, fail-fast on missing data."""

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from scalping.backtest import (
    DataKind,
    HistoricalStore,
    MissingDataError,
    ReplayFeed,
    day_start_ms,
)
from scalping.core import AggregatedTrade, FixedClock, Kline, MarketEvent, MarketFeed
from scalping.market_data import MarketDataFeed

D1, D2 = date(2026, 10, 11), date(2026, 10, 12)
T1 = day_start_ms(D1)
T2 = day_start_ms(D2)


def klines(open_times: list[int], close: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame({
        "open_time": open_times,
        "open": close, "high": close + 1, "low": close - 1, "close": close,
        "volume": 2.5, "close_time": [t + 59_999 for t in open_times],
        "quote_volume": 250.0, "count": 7, "taker_buy_volume": 1.5,
        "taker_buy_quote_volume": 150.0,
    })  # fmt: skip


def trades(times: list[int], first_id: int = 1, price: float = 100.1) -> pd.DataFrame:
    n = len(times)
    ids = list(range(first_id, first_id + n))
    return pd.DataFrame({
        "agg_trade_id": ids, "price": price, "quantity": 0.25,
        "first_trade_id": ids, "last_trade_id": ids, "transact_time": times,
        "is_buyer_maker": [i % 2 == 0 for i in range(n)],
    })  # fmt: skip


@pytest.fixture
def store(tmp_path: Path) -> HistoricalStore:
    s = HistoricalStore(tmp_path)
    for day, t0 in ((D1, T1), (D2, T2)):
        s.write(klines([t0, t0 + 60_000]), s.path(DataKind.KLINES, "BTCUSDT", day))
        s.write(klines([t0], close=2500.0), s.path(DataKind.KLINES, "ETHUSDT", day))
        # trade at the candle's last ms (t0+59_999) must come before that candle's kline
        s.write(
            trades([t0 + 10, t0 + 59_999, t0 + 61_000]), s.path(DataKind.AGG_TRADES, "BTCUSDT", day)
        )
        s.write(
            trades([t0 + 5], first_id=900, price=2500.5),
            s.path(DataKind.AGG_TRADES, "ETHUSDT", day),
        )
    return s


def describe(e: MarketEvent) -> tuple[str, str, int]:
    return (type(e).__name__, e.symbol, e.event_time)


def test_events_are_time_ordered_with_deterministic_ties(store: HistoricalStore) -> None:
    feed = ReplayFeed(store, ["BTCUSDT", "ETHUSDT"], D1, D1)
    assert [describe(e) for e in feed.events()] == [
        ("AggregatedTrade", "ETHUSDT", T1 + 5),
        ("AggregatedTrade", "BTCUSDT", T1 + 10),
        ("AggregatedTrade", "BTCUSDT", T1 + 59_999),  # trade before its candle at same ms
        ("Kline", "BTCUSDT", T1 + 59_999),  # symbol order breaks kline ties
        ("Kline", "ETHUSDT", T1 + 59_999),
        ("AggregatedTrade", "BTCUSDT", T1 + 61_000),
        ("Kline", "BTCUSDT", T1 + 119_999),
    ]


def test_events_are_core_models_with_exact_decimals(store: HistoricalStore) -> None:
    events = list(ReplayFeed(store, ["ETHUSDT"], D1, D1).events())
    trade, kline = events
    assert isinstance(trade, AggregatedTrade) and isinstance(kline, Kline)
    assert trade.price == Decimal("2500.5") and str(trade.qty) == "0.25"
    assert trade.agg_trade_id == 900 and trade.is_buyer_maker is True
    assert kline.is_closed and kline.close == Decimal("2500.0") and kline.trades == 7
    assert kline.event_time == kline.close_time == T1 + 59_999


def test_clock_advances_with_each_event(store: HistoricalStore) -> None:
    feed = ReplayFeed(store, ["BTCUSDT", "ETHUSDT"], D1, D2, latency_ms=25)
    seen: list[tuple[int, int]] = []
    feed.replay(lambda e: seen.append((feed.clock.now_ms(), e.recv_time)))

    assert len(seen) == 14
    assert all(now == recv for now, recv in seen)  # clock == event time when handled
    assert [now for now, _ in seen] == sorted(now for now, _ in seen)  # monotonic
    assert seen[0][0] == T1 + 5 + 25  # latency applied
    assert feed.clock.now_ms() == T2 + 119_999 + 25


async def test_async_run_matches_sync_replay_and_never_leaks_future_time(
    store: HistoricalStore,
) -> None:
    sync_events = list(ReplayFeed(store, ["BTCUSDT", "ETHUSDT"], D1, D2).events())

    received: list[MarketEvent] = []
    clock_ok: list[bool] = []
    feed: ReplayFeed

    def on_event(e: MarketEvent) -> None:
        clock_ok.append(feed.clock.now_ms() == e.recv_time)
        received.append(e)

    # Tiny queue: the producer runs ahead of the consumer; the clock must not.
    feed = ReplayFeed(store, ["BTCUSDT", "ETHUSDT"], D1, D2, on_event=on_event, queue_maxsize=2)
    assert isinstance(feed, MarketFeed)
    await asyncio.wait_for(feed.run(), timeout=5)

    assert received == sync_events
    assert all(clock_ok) and len(clock_ok) == 14
    assert feed.stats.events == {"AggregatedTrade": 8, "Kline": 6}


def test_live_feed_satisfies_same_protocol() -> None:
    from scalping.config import Settings

    assert isinstance(MarketDataFeed(Settings(_env_file=None)), MarketFeed)  # type: ignore[call-arg]


def test_stop_from_inside_handler(store: HistoricalStore) -> None:
    feed = ReplayFeed(store, ["BTCUSDT"], D1, D2)
    handled: list[MarketEvent] = []

    def on_event(e: MarketEvent) -> None:
        handled.append(e)
        if len(handled) == 3:
            feed.request_stop()

    assert feed.replay(on_event) == 3


def test_missing_data_fails_before_any_event(store: HistoricalStore) -> None:
    feed = ReplayFeed(store, ["BTCUSDT", "SOLUSDT"], D1, D2)
    handled: list[MarketEvent] = []
    with pytest.raises(MissingDataError, match="SOLUSDT"):
        feed.replay(handled.append)
    assert handled == []


def test_klines_only_and_validation(store: HistoricalStore) -> None:
    feed = ReplayFeed(store, ["BTCUSDT"], D1, D1, agg_trades=False)
    assert {type(e) for e in feed.events()} == {Kline}
    with pytest.raises(ValueError):
        ReplayFeed(store, ["BTCUSDT"], D1, D1, intervals=(), agg_trades=False)
    with pytest.raises(ValueError):
        ReplayFeed(store, [], D1, D1)
    with pytest.raises(ValueError):
        ReplayFeed(store, ["BTCUSDT"], D1, D1, latency_ms=-1)


def test_clock_cannot_go_backwards(store: HistoricalStore) -> None:
    late_clock = FixedClock(T2)
    with pytest.raises(ValueError, match="backwards"):
        ReplayFeed(store, ["BTCUSDT"], D1, D1, clock=late_clock).replay()
    with pytest.raises(ValueError):
        FixedClock(10).advance(-1)


async def test_handler_error_propagates_without_hanging(store: HistoricalStore) -> None:
    def boom(e: MarketEvent) -> None:
        raise RuntimeError("strategy bug")

    feed = ReplayFeed(store, ["BTCUSDT", "ETHUSDT"], D1, D2, on_event=boom, queue_maxsize=1)
    with pytest.raises(ExceptionGroup) as err:
        await asyncio.wait_for(feed.run(), timeout=5)
    assert err.group_contains(RuntimeError, match="strategy bug")

"""DepthRecorder: sampling synced books, padding, flush layout, stop file, loader."""

import asyncio
import math
from datetime import UTC, date, datetime
from decimal import Decimal as D
from pathlib import Path

import pandas as pd
import pytest

from scalping.core import Clock, FixedClock, OrderBookDelta, OrderBookSnapshot, PriceLevel
from scalping.market_data import OrderBookManager
from scalping.market_data.depth_recorder import (
    STOP_FILE,
    DepthRecorder,
    RecorderConfig,
    depth_columns,
    load_depth,
)

T0 = int(datetime(2026, 10, 14, 12, 30, tzinfo=UTC).timestamp() * 1000)


class FakeSource:
    def __init__(self, manager: OrderBookManager, clock: Clock) -> None:
        self.manager: OrderBookManager | None = manager
        self.clock: Clock | None = clock


async def never(symbol: str) -> OrderBookSnapshot:
    raise AssertionError("not used")


def synced_manager() -> OrderBookManager:
    manager = OrderBookManager(["BTCUSDT", "ETHUSDT"], never)
    book = manager.books["BTCUSDT"]
    bids = (PriceLevel(D("100.0"), D("1.5")),)
    asks = (PriceLevel(D("100.1"), D("2")), PriceLevel(D("100.2"), D("3")))
    snap = OrderBookSnapshot("BTCUSDT", 100, bids, asks, T0)
    assert book.apply_snapshot(snap)
    book.apply_delta(OrderBookDelta("BTCUSDT", 100, 101, 99, (), (), T0 + 5, T0 + 5, T0 + 45))
    return manager


def test_sample_and_flush(tmp_path: Path) -> None:
    clock = FixedClock(T0 + 100)
    rec = DepthRecorder(FakeSource(synced_manager(), clock), ["BTCUSDT", "ETHUSDT"],
                        RecorderConfig(root=tmp_path, levels=2))  # fmt: skip
    assert rec.sample(clock.now_ms()) == 1  # ETHUSDT not synced -> skipped
    assert rec.stats["skipped_unsynced_ETHUSDT"] == 1

    (path,) = rec.flush()
    assert path == tmp_path / "futures_um/depth/BTCUSDT/2026-10-14/123000.parquet"
    frame = pd.read_parquet(path)
    assert list(frame.columns) == depth_columns(2)
    row = frame.iloc[0]
    assert (row.ts, row.event_time, row.last_update_id, row.latency_ms) == (
        T0 + 100,
        T0 + 5,
        101,
        40,
    )
    assert (row.bid_px_0, row.bid_qty_0, row.ask_px_0, row.ask_qty_1) == (100.0, 1.5, 100.1, 3.0)
    assert math.isnan(row.bid_px_1)  # bid side shorter than levels -> NaN padding
    assert rec.flush() == []  # buffer cleared
    assert not list(tmp_path.rglob("*.tmp"))


def test_load_depth_concatenates_and_sorts(tmp_path: Path) -> None:
    clock = FixedClock(T0)
    rec = DepthRecorder(FakeSource(synced_manager(), clock), ["BTCUSDT"],
                        RecorderConfig(root=tmp_path, levels=1))  # fmt: skip
    rec.sample(T0 + 2000)
    rec.flush()
    rec.sample(T0 + 1000)  # later file, earlier ts
    clock.advance(60_000)
    rec._rows["BTCUSDT"][0][0] = T0 + 61_000  # different file name
    rec.flush()
    frame = load_depth(tmp_path, "BTCUSDT", date(2026, 10, 14), date(2026, 10, 14))
    assert frame["ts"].tolist() == [T0 + 2000, T0 + 61_000]
    assert load_depth(tmp_path, "SOLUSDT", date(2026, 10, 14), date(2026, 10, 14)).empty


async def test_run_stops_on_stop_file_and_flushes(tmp_path: Path) -> None:
    config = RecorderConfig(root=tmp_path, levels=1, interval_ms=10, flush_every_s=3600)
    clock = FixedClock(T0)
    rec = DepthRecorder(FakeSource(synced_manager(), clock), ["BTCUSDT"], config)
    task = asyncio.create_task(rec.run())
    await asyncio.sleep(0.1)
    config.depth_dir.mkdir(parents=True, exist_ok=True)
    (config.depth_dir / STOP_FILE).touch()
    await asyncio.wait_for(task, timeout=2)
    assert rec.stats["samples"] >= 3 and rec.stats["files_written"] == 1


def test_config_validation() -> None:
    with pytest.raises(ValueError):
        RecorderConfig(levels=0)

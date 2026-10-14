"""Depth recorder (T14): sample the synced local order book to Parquet (K17).

Binance publishes no historical depth, so book-based strategies (imbalance,
``ORDER_FLOW_SQUEEZE``) can only be backtested from our own recordings.

Every ``interval_ms`` the top ``levels`` of each *synced* book are sampled (unsynced
books are skipped and counted). Rows are flushed every ``flush_every_s`` to
``<root>/futures_um/depth/<SYMBOL>/<YYYY-MM-DD>/<HHMMSS>.parquet`` (atomic writes; a
crash loses at most one flush interval). Creating ``<root>/futures_um/depth/STOP``
stops the recorder gracefully (final flush) on any OS.

Columns: ``ts`` (sample time, server-aligned clock), ``event_time`` (book's last
exchange event), ``last_update_id``, ``latency_ms`` (-1 unknown), then
``bid_px_i, bid_qty_i, ask_px_i, ask_qty_i`` for i < levels (NaN if the side is shorter).
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

from scalping.core.clock import Clock
from scalping.market_data.order_book import OrderBookManager

log = logging.getLogger(__name__)

DEPTH_SUBDIR = Path("futures_um") / "depth"
STOP_FILE = "STOP"


class DepthSource(Protocol):
    """What the recorder needs from a running feed (``MarketDataFeed`` satisfies it)."""

    manager: OrderBookManager | None
    clock: Clock | None


@dataclass(frozen=True, slots=True)
class RecorderConfig:
    root: Path = Path("data")
    levels: int = 20
    interval_ms: int = 250
    flush_every_s: int = 600

    def __post_init__(self) -> None:
        if self.levels < 1 or self.interval_ms < 10 or self.flush_every_s < 1:
            raise ValueError("levels >= 1, interval_ms >= 10, flush_every_s >= 1")

    @property
    def depth_dir(self) -> Path:
        return self.root / DEPTH_SUBDIR


def depth_columns(levels: int) -> list[str]:
    cols = ["ts", "event_time", "last_update_id", "latency_ms"]
    for i in range(levels):
        cols += [f"bid_px_{i}", f"bid_qty_{i}", f"ask_px_{i}", f"ask_qty_{i}"]
    return cols


class DepthRecorder:
    def __init__(self, source: DepthSource, symbols: Sequence[str], config: RecorderConfig) -> None:
        self._source = source
        self._symbols = list(symbols)
        self.config = config
        self._rows: dict[str, list[list[float]]] = {s: [] for s in self._symbols}
        self.stats: Counter[str] = Counter()
        self._last_flush_ms: int | None = None

    def sample(self, now_ms: int) -> int:
        """Append one row per synced book. Returns the number of rows sampled."""
        manager = self._source.manager
        if manager is None:
            return 0
        sampled = 0
        n = self.config.levels
        for symbol in self._symbols:
            book = manager.books[symbol]
            if not book.is_synced:
                self.stats[f"skipped_unsynced_{symbol}"] += 1
                continue
            snap = book.snapshot(levels=n)
            latency = book.last_latency_ms
            row: list[float] = [now_ms, snap.timestamp, snap.last_update_id,
                                -1 if latency is None else latency]  # fmt: skip
            for i in range(n):
                bid = snap.bids[i] if i < len(snap.bids) else None
                ask = snap.asks[i] if i < len(snap.asks) else None
                row += [
                    float(bid.price) if bid else math.nan,
                    float(bid.qty) if bid else math.nan,
                    float(ask.price) if ask else math.nan,
                    float(ask.qty) if ask else math.nan,
                ]
            self._rows[symbol].append(row)
            sampled += 1
        self.stats["samples"] += sampled
        return sampled

    def flush(self) -> list[Path]:
        """Write buffered rows (one file per symbol) and clear the buffers."""
        written = []
        columns = depth_columns(self.config.levels)
        for symbol, rows in self._rows.items():
            if not rows:
                continue
            frame = pd.DataFrame(rows, columns=columns)
            for col in ("ts", "event_time", "last_update_id", "latency_ms"):
                frame[col] = frame[col].astype("int64")
            first = datetime.fromtimestamp(rows[0][0] / 1000, UTC)
            path = (self.config.depth_dir / symbol / first.date().isoformat()
                    / f"{first:%H%M%S}.parquet")  # fmt: skip
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            frame.to_parquet(tmp, index=False, compression="zstd")
            os.replace(tmp, path)
            written.append(path)
            self.stats["rows_written"] += len(rows)
            self.stats["files_written"] += 1
            rows.clear()
        return written

    def stop_requested(self) -> bool:
        return (self.config.depth_dir / STOP_FILE).exists()

    async def run(self) -> None:
        """Sample until the STOP file appears or the task is cancelled; always flushes."""
        interval = self.config.interval_ms / 1000
        try:
            while not self.stop_requested():
                await asyncio.sleep(interval)
                clock = self._source.clock
                if clock is None:
                    continue
                now = clock.now_ms()
                self.sample(now)
                if self._last_flush_ms is None:
                    self._last_flush_ms = now
                elif now - self._last_flush_ms >= self.config.flush_every_s * 1000:
                    self.flush()
                    self._last_flush_ms = now
        finally:
            self.flush()
            log.info("depth recorder stopped: %s", dict(self.stats))


def load_depth(root: Path | str, symbol: str, start: date, end: date) -> pd.DataFrame:
    """Concatenate recorded depth for ``symbol`` between two days (inclusive), sorted by ts."""
    base = Path(root) / DEPTH_SUBDIR / symbol
    files = sorted(
        f
        for d in base.iterdir()
        if d.is_dir() and start <= date.fromisoformat(d.name) <= end
        for f in d.glob("*.parquet")
    ) if base.exists() else []  # fmt: skip
    if not files:
        return pd.DataFrame(columns=depth_columns(1))
    frame = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    return frame.sort_values("ts", ignore_index=True)

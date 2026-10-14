"""Parquet store for historical market data (ADR-0006).

Layout (one file per UTC day, written atomically)::

    <root>/futures_um/klines/<interval>/<SYMBOL>/<YYYY-MM-DD>.parquet
    <root>/futures_um/aggTrades/<SYMBOL>/<YYYY-MM-DD>.parquet

Prices/quantities are float64 parsed with round-trip precision; convert to ``Decimal``
with ``Decimal(str(x))`` only at the order boundary. Timestamps are int64 ms UTC.
Loading a range with missing days raises: a backtest must never skip data silently.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import date, timedelta
from enum import StrEnum
from pathlib import Path

import pandas as pd

from scalping.core.models import KlineInterval

_INTERVAL_MS = {KlineInterval.M1: 60_000, KlineInterval.M3: 180_000, KlineInterval.M5: 300_000}


class DataKind(StrEnum):
    KLINES = "klines"
    AGG_TRADES = "aggTrades"


class MissingDataError(LookupError):
    def __init__(self, kind: DataKind, symbol: str, days: Sequence[date]) -> None:
        self.days = list(days)
        preview = ", ".join(d.isoformat() for d in self.days[:5])
        more = f" (+{len(self.days) - 5} more)" if len(self.days) > 5 else ""
        super().__init__(f"missing {kind} for {symbol}: {preview}{more}")


def day_range(start: date, end: date) -> list[date]:
    """Inclusive list of days."""
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


class HistoricalStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def path(
        self, kind: DataKind, symbol: str, day: date, interval: KlineInterval = KlineInterval.M1
    ) -> Path:
        base = self.root / "futures_um" / kind
        folder = base / interval / symbol if kind is DataKind.KLINES else base / symbol
        return folder / f"{day.isoformat()}.parquet"

    def has(
        self, kind: DataKind, symbol: str, day: date, interval: KlineInterval = KlineInterval.M1
    ) -> bool:
        return self.path(kind, symbol, day, interval).exists()

    def write(self, frame: pd.DataFrame, path: Path) -> None:
        """Atomic write: readers never see a half-written file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        frame.to_parquet(tmp, index=False, compression="zstd")
        os.replace(tmp, path)

    def load(
        self,
        kind: DataKind,
        symbol: str,
        start: date,
        end: date,
        interval: KlineInterval = KlineInterval.M1,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        days = day_range(start, end)
        paths = [self.path(kind, symbol, day, interval) for day in days]
        missing = [day for day, path in zip(days, paths, strict=True) if not path.exists()]
        if missing:
            raise MissingDataError(kind, symbol, missing)
        frames = [
            pd.read_parquet(path, columns=list(columns) if columns else None) for path in paths
        ]
        return pd.concat(frames, ignore_index=True)


def find_kline_gaps(klines: pd.DataFrame, interval: KlineInterval) -> pd.DataFrame:
    """Rows where the next candle does not start exactly one interval later.

    Returns ``open_time`` (last candle before the gap) and ``missing`` (candle count).
    """
    step = _INTERVAL_MS[interval]
    diff = klines["open_time"].diff().shift(-1)
    gaps = klines.loc[diff > step, ["open_time"]].copy()
    gaps["missing"] = (diff[diff > step] // step - 1).astype("int64")
    return gaps.reset_index(drop=True)

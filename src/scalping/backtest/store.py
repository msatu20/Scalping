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
    step = interval.ms
    diff = klines["open_time"].diff().shift(-1)
    gaps = klines.loc[diff > step, ["open_time"]].copy()
    gaps["missing"] = (diff[diff > step] // step - 1).astype("int64")
    return gaps.reset_index(drop=True)


_SUM_COLUMNS = ("volume", "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume")


def resample_klines(
    klines: pd.DataFrame, target: KlineInterval, strict: bool = True
) -> pd.DataFrame:
    """Aggregate 1m klines into ``target`` candles (Binance definition: open of the first,
    max high, min low, close of the last, summed volumes). Requires complete buckets."""
    step = target.ms
    bucket = klines["open_time"] // step * step
    grouped = klines.groupby(bucket, sort=True)
    sizes = grouped.size()
    expected = step // KlineInterval.M1.ms
    if strict and (sizes != expected).any():
        incomplete = sizes[sizes != expected].index.tolist()[:3]
        raise ValueError(f"incomplete {target} buckets (first: {incomplete})")
    out = pd.DataFrame(
        {
            "open_time": sizes.index.to_numpy(dtype="int64"),
            "open": grouped["open"].first().to_numpy(),
            "high": grouped["high"].max().to_numpy(),
            "low": grouped["low"].min().to_numpy(),
            "close": grouped["close"].last().to_numpy(),
            "close_time": (sizes.index + step - 1).to_numpy(dtype="int64"),
        }
    )
    for col in _SUM_COLUMNS:
        if col in klines:
            out[col] = grouped[col].sum().to_numpy()
    # Column order as downloaded klines.
    order = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "count",
        "taker_buy_volume",
        "taker_buy_quote_volume",
    ]
    return out[[c for c in order if c in out]]


def resample_day(store: HistoricalStore, symbol: str, day: date, target: KlineInterval) -> bool:
    """Write ``target`` klines for ``day`` from stored 1m klines. False if already present.

    Tolerates missing minutes (exchange outages): like Binance, a candle aggregates the
    minutes that exist; buckets with no minute at all produce no candle.
    """
    path = store.path(DataKind.KLINES, symbol, day, target)
    if path.exists():
        return False
    minute = store.load(DataKind.KLINES, symbol, day, day, KlineInterval.M1)
    store.write(resample_klines(minute, target, strict=False), path)
    return True


def available_segments(
    store: HistoricalStore,
    kind: DataKind,
    symbol: str,
    start: date,
    end: date,
    interval: KlineInterval = KlineInterval.M1,
) -> list[tuple[date, date]]:
    """Contiguous runs of stored days in ``[start, end]`` (e.g. listing/delisting, outages)."""
    segments: list[tuple[date, date]] = []
    run_start: date | None = None
    prev: date | None = None
    for day in day_range(start, end):
        if store.has(kind, symbol, day, interval):
            if run_start is None:
                run_start = day
            prev = day
        elif run_start is not None and prev is not None:
            segments.append((run_start, prev))
            run_start = None
    if run_start is not None and prev is not None:
        segments.append((run_start, prev))
    return segments

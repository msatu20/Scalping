"""Historical funding rates (USDⓈ-M perpetuals) for backtests.

Source: public REST ``GET /fapi/v1/fundingRate`` (rate + mark price per settlement;
data.binance.vision only publishes complete months). Stored per symbol at
``<root>/futures_um/fundingRate/<SYMBOL>.parquet`` (merged and de-duplicated).

Payment at each settlement for an open position (Binance definition):
``payment = -side * qty * mark_price * rate`` (side +1 long / -1 short): with a positive
rate longs pay shorts.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

from scalping.backtest.store import HistoricalStore

FUNDING_PATH = "/fapi/v1/fundingRate"
_PAGE_LIMIT = 1000


@dataclass(frozen=True, slots=True)
class FundingEvent:
    time: int
    rate: Decimal
    mark_price: Decimal | None


def funding_path(store: HistoricalStore, symbol: str) -> Path:
    return store.root / "futures_um" / "fundingRate" / f"{symbol}.parquet"


async def fetch_funding_rates(
    session: aiohttp.ClientSession,
    rest_base_url: str,
    symbol: str,
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    """All settlements in ``[start_ms, end_ms]``, paginated (1000 rows per request)."""
    url = f"{rest_base_url.rstrip('/')}{FUNDING_PATH}"
    rows: list[dict[str, Any]] = []
    cursor = start_ms
    while cursor <= end_ms:
        params = {"symbol": symbol, "startTime": str(cursor), "endTime": str(end_ms),
                  "limit": str(_PAGE_LIMIT)}  # fmt: skip
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            page = await resp.json()
        rows.extend(page)
        if len(page) < _PAGE_LIMIT:
            break
        cursor = int(page[-1]["fundingTime"]) + 1
    return pd.DataFrame(
        {
            "funding_time": [int(r["fundingTime"]) for r in rows],
            # Kept as strings: exact Decimal reconstruction (rates have up to 8 decimals).
            "funding_rate": [str(r["fundingRate"]) for r in rows],
            "mark_price": [str(r.get("markPrice") or "") for r in rows],
        }
    ).astype({"funding_time": "int64"})


def save_funding(store: HistoricalStore, symbol: str, frame: pd.DataFrame) -> int:
    """Merge with stored rows (de-duplicated by time). Returns total stored rows."""
    path = funding_path(store, symbol)
    if path.exists():
        frame = pd.concat([pd.read_parquet(path), frame], ignore_index=True)
    frame = frame.drop_duplicates("funding_time").sort_values("funding_time", ignore_index=True)
    store.write(frame, path)
    return len(frame)


class FundingSchedule:
    """Settlements sorted by time; rates kept as exact Decimals (stored as strings)."""

    def __init__(self, events: list[FundingEvent]) -> None:
        self._events = sorted(events, key=lambda e: e.time)
        self._times = [e.time for e in self._events]

    @classmethod
    def load(cls, store: HistoricalStore, symbol: str) -> FundingSchedule:
        path = funding_path(store, symbol)
        if not path.exists():
            raise FileNotFoundError(f"no funding data for {symbol}: {path}")
        frame = pd.read_parquet(path)
        return cls([
            FundingEvent(int(t), Decimal(str(r)), Decimal(str(m)) if m else None)
            for t, r, m in zip(frame["funding_time"], frame["funding_rate"],
                               frame["mark_price"], strict=True)
        ])  # fmt: skip

    def __len__(self) -> int:
        return len(self._events)

    def between(self, after_ms: int, up_to_ms: int) -> list[FundingEvent]:
        """Settlements with ``after_ms < time <= up_to_ms``."""
        lo = bisect.bisect_right(self._times, after_ms)
        hi = bisect.bisect_right(self._times, up_to_ms)
        return self._events[lo:hi]

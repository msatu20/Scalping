"""Download Binance USDⓈ-M Futures daily history from data.binance.vision (T5).

Every file is verified against its ``.CHECKSUM`` (SHA-256) before being parsed and
stored. Already-stored days are skipped, so re-running a range is cheap and resumes
interrupted downloads. Days not yet published (e.g. today) are reported as missing.
"""

from __future__ import annotations

import asyncio
import calendar
import hashlib
import io
import logging
import random
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import aiohttp
import pandas as pd

from scalping.backtest.replay import day_start_ms
from scalping.backtest.store import DataKind, HistoricalStore, day_range
from scalping.core.models import KlineInterval

log = logging.getLogger(__name__)

BASE_URL = "https://data.binance.vision/data/futures/um/daily"
MONTHLY_BASE_URL = "https://data.binance.vision/data/futures/um/monthly"

KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]  # fmt: skip
AGG_TRADE_COLUMNS = [
    "agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id",
    "transact_time", "is_buyer_maker",
]  # fmt: skip

_KLINE_DTYPES = {
    "open_time": "int64", "close_time": "int64", "count": "int64",
    **{c: "float64" for c in ("open", "high", "low", "close", "volume", "quote_volume",
                               "taker_buy_volume", "taker_buy_quote_volume")},
}  # fmt: skip
_AGG_TRADE_DTYPES = {
    "agg_trade_id": "int64", "first_trade_id": "int64", "last_trade_id": "int64",
    "transact_time": "int64", "price": "float64", "quantity": "float64",
}  # fmt: skip
_TIME_COLUMNS = {
    DataKind.KLINES: ("open_time", "close_time"),
    DataKind.AGG_TRADES: ("transact_time",),
}
# Anything above this is microseconds (ms timestamps stay below until year 5138).
_MAX_MS_TIMESTAMP = 10**14


class ChecksumError(ValueError):
    pass


class DownloadStatus(StrEnum):
    DOWNLOADED = "downloaded"
    SKIPPED = "skipped"  # already in the store
    MISSING = "missing"  # not published (404)


@dataclass(frozen=True, slots=True)
class DownloadResult:
    kind: DataKind
    symbol: str
    day: date
    status: DownloadStatus
    rows: int = 0


def daily_url(
    kind: DataKind,
    symbol: str,
    day: date,
    interval: KlineInterval = KlineInterval.M1,
    base_url: str = BASE_URL,
) -> str:
    base = base_url.rstrip("/")
    if kind is DataKind.KLINES:
        return f"{base}/klines/{symbol}/{interval}/{symbol}-{interval}-{day.isoformat()}.zip"
    return f"{base}/aggTrades/{symbol}/{symbol}-aggTrades-{day.isoformat()}.zip"


def monthly_url(
    kind: DataKind,
    symbol: str,
    month: date,
    interval: KlineInterval = KlineInterval.M1,
    base_url: str = MONTHLY_BASE_URL,
) -> str:
    base, ym = base_url.rstrip("/"), f"{month.year:04d}-{month.month:02d}"
    if kind is DataKind.KLINES:
        return f"{base}/klines/{symbol}/{interval}/{symbol}-{interval}-{ym}.zip"
    return f"{base}/aggTrades/{symbol}/{symbol}-aggTrades-{ym}.zip"


def _month_days(month: date) -> list[date]:
    last = calendar.monthrange(month.year, month.month)[1]
    return day_range(date(month.year, month.month, 1), date(month.year, month.month, last))


def _full_months(start: date, end: date) -> list[date]:
    """First days of the calendar months entirely inside ``[start, end]``."""
    months = []
    m = date(start.year, start.month, 1)
    while m <= end:
        days = _month_days(m)
        if days[0] >= start and days[-1] <= end:
            months.append(m)
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    return months


def verify_checksum(payload: bytes, checksum_text: str) -> None:
    """``.CHECKSUM`` format: ``<sha256 hex>  <file name>``."""
    expected = checksum_text.split()[0].lower() if checksum_text.strip() else ""
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ChecksumError(f"sha256 mismatch: expected {expected or '<empty>'}, got {actual}")


def repair_klines(frame: pd.DataFrame) -> pd.DataFrame:
    """Fix upstream inconsistencies seen in Binance files (logged, never silent).

    Taker-buy volume above total volume (2 rows in ~27 M 1m klines, e.g. XRPUSDT
    2023-11-30) is clipped to the total; the quote counterpart likewise.
    """
    for taker, total in (
        ("taker_buy_volume", "volume"),
        ("taker_buy_quote_volume", "quote_volume"),
    ):
        if taker in frame and total in frame:
            bad = frame[taker] > frame[total]
            if bad.any():
                first = int(frame.loc[bad, "open_time"].iloc[0])
                log.warning(
                    "data repair: %d rows with %s > %s (first open_time %d)",
                    int(bad.sum()), taker, total, first,
                )  # fmt: skip
                frame.loc[bad, taker] = frame.loc[bad, total]
    return frame


def parse_daily_zip(payload: bytes, kind: DataKind) -> pd.DataFrame:
    """Zipped CSV -> typed DataFrame. Handles files with and without header row."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.namelist()
        if len(members) != 1:
            raise ValueError(f"expected one CSV in zip, got {members}")
        raw = archive.read(members[0])

    columns = KLINE_COLUMNS if kind is DataKind.KLINES else AGG_TRADE_COLUMNS
    has_header = not raw[:1].isdigit()
    if has_header:
        header = raw.split(b"\n", 1)[0].decode().strip().split(",")
        if header != columns:
            raise ValueError(f"unexpected CSV header {header}; schema changed?")
    frame = pd.read_csv(
        io.BytesIO(raw),
        header=0 if has_header else None,
        names=columns,
        dtype=_KLINE_DTYPES if kind is DataKind.KLINES else _AGG_TRADE_DTYPES,
        true_values=["true", "True"],
        false_values=["false", "False"],
        float_precision="round_trip",
    )
    if kind is DataKind.KLINES:
        frame = repair_klines(frame.drop(columns="ignore"))
    elif frame["is_buyer_maker"].dtype != bool:
        raise ValueError(f"is_buyer_maker is not boolean: {frame['is_buyer_maker'].dtype}")

    for column in _TIME_COLUMNS[kind]:
        if len(frame) and frame[column].max() > _MAX_MS_TIMESTAMP:
            frame[column] = frame[column] // 1000  # microseconds -> ms
    if frame.isna().any().any():
        raise ValueError("CSV contains empty values")
    if not frame[_TIME_COLUMNS[kind][0]].is_monotonic_increasing:
        raise ValueError("rows are not sorted by time")
    return frame


class BinanceVisionDownloader:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        store: HistoricalStore,
        base_url: str = BASE_URL,
        concurrency: int = 4,
        max_retries: int = 3,
    ) -> None:
        self._session = session
        self._store = store
        self._base_url = base_url
        # data.binance.vision publishes the same files per month under /monthly/.
        self._monthly_base_url = base_url.rstrip("/").removesuffix("/daily") + "/monthly"
        self._semaphore = asyncio.Semaphore(concurrency)
        self._max_retries = max_retries

    async def download_range(
        self,
        symbols: Sequence[str],
        kinds: Sequence[DataKind],
        start: date,
        end: date,
        interval: KlineInterval = KlineInterval.M1,
        monthly: bool = False,
    ) -> list[DownloadResult]:
        """Daily files; with ``monthly=True`` complete calendar months come from one monthly
        file each (far fewer requests) and the remaining days from daily files."""
        results: list[DownloadResult] = []
        for symbol in symbols:
            for kind in kinds:
                days = day_range(start, end)
                if monthly:
                    months = _full_months(start, end)
                    month_results = await asyncio.gather(
                        *(self.download_month(kind, symbol, m, interval) for m in months)
                    )
                    results.extend(month_results)
                    covered = {
                        d
                        for m, r in zip(months, month_results, strict=True)
                        if r.status is not DownloadStatus.MISSING
                        for d in _month_days(m)
                    }
                    days = [d for d in days if d not in covered]
                results.extend(
                    await asyncio.gather(
                        *(self.download_day(kind, symbol, d, interval) for d in days)
                    )
                )
        return results

    async def download_month(
        self, kind: DataKind, symbol: str, month: date, interval: KlineInterval = KlineInterval.M1
    ) -> DownloadResult:
        """One monthly file split into the daily store layout (only missing days written)."""
        days = _month_days(month)
        missing = [d for d in days if not self._store.has(kind, symbol, d, interval)]
        if not missing:
            return DownloadResult(kind, symbol, month, DownloadStatus.SKIPPED)
        url = monthly_url(kind, symbol, month, interval, self._monthly_base_url)
        async with self._semaphore:
            payload = await self._get(url)
            if payload is None:
                log.info("not published: %s", url)
                return DownloadResult(kind, symbol, month, DownloadStatus.MISSING)
            checksum = await self._get(url + ".CHECKSUM")
            if checksum is None:
                raise ChecksumError(f"checksum file missing for {url}")
            verify_checksum(payload, checksum.decode())
            frame = await asyncio.to_thread(parse_daily_zip, payload, kind)
            del payload
            rows = await asyncio.to_thread(self._write_days, frame, kind, symbol, interval, missing)
        log.info("stored %s %s %s (%d rows, %d days)", kind, symbol, month, rows, len(missing))
        return DownloadResult(kind, symbol, month, DownloadStatus.DOWNLOADED, rows)

    def _write_days(
        self,
        frame: pd.DataFrame,
        kind: DataKind,
        symbol: str,
        interval: KlineInterval,
        days: Sequence[date],
    ) -> int:
        time_col = _TIME_COLUMNS[kind][0]
        day_index = frame[time_col] // 86_400_000
        written = 0
        for day in days:
            part = frame[day_index == day_start_ms(day) // 86_400_000]
            if part.empty:
                continue  # no data that day (e.g. before listing / after delisting)
            self._store.write(
                part.reset_index(drop=True), self._store.path(kind, symbol, day, interval)
            )
            written += len(part)
        return written

    async def download_day(
        self, kind: DataKind, symbol: str, day: date, interval: KlineInterval = KlineInterval.M1
    ) -> DownloadResult:
        path = self._store.path(kind, symbol, day, interval)
        if path.exists():
            return DownloadResult(kind, symbol, day, DownloadStatus.SKIPPED)
        url = daily_url(kind, symbol, day, interval, self._base_url)
        # The semaphore bounds the whole day (download + parse + write): parsed aggTrades
        # days hold millions of rows, so unbounded parsing exhausts memory.
        async with self._semaphore:
            payload = await self._get(url)
            if payload is None:
                log.info("not published: %s", url)
                return DownloadResult(kind, symbol, day, DownloadStatus.MISSING)
            checksum = await self._get(url + ".CHECKSUM")
            if checksum is None:
                raise ChecksumError(f"checksum file missing for {url}")
            verify_checksum(payload, checksum.decode())
            frame = await asyncio.to_thread(parse_daily_zip, payload, kind)
            del payload
            await asyncio.to_thread(self._store.write, frame, path)
            rows = len(frame)
            del frame
        log.info("stored %s %s %s (%d rows)", kind, symbol, day, rows)
        return DownloadResult(kind, symbol, day, DownloadStatus.DOWNLOADED, rows)

    async def _get(self, url: str) -> bytes | None:
        """Body, or None on 404. Retries network errors and 5xx/429 with backoff."""
        for attempt in range(self._max_retries + 1):
            try:
                async with self._session.get(url) as resp:
                    if resp.status == 404:
                        return None
                    if resp.status == 429 or resp.status >= 500:
                        raise aiohttp.ClientResponseError(
                            resp.request_info, resp.history, status=resp.status
                        )
                    resp.raise_for_status()
                    return await resp.read()
            except (aiohttp.ClientError, TimeoutError) as exc:
                retryable = not isinstance(exc, aiohttp.ClientResponseError) or (
                    exc.status == 429 or exc.status >= 500
                )
                if not retryable or attempt == self._max_retries:
                    raise
                delay = random.uniform(0.5, 1.0) * 2**attempt
                log.warning("GET %s failed (%r), retry in %.1fs", url, exc, delay)
                await asyncio.sleep(delay)
        raise AssertionError("unreachable")

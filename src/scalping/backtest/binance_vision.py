"""Download Binance USDⓈ-M Futures daily history from data.binance.vision (T5).

Every file is verified against its ``.CHECKSUM`` (SHA-256) before being parsed and
stored. Already-stored days are skipped, so re-running a range is cheap and resumes
interrupted downloads. Days not yet published (e.g. today) are reported as missing.
"""

from __future__ import annotations

import asyncio
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

from scalping.backtest.store import DataKind, HistoricalStore, day_range
from scalping.core.models import KlineInterval

log = logging.getLogger(__name__)

BASE_URL = "https://data.binance.vision/data/futures/um/daily"

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


def verify_checksum(payload: bytes, checksum_text: str) -> None:
    """``.CHECKSUM`` format: ``<sha256 hex>  <file name>``."""
    expected = checksum_text.split()[0].lower() if checksum_text.strip() else ""
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ChecksumError(f"sha256 mismatch: expected {expected or '<empty>'}, got {actual}")


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
        frame = frame.drop(columns="ignore")
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
        self._semaphore = asyncio.Semaphore(concurrency)
        self._max_retries = max_retries

    async def download_range(
        self,
        symbols: Sequence[str],
        kinds: Sequence[DataKind],
        start: date,
        end: date,
        interval: KlineInterval = KlineInterval.M1,
    ) -> list[DownloadResult]:
        jobs = [
            self.download_day(kind, symbol, day, interval)
            for symbol in symbols
            for kind in kinds
            for day in day_range(start, end)
        ]
        return list(await asyncio.gather(*jobs))

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

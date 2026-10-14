"""Download Binance USDⓈ-M Futures history (klines + aggTrades) to Parquet (T5).

    .venv/Scripts/python.exe scripts/download_history.py --start 2026-10-01 --end 2026-10-13
    .venv/Scripts/python.exe scripts/download_history.py --days 7 --kinds klines

Defaults: symbols from settings (BTCUSDT, ETHUSDT), klines 1m + aggTrades, ./data.
Size guide: klines 1m ~60 KB/day/symbol; aggTrades ~15-50 MB/day/symbol (zipped).
Re-running skips stored days. Public data only: no API keys.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta

import aiohttp

from scalping.backtest import (
    BinanceVisionDownloader,
    DataKind,
    DownloadStatus,
    HistoricalStore,
    day_start_ms,
    fetch_funding_rates,
    save_funding,
)
from scalping.config import Settings
from scalping.core import KlineInterval

PUBLICATION_LAG_DAYS = 2


async def main(args: argparse.Namespace) -> int:
    symbols = args.symbols or list(Settings(_env_file=None).symbols)  # type: ignore[call-arg]
    store = HistoricalStore(args.data_dir)
    timeout = aiohttp.ClientTimeout(total=600)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        downloader = BinanceVisionDownloader(session, store, concurrency=args.concurrency)
        results = await downloader.download_range(
            symbols, [DataKind(k) for k in args.kinds], args.start, args.end, args.interval
        )
        if args.funding:
            rest = Settings(_env_file=None).rest_base_url  # type: ignore[call-arg]
            end_ms = day_start_ms(args.end) + 86_400_000 - 1
            for symbol in symbols:
                frame = await fetch_funding_rates(
                    session, rest, symbol, day_start_ms(args.start), end_ms
                )
                total = save_funding(store, symbol, frame)
                print(f"  fundingRate {symbol}: {len(frame)} fetched, {total} stored")

    summary = Counter((r.kind.value, r.status.value) for r in results)
    rows = sum(r.rows for r in results)
    print(f"{symbols} {args.start}..{args.end} -> {store.root.resolve()}")
    for (kind, status), count in sorted(summary.items()):
        print(f"  {kind:<10} {status:<11} {count} day(s)")
    print(f"  rows written: {rows:,}")
    # Binance publishes each daily file some hours after the UTC day closes.
    recent = datetime.now(UTC).date() - timedelta(days=PUBLICATION_LAG_DAYS)
    missing = [r for r in results if r.status is DownloadStatus.MISSING]
    for r in missing:
        note = "not published yet" if r.day >= recent else "NOT AVAILABLE"
        print(f"  missing {r.kind} {r.symbol} {r.day} ({note})")
    return 1 if any(r.day < recent for r in missing) else 0


def parse_args() -> argparse.Namespace:
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--symbols", nargs="+", type=str.upper)
    parser.add_argument("--kinds", nargs="*", choices=[k.value for k in DataKind],
                        default=[k.value for k in DataKind])  # fmt: skip
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat, default=yesterday)
    parser.add_argument("--days", type=int, help="alternative to --start: last N days up to --end")
    parser.add_argument("--interval", type=KlineInterval, default=KlineInterval.M1)
    parser.add_argument("--funding", action="store_true", help="also fetch funding rates (REST)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    if args.start is None:
        if args.days is None:
            parser.error("use --start or --days")
        args.start = args.end - timedelta(days=args.days - 1)
    return args


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "WARNING"))
    sys.exit(asyncio.run(main(parse_args())))

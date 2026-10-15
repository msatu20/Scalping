"""Build 15m / 1h (or any) klines from stored 1m klines (validated exact vs Binance 5m).

    .venv/Scripts/python.exe scripts/resample_klines.py --start 2023-10-13 --end 2026-10-12

Days already present are skipped; days whose 1m data is missing or incomplete are reported
(download the official file for those with download_history.py --interval).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date

from scalping.backtest import HistoricalStore, MissingDataError, day_range
from scalping.backtest.store import resample_day
from scalping.core import KlineInterval


def main(args: argparse.Namespace) -> int:
    store = HistoricalStore(args.data_dir)
    summary: Counter[str] = Counter()
    problems: list[str] = []
    for symbol in args.symbols:
        for interval in args.intervals:
            for day in day_range(args.start, args.end):
                try:
                    summary[
                        "written" if resample_day(store, symbol, day, interval) else "skipped"
                    ] += 1
                except (MissingDataError, ValueError) as exc:
                    summary["failed"] += 1
                    problems.append(f"{symbol} {interval} {day}: {exc}")
    intervals = [str(i) for i in args.intervals]
    print(f"{args.symbols} {intervals} {args.start}..{args.end}: {dict(summary)}")
    for p in problems[:20]:
        print("  ", p)
    return 1 if problems else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--symbols", nargs="+", type=str.upper, default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument(
        "--intervals", nargs="+", type=KlineInterval, default=[KlineInterval.M15, KlineInterval.H1]
    )
    parser.add_argument("--data-dir", default="data")
    sys.exit(main(parser.parse_args()))

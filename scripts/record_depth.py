"""Record Binance USDⓈ-M depth (top-N of the synced local book) to Parquet — T14.

Public data only (no keys). Runs until stopped:

    .venv/Scripts/python.exe scripts/record_depth.py               # foreground
    New-Item data/futures_um/depth/STOP                            # graceful stop (any OS)

Logs go to logs/depth_recorder.log; the PID is written to data/futures_um/depth/recorder.pid.
Only the /public depth streams are subscribed (no trades/klines).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from scalping.config import Settings, TradingMode
from scalping.market_data import MarketDataFeed, depth_stream
from scalping.market_data.depth_recorder import STOP_FILE, DepthRecorder, RecorderConfig

log = logging.getLogger("record_depth")


async def status_loop(feed: MarketDataFeed, recorder: DepthRecorder, every_s: int) -> None:
    while True:
        await asyncio.sleep(every_s)
        books = {}
        if feed.manager is not None:
            books = {s: (str(b.state), b.gaps, b.last_latency_ms)
                     for s, b in feed.manager.books.items()}  # fmt: skip
        log.info("status books=%s reconnects=%d stats=%s", books, feed.reconnects,
                 dict(recorder.stats))  # fmt: skip


async def main(args: argparse.Namespace) -> int:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, trading_mode=TradingMode.PAPER, symbols=",".join(args.symbols)
    )
    config = RecorderConfig(root=Path(args.data_dir), levels=args.levels,
                            interval_ms=args.interval_ms, flush_every_s=args.flush_s)  # fmt: skip
    config.depth_dir.mkdir(parents=True, exist_ok=True)
    (config.depth_dir / STOP_FILE).unlink(missing_ok=True)
    (config.depth_dir / "recorder.pid").write_text(str(os.getpid()))

    feed = MarketDataFeed(settings, streams=[depth_stream(s) for s in settings.symbols])
    recorder = DepthRecorder(feed, settings.symbols, config)
    log.info("recording %s top-%d every %d ms -> %s", list(settings.symbols), config.levels,
             config.interval_ms, config.depth_dir.resolve())  # fmt: skip

    feed_task = asyncio.create_task(feed.run(), name="feed")
    status_task = asyncio.create_task(status_loop(feed, recorder, args.status_s), name="status")
    try:
        await recorder.run()  # returns when the STOP file appears
    finally:
        status_task.cancel()
        await feed.stop()
        await asyncio.wait_for(feed_task, timeout=15)
        (config.depth_dir / "recorder.pid").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--symbols", nargs="+", type=str.upper, default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--levels", type=int, default=20)
    parser.add_argument("--interval-ms", type=int, default=250)
    parser.add_argument("--flush-s", type=int, default=600)
    parser.add_argument("--status-s", type=int, default=300)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--log", default="logs/depth_recorder.log")
    args = parser.parse_args()
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(args.log, encoding="utf-8"), logging.StreamHandler()],
    )
    sys.exit(asyncio.run(main(args)))

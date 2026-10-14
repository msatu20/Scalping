"""Run MEAN_REVERSION over historical data with the replay engine and summarise signals.

    .venv/Scripts/python.exe scripts/run_signals.py --start 2026-07-16 --end 2026-10-12
    .venv/Scripts/python.exe scripts/run_signals.py --start 2026-10-11 --end 2026-10-12 \
        --trigger tick

The "first touch" section is a PRELIMINARY diagnostic, not a backtest: it checks whether
take profit or stop loss is touched first in later 1m candles (both in the same candle
counts as stop, conservatively), with no fills, fees, slippage or position sizing.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime

import numpy as np

from scalping.backtest import DataKind, HistoricalStore, ReplayFeed
from scalping.core import Side, Signal
from scalping.strategy.signals import MeanReversionParams, MeanReversionStrategy, TriggerMode

HORIZON_CANDLES = 60


def first_touch(signal: Signal, open_times: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> str:
    start = int(np.searchsorted(open_times, signal.created_at, side="right"))
    tp, sl = float(signal.take_profit), float(signal.stop_loss)
    for i in range(start, min(start + HORIZON_CANDLES, len(open_times))):
        if signal.side is Side.BUY:
            hit_sl, hit_tp = lows[i] <= sl, highs[i] >= tp
        else:
            hit_sl, hit_tp = highs[i] >= sl, lows[i] <= tp
        if hit_sl:
            return "sl"
        if hit_tp:
            return "tp"
    return "timeout"


def main(args: argparse.Namespace) -> int:
    store = HistoricalStore(args.data_dir)
    params = MeanReversionParams(trigger=TriggerMode(args.trigger))
    feed = ReplayFeed(store, args.symbols, args.start, args.end, agg_trades=args.trigger == "tick")
    signals: list[Signal] = []
    strategy = MeanReversionStrategy(args.symbols, feed.clock, params, on_signal=signals.append)
    events = feed.replay(strategy.on_event)

    print(f"replayed {events:,} events {args.start}..{args.end} trigger={args.trigger}")
    print(f"params: {params}\n")
    for symbol in args.symbols:
        mine = [s for s in signals if s.symbol == symbol]
        kl = store.load(DataKind.KLINES, symbol, args.start, args.end)
        ot, hi, lo = (kl[c].to_numpy() for c in ("open_time", "high", "low"))
        sides = Counter(s.side.value for s in mine)
        outcomes = Counter(first_touch(s, ot, hi, lo) for s in mine)
        weeks: dict[str, int] = defaultdict(int)
        for s in mine:
            weeks[datetime.fromtimestamp(s.created_at / 1000, UTC).strftime("%G-W%V")] += 1
        print(
            f"== {symbol}: {len(mine)} signals {dict(sides)} "
            f"| strategy stats {strategy.stats(symbol)}"
        )
        if not mine:
            continue
        conf = [s.confidence or 0.0 for s in mine]
        rr = [s.features["reward_risk"] for s in mine]
        tgt = [s.features["target_bps"] for s in mine]
        print(f"   per day {len(mine) / ((args.end - args.start).days + 1):.1f} | "
              f"confidence median {statistics.median(conf):.2f} | "
              f"reward/risk median {statistics.median(rr):.2f} | "
              f"target median {statistics.median(tgt):.1f} bps")  # fmt: skip
        print(f"   per ISO week: {dict(sorted(weeks.items()))}")
        decided = outcomes["tp"] + outcomes["sl"]
        rate = outcomes["tp"] / decided if decided else float("nan")
        print(f"   first touch within {HORIZON_CANDLES} candles (preliminary, no fees): "
              f"{dict(outcomes)} -> TP rate {rate:.1%}")  # fmt: skip
        last = mine[-1]
        print(f"   last: {datetime.fromtimestamp(last.created_at / 1000, UTC):%Y-%m-%d %H:%M} "
              f"{last.side} ref={last.reference_price} sl={last.stop_loss} tp={last.take_profit} "
              f"conf={last.confidence} | {last.reason}")  # fmt: skip
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--symbols", nargs="+", type=str.upper, default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--trigger", choices=[m.value for m in TriggerMode], default="close")
    parser.add_argument("--data-dir", default="data")
    sys.exit(main(parser.parse_args()))

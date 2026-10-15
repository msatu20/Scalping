"""T20 — TREND_BREAKOUT walk-forward research (pre-registered in ADR-0010).

    .venv/Scripts/python.exe scripts/research_trend_breakout.py --start 2023-10-13 --end 2026-10-12

One job per (symbol, strategy interval) over the whole period: the 8 variants of that
interval (+ their zero-cost controls) share a single replay pass (``run_many``). The broker
uses 1m candles as price path (pessimistic, ADR-0007). Results are cached per job.
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from scalping.backtest import (
    CostModel,
    DataKind,
    FundingSchedule,
    HistoricalStore,
    PriceSource,
    RunSpec,
    SizingParams,
    run_many,
)
from scalping.backtest.research import (
    CONTROL_SUFFIX,
    evaluate_criteria,
    fmt_stats,
    split_controls,
    walk_forward_report,
)
from scalping.backtest.store import available_segments
from scalping.backtest.walk_forward import TradeRecord, make_folds, walk_forward
from scalping.config import Settings
from scalping.core import Clock, KlineInterval
from scalping.strategy.signals import SignalHandler, TrendBreakoutParams, TrendBreakoutStrategy

SYMBOLS = ("BTCUSDT", "ETHUSDT")
ZERO_COSTS = CostModel(maker_fee=Decimal(0), taker_fee=Decimal(0), taker_slippage_bps=Decimal(0))
CACHE_VERSION = 1

Job = tuple[str, KlineInterval, date, date, str]


def grid(interval: KlineInterval) -> dict[str, TrendBreakoutParams]:
    return {
        f"{interval}-n{n}-k{k:g}-r{r:g}": TrendBreakoutParams(
            interval=interval, channel=n, atr_mult=k, target_r=r
        )
        for n in (20, 55)
        for k in (2.0, 3.0)
        for r in (2.0, 3.0)
    }


def run_job(job: Job) -> tuple[str, KlineInterval, dict[str, list[TradeRecord]], float]:
    symbol, interval, start, end, data_dir = job
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    store = HistoricalStore(data_dir)
    real_costs = CostModel.from_settings(settings)
    sizing = SizingParams(compounding=False, max_leverage=settings.max_leverage)
    specs = []
    for name, params in grid(interval).items():

        def factory(
            clock: Clock, on_signal: SignalHandler, p: TrendBreakoutParams = params
        ) -> TrendBreakoutStrategy:
            return TrendBreakoutStrategy([symbol], clock, p, on_signal)

        specs.append(RunSpec(name, factory, real_costs, sizing))
        specs.append(RunSpec(name + CONTROL_SUFFIX, factory, ZERO_COSTS, sizing))
    t0 = time.perf_counter()
    results = run_many(
        store,
        [symbol],
        start,
        end,
        specs,
        price_source=PriceSource.KLINES,
        funding={symbol: FundingSchedule.load(store, symbol)},
        strategy_interval=interval,
    )
    trades = {n: [TradeRecord.from_trade(t) for t in r.trades] for n, r in results.items()}
    return symbol, interval, trades, time.perf_counter() - t0


def main(args: argparse.Namespace) -> int:
    # One job per contiguous data segment (listing/delisting, exchange outages) of each
    # (symbol, interval); both the 1m price path and the strategy candles must exist.
    store = HistoricalStore(args.data_dir)
    jobs: list[Job] = []
    for s in args.symbols:
        minute = set(available_segments(store, DataKind.KLINES, s, args.start, args.end))
        for iv in args.intervals:
            for seg in available_segments(store, DataKind.KLINES, s, args.start, args.end, iv):
                if seg not in minute:
                    print(f"  WARNING {s} {iv} segment {seg} not matched by 1m data: skipped")
                    continue
                if (seg[1] - seg[0]).days < 30:
                    print(f"  WARNING {s} {iv} segment {seg} shorter than 30 days: skipped")
                    continue
                jobs.append((s, iv, seg[0], seg[1], args.data_dir))
    print(f"{len(jobs)} jobs")
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    trades: dict[str, list[TradeRecord]] = {}
    t0 = time.perf_counter()

    def cache(job: Job) -> Path:
        return args.cache_dir / f"v{CACHE_VERSION}_{job[0]}_{job[1]}_{job[2]}_{job[3]}.pkl"

    def collect(
        symbol: str, interval: KlineInterval, job_trades: dict[str, list[TradeRecord]], origin: str
    ) -> None:
        for name, recs in job_trades.items():
            trades.setdefault(name, []).extend(recs)
        n = sum(len(v) for k, v in job_trades.items() if not k.endswith(CONTROL_SUFFIX))
        print(f"  {symbol} {interval}: {n} trades (8 variants) {origin}", flush=True)

    pending = []
    for job in jobs:
        if cache(job).exists() and not args.fresh:
            with cache(job).open("rb") as fh:  # our own local cache files only
                symbol, interval, job_trades, _ = pickle.load(fh)
            collect(symbol, interval, job_trades, "cached")
        else:
            pending.append(job)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_job, job): job for job in pending}
        for fut in as_completed(futures):
            result = fut.result()
            tmp = cache(futures[fut]).with_suffix(".tmp")
            with tmp.open("wb") as fh:
                pickle.dump(result, fh)
            os.replace(tmp, cache(futures[fut]))
            collect(result[0], result[1], result[2], f"{result[3] / 60:.1f} min")

    real, _ = split_controls(trades)
    wf = walk_forward(real, make_folds(args.start, args.end), min_train_trades=30)
    print(f"\nOOS: {fmt_stats(wf.oos)}  (trades | mean R | total R | win | PF | maxDD R | t)")
    criteria = evaluate_criteria(wf)
    for c in criteria:
        print(f"  [{'OK' if c.passed else 'FAIL'}] {c.name}: {c.observed}")
    meta = [
        f"Generado {datetime.now(UTC):%Y-%m-%d %H:%M} UTC por `scripts/research_trend_breakout.py` "
        f"({(time.perf_counter() - t0) / 60:.1f} min). Datos {args.start}..{args.end}, "
        f"{', '.join(args.symbols)}; broker sobre velas 1m (pesimista), costes reales + funding.",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        walk_forward_report(args.title, meta, trades, wf, criteria),
        encoding="utf-8",
    )
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows consoles: cp1252
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--symbols", nargs="+", type=str.upper, default=list(SYMBOLS))
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/research/t20"))
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument(
        "--intervals", nargs="+", type=KlineInterval, default=[KlineInterval.M15, KlineInterval.H1]
    )
    parser.add_argument(
        "--title", default="T20 — TREND_BREAKOUT: walk-forward (pre-registrado en ADR-0010)"
    )
    default_report = Path("reports/2026-10-14-t20-trend-breakout-walk-forward.md")
    parser.add_argument("--report", type=Path, default=default_report)
    sys.exit(main(parser.parse_args()))
